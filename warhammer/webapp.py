from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from . import api_payloads as api_payload_service
from . import data_review as data_review_service
from . import editions as edition_service
from . import matchups as matchup_service
from . import unit_search as unit_search_service
from .calculator import EngagementContext
from .datasheet import _profile_priority, load_units_from_json
from .importers.csv_loader import load_units_from_directory
from .matchups import calculate_matchup
from .ml.advisory import load_advisory_model, ml_judgement_from_result, model_status
from .profiles import UnitProfile
from .rules import get_ruleset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDITION = "10e"
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / DEFAULT_EDITION / "latest"
LEGACY_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_JSON_PATH = PROJECT_ROOT / "units.json"
WEB_ROOT = PROJECT_ROOT / "web"
MODEL_ROOT = PROJECT_ROOT / "models"


@dataclass
class EditionDataset:
    edition: str
    data_dir: Optional[Path]
    source: str
    units: Dict[str, UnitProfile]
    metadata: Optional[Dict[str, Any]]

    def __post_init__(self) -> None:
        self.supported_rules_editions = _supported_rules_editions_from_metadata(self.metadata)
        self.units_by_id = {unit.unit_id: unit for unit in self.units.values() if unit.unit_id}
        self.units_by_name: Dict[str, list[UnitProfile]] = {}
        for unit in self.units.values():
            self.units_by_name.setdefault(unit.name.casefold(), []).append(unit)

    def require_unit(self, name: str = "", *, unit_id: Optional[str] = None) -> UnitProfile:
        if unit_id:
            unit = self.units_by_id.get(str(unit_id))
            if unit is not None:
                return unit
        key = (name or "").casefold()
        matches = self.units_by_name.get(key) or []
        if not matches:
            raise KeyError(unit_id or name)
        if len(matches) == 1:
            return matches[0]
        return sorted(matches, key=lambda profile: _profile_priority(profile, None), reverse=True)[0]


class AppState:
    def __init__(self, *, csv_dir: Optional[Path], json_path: Optional[Path]) -> None:
        if csv_dir:
            self.data_dir = csv_dir
            self.units = load_units_from_directory(csv_dir)
            self.source = str(csv_dir)
        elif json_path:
            self.data_dir = _default_data_dir()
            self.units = load_units_from_json(json_path)
            self.source = str(json_path)
        elif _default_data_dir():
            self.data_dir = _default_data_dir()
            self.units = load_units_from_directory(self.data_dir)
            self.source = str(self.data_dir)
        else:
            self.data_dir = None
            self.units = load_units_from_json(DEFAULT_JSON_PATH)
            self.source = str(DEFAULT_JSON_PATH)

        self.metadata = _load_json_file(self.data_dir / "metadata.json") if self.data_dir else None
        self.rules_edition = _rules_edition_from_metadata(self.metadata)
        self.supported_rules_editions = _supported_rules_editions_from_metadata(self.metadata)
        self.datasets: Dict[str, EditionDataset] = {
            self.rules_edition: EditionDataset(
                edition=self.rules_edition,
                data_dir=self.data_dir,
                source=self.source,
                units=self.units,
                metadata=self.metadata,
            )
        }
        discovered_editions = []
        if not json_path:
            discovered_editions = _discover_edition_data_dirs(DATA_ROOT, active_data_dir=self.data_dir)
            for row in discovered_editions:
                edition = str(row["edition"])
                path = Path(str(row["path"]))
                if edition in self.datasets or not row.get("rules_available"):
                    continue
                self.datasets[edition] = _load_edition_dataset(path, edition=edition)
        self.available_editions = _available_edition_rows(
            self.datasets,
            active_edition=self.rules_edition,
            discovered_rows=discovered_editions,
        )
        self.ml_models = {
            edition: load_advisory_model(MODEL_ROOT / edition / "matchup_centroid_model.json")
            for edition in self.datasets
        }

    def dataset_for_edition(self, edition: Optional[str] = None) -> EditionDataset:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        dataset = self.datasets.get(requested)
        if dataset is None:
            available = ", ".join(sorted(self.datasets))
            raise ValueError(f"Edition {requested!r} is not loaded; loaded editions: {available}")
        return dataset

    def require_unit(self, name: str = "", *, unit_id: Optional[str] = None, edition: Optional[str] = None) -> UnitProfile:
        return self.dataset_for_edition(edition).require_unit(name, unit_id=unit_id)

    def ml_model_for_edition(self, edition: Optional[str] = None) -> Optional[dict[str, Any]]:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        return self.ml_models.get(requested)

    def ml_model_dir_for_edition(self, edition: Optional[str] = None) -> Path:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        return MODEL_ROOT / requested

    def ml_model_status(self) -> dict[str, Any]:
        return {
            edition: model_status(model)
            for edition, model in self.ml_models.items()
        }


def _default_data_dir() -> Optional[Path]:
    if DEFAULT_CSV_DIR.exists():
        return DEFAULT_CSV_DIR
    if LEGACY_CSV_DIR.exists():
        return LEGACY_CSV_DIR
    return None


def _load_edition_dataset(data_dir: Path, *, edition: Optional[str] = None) -> EditionDataset:
    metadata = _load_json_file(data_dir / "metadata.json")
    resolved_edition = edition or _rules_edition_from_metadata(metadata)
    return EditionDataset(
        edition=resolved_edition,
        data_dir=data_dir,
        source=str(data_dir),
        units=load_units_from_directory(data_dir),
        metadata=metadata,
    )


def _available_edition_rows(
    datasets: Dict[str, EditionDataset],
    *,
    active_edition: str,
    discovered_rows: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, Any]]:
    return edition_service.available_edition_rows(
        datasets,
        active_edition=active_edition,
        discovered_rows=discovered_rows,
    )


def _discover_edition_data_dirs(data_root: Path, *, active_data_dir: Optional[Path] = None) -> list[Dict[str, Any]]:
    return edition_service.discover_edition_data_dirs(
        data_root,
        active_data_dir=active_data_dir,
        default_edition=DEFAULT_EDITION,
    )


def _edition_data_info(
    *,
    edition: str,
    data_dir: Optional[Path],
    metadata: Dict[str, Any],
    active_data_dir: Optional[Path] = None,
    active_edition: Optional[str] = None,
    loaded: bool = False,
) -> Dict[str, Any]:
    return edition_service.edition_data_info(
        edition=edition,
        data_dir=data_dir,
        metadata=metadata,
        active_data_dir=active_data_dir,
        active_edition=active_edition,
        loaded=loaded,
    )


def _edition_label(edition: str) -> str:
    return edition_service.edition_label(edition)


def _same_path(left: Path, right: Optional[Path]) -> bool:
    return edition_service.same_path(left, right)


def create_handler(state: AppState) -> type[SimpleHTTPRequestHandler]:
    class WarhammerHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json(
                    {
                        "ok": True,
                        "source": state.source,
                        "units": len(state.units),
                        "source_info": _source_info_from_metadata(state.metadata),
                        "available_editions": state.available_editions,
                        "ml_models": state.ml_model_status(),
                    }
                )
                return
            if parsed.path == "/api/data-review":
                query = parse_qs(parsed.query)
                try:
                    dataset = state.dataset_for_edition(query.get("edition", [""])[0] or None)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json(
                    _data_review_payload(
                        dataset.data_dir,
                        edition=dataset.edition,
                        model_dir=state.ml_model_dir_for_edition(dataset.edition),
                    )
                )
                return
            if parsed.path.startswith("/api/review-files/"):
                edition, filename = _review_file_request_parts(parsed.path, default_edition=state.rules_edition)
                try:
                    dataset = state.dataset_for_edition(edition)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                if not dataset.data_dir or filename not in _REVIEW_FILE_LABELS:
                    self._send_error(HTTPStatus.NOT_FOUND, "Unknown review file")
                    return
                self._send_file(dataset.data_dir / filename, _review_file_content_type(filename))
                return
            if parsed.path.startswith("/api/ml-model-files/"):
                edition, filename = _review_file_request_parts(parsed.path, default_edition=state.rules_edition)
                try:
                    state.dataset_for_edition(edition)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                if filename not in _MODEL_FILE_LABELS:
                    self._send_error(HTTPStatus.NOT_FOUND, "Unknown ML model file")
                    return
                self._send_file(state.ml_model_dir_for_edition(edition) / filename, _review_file_content_type(filename))
                return
            if parsed.path == "/api/units":
                query = parse_qs(parsed.query)
                try:
                    dataset = state.dataset_for_edition(query.get("edition", [""])[0] or None)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                text = query.get("q", [""])[0] or ""
                faction = query.get("faction", [""])[0] or ""
                limit = _query_limit(query.get("limit", ["300"])[0])
                units = _search_units(dataset.units.values(), text=text, faction=faction, limit=limit)
                self._send_json(
                    {
                        "units": [_unit_summary(unit) for unit in units],
                        "factions": _unit_factions(dataset.units.values()),
                        "edition": dataset.edition,
                    }
                )
                return
            if parsed.path == "/api/unit":
                query = parse_qs(parsed.query)
                try:
                    dataset = state.dataset_for_edition(query.get("edition", [""])[0] or None)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                try:
                    unit = dataset.require_unit(
                        query.get("name", [""])[0],
                        unit_id=query.get("id", [""])[0] or None,
                    )
                except KeyError:
                    self._send_error(HTTPStatus.NOT_FOUND, "Unknown unit")
                    return
                self._send_json({"unit": _unit_detail(unit)})
                return
            if parsed.path in {"", "/"}:
                self.path = "/index.html"
            return super().do_GET()

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/calculate":
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
                return

            try:
                payload = self._read_json()
                edition = _requested_rules_edition(payload.get("edition"), state=state)
                dataset = state.dataset_for_edition(edition)
                attacker = dataset.require_unit(
                    str(payload.get("attacker", "")),
                    unit_id=_optional_unit_id(payload.get("attacker_id")),
                )
                defender = dataset.require_unit(
                    str(payload.get("defender", "")),
                    unit_id=_optional_unit_id(payload.get("defender_id")),
                )
                mode = str(payload.get("mode", "ranged")).lower()
                if mode not in {"ranged", "melee"}:
                    raise ValueError("mode must be ranged or melee")
                outgoing_context, incoming_context = _contexts_from_payload(payload)
                outgoing_weapon = _optional_weapon_name(payload.get("outgoing_weapon"))
                incoming_weapon = _optional_weapon_name(payload.get("incoming_weapon"))
                outgoing_multiplier = _optional_positive_int(
                    payload.get("outgoing_multiplier", 1),
                    field_name="outgoing_multiplier",
                ) or 1
                incoming_multiplier = _optional_positive_int(
                    payload.get("incoming_multiplier", 1),
                    field_name="incoming_multiplier",
                ) or 1
            except KeyError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, f"Unknown unit: {exc.args[0]}")
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            try:
                result_payload = calculate_matchup(
                    attacker,
                    defender,
                    mode,
                    outgoing_context=outgoing_context,
                    incoming_context=incoming_context,
                    outgoing_weapon=outgoing_weapon,
                    incoming_weapon=incoming_weapon,
                    outgoing_multiplier=outgoing_multiplier,
                    incoming_multiplier=incoming_multiplier,
                    edition=edition,
                )
                ml_judgement = ml_judgement_from_result(
                    state.ml_model_for_edition(edition),
                    attacker=attacker,
                    defender=defender,
                    mode=mode,
                    result=result_payload,
                    edition=edition,
                )
                if ml_judgement:
                    result_payload["ml_judgement"] = ml_judgement
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(result_payload)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length)
            if not raw:
                return {}
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            return payload

        def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status=status)

        def _send_file(self, path: Path, content_type: str) -> None:
            try:
                body = path.read_bytes()
            except OSError:
                self._send_error(HTTPStatus.NOT_FOUND, "Review file not found")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.end_headers()
            self.wfile.write(body)

    return WarhammerHandler


def _contexts_from_payload(payload: Dict[str, Any]) -> tuple[EngagementContext, EngagementContext]:
    return api_payload_service.contexts_from_payload(payload)


def _context_from_payload(payload: Dict[str, Any]) -> EngagementContext:
    return api_payload_service.context_from_payload(payload)


def _optional_bool(value: Any, *, field_name: str) -> bool:
    return api_payload_service.optional_bool(value, field_name=field_name)


def _optional_positive_int(value: Any, *, field_name: str) -> Optional[int]:
    return api_payload_service.optional_positive_int(value, field_name=field_name)


def _optional_weapon_name(value: Any) -> Optional[str]:
    return api_payload_service.optional_weapon_name(value)


def _optional_unit_id(value: Any) -> Optional[str]:
    return api_payload_service.optional_unit_id(value)


def _rules_edition_from_metadata(metadata: Optional[Dict[str, Any]]) -> str:
    return edition_service.rules_edition_from_metadata(metadata, default=DEFAULT_EDITION)


def _supported_rules_editions_from_metadata(metadata: Optional[Dict[str, Any]]) -> list[str]:
    return edition_service.supported_rules_editions_from_metadata(metadata)


def _requested_rules_edition(value: Any, *, state: AppState) -> str:
    edition = str(value or state.rules_edition or "10e").strip() or "10e"
    dataset = state.dataset_for_edition(edition)
    if edition not in dataset.supported_rules_editions:
        supported = ", ".join(dataset.supported_rules_editions)
        raise ValueError(f"Edition {edition!r} is not available for this dataset; available editions: {supported}")
    get_ruleset(edition)
    return edition


def _review_file_request_parts(path: str, *, default_edition: str) -> tuple[str, str]:
    prefix = "/api/review-files/"
    remainder = path[len(prefix) :] if path.startswith(prefix) else path
    parts = [part for part in remainder.split("/") if part]
    if len(parts) >= 2:
        return parts[0], Path(parts[-1]).name
    return default_edition, Path(parts[-1] if parts else "").name


def _evaluate_unit_with_weapon_filter(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    *,
    context: EngagementContext,
    weapon_name: Optional[str],
    multiplier: int = 1,
    edition: str = "10e",
) -> UnitResult:
    return matchup_service.evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        mode,
        context=context,
        weapon_name=weapon_name,
        multiplier=multiplier,
        edition=edition,
    )


def _context_detail(context: EngagementContext) -> Dict[str, Any]:
    return matchup_service.context_detail(context)


def _query_limit(raw: Any) -> int:
    return api_payload_service.query_limit(raw)


def _unit_factions(units: Any) -> list[str]:
    return unit_search_service.unit_factions(units)


def _search_units(units: Any, *, text: str = "", faction: str = "", limit: int = 300) -> list[UnitProfile]:
    return unit_search_service.search_units(units, text=text, faction=faction, limit=limit)


def _unit_summary(unit: UnitProfile) -> Dict[str, Any]:
    return matchup_service.unit_summary(unit)


def _unit_detail(unit: UnitProfile) -> Dict[str, Any]:
    return matchup_service.unit_detail(unit)


def _weapon_detail(weapon: WeaponProfile) -> Dict[str, Any]:
    return matchup_service.weapon_detail(weapon)


def _unit_result(result: Any, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return matchup_service.unit_result(result, target=target)


_REVIEW_FILE_LABELS = {
    **data_review_service.REVIEW_FILE_LABELS,
}

_MODEL_FILE_LABELS = {
    **data_review_service.MODEL_FILE_LABELS,
}


def _data_review_payload(
    data_dir: Optional[Path],
    *,
    edition: str = DEFAULT_EDITION,
    model_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    return data_review_service.data_review_payload(data_dir, edition=edition, model_dir=model_dir)


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    return data_review_service.load_json_file(path)


def _load_text_file(path: Path) -> Optional[str]:
    return data_review_service.load_text_file(path)


def _source_info_from_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return data_review_service.source_info_from_metadata(metadata)


def _review_files(data_dir: Path, *, href_prefix: str) -> list[Dict[str, Any]]:
    return data_review_service.review_files(data_dir, href_prefix=href_prefix)


def _review_file_content_type(filename: str) -> str:
    return data_review_service.review_file_content_type(filename)


def _points_basis_models(unit: Optional[UnitProfile]) -> Optional[int]:
    return matchup_service.points_basis_models(unit)


def _points_per_model(unit: Optional[UnitProfile]) -> Optional[float]:
    return matchup_service.points_per_model(unit)


def _points_removed(unit: Optional[UnitProfile], models_destroyed: Optional[float]) -> Optional[float]:
    return matchup_service.points_removed(unit, models_destroyed)


def _as_float(value: Any) -> Optional[float]:
    return matchup_service._as_float(value)


def _matchup_judgement(
    attacker: UnitProfile,
    defender: UnitProfile,
    *,
    outgoing: Dict[str, Any],
    incoming: Dict[str, Any],
) -> Dict[str, Any]:
    return matchup_service.matchup_judgement(attacker, defender, outgoing=outgoing, incoming=incoming)


def _weapon_result(result: Any, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return matchup_service.weapon_result(result, target=target)


def run_server(*, host: str, port: int, csv_dir: Optional[Path], json_path: Optional[Path]) -> None:
    state = AppState(csv_dir=csv_dir, json_path=json_path)
    handler = create_handler(state)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Loaded {len(state.units)} units from {state.source}")
    print(f"Open http://{host}:{port}/")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Warhammer 40K calculator web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--csv-dir", type=Path)
    parser.add_argument("--data", type=Path, help="Path to units.json")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, csv_dir=args.csv_dir, json_path=args.data)


if __name__ == "__main__":
    main()
