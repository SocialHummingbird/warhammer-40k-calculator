from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .calculator import EngagementContext, UnitResult, evaluate_unit, evaluate_weapon, scale_unit_result
from .datasheet import _profile_priority, load_units_from_json
from .importers.csv_loader import load_units_from_directory
from .profiles import UnitProfile, WeaponProfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_JSON_PATH = PROJECT_ROOT / "units.json"
WEB_ROOT = PROJECT_ROOT / "web"


class AppState:
    def __init__(self, *, csv_dir: Optional[Path], json_path: Optional[Path]) -> None:
        if csv_dir:
            self.data_dir = csv_dir
            self.units = load_units_from_directory(csv_dir)
            self.source = str(csv_dir)
        elif json_path:
            self.data_dir = DEFAULT_CSV_DIR if DEFAULT_CSV_DIR.exists() else None
            self.units = load_units_from_json(json_path)
            self.source = str(json_path)
        elif DEFAULT_CSV_DIR.exists():
            self.data_dir = DEFAULT_CSV_DIR
            self.units = load_units_from_directory(DEFAULT_CSV_DIR)
            self.source = str(DEFAULT_CSV_DIR)
        else:
            self.data_dir = None
            self.units = load_units_from_json(DEFAULT_JSON_PATH)
            self.source = str(DEFAULT_JSON_PATH)

        self.metadata = _load_json_file(self.data_dir / "metadata.json") if self.data_dir else None
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
                    }
                )
                return
            if parsed.path == "/api/data-review":
                self._send_json(_data_review_payload(state.data_dir))
                return
            if parsed.path.startswith("/api/review-files/"):
                filename = Path(parsed.path).name
                if not state.data_dir or filename not in _REVIEW_FILE_LABELS:
                    self._send_error(HTTPStatus.NOT_FOUND, "Unknown review file")
                    return
                self._send_file(state.data_dir / filename, _review_file_content_type(filename))
                return
            if parsed.path == "/api/units":
                query = parse_qs(parsed.query)
                text = query.get("q", [""])[0] or ""
                faction = query.get("faction", [""])[0] or ""
                limit = _query_limit(query.get("limit", ["300"])[0])
                units = _search_units(state.units.values(), text=text, faction=faction, limit=limit)
                self._send_json(
                    {
                        "units": [_unit_summary(unit) for unit in units],
                        "factions": _unit_factions(state.units.values()),
                    }
                )
                return
            if parsed.path == "/api/unit":
                query = parse_qs(parsed.query)
                try:
                    unit = state.require_unit(
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
                attacker = state.require_unit(
                    str(payload.get("attacker", "")),
                    unit_id=_optional_unit_id(payload.get("attacker_id")),
                )
                defender = state.require_unit(
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
                outgoing = _evaluate_unit_with_weapon_filter(
                    attacker,
                    defender,
                    mode,
                    context=outgoing_context,
                    weapon_name=outgoing_weapon,
                    multiplier=outgoing_multiplier,
                )
                incoming = _evaluate_unit_with_weapon_filter(
                    defender,
                    attacker,
                    mode,
                    context=incoming_context,
                    weapon_name=incoming_weapon,
                    multiplier=incoming_multiplier,
                )
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            outgoing_payload = _unit_result(outgoing, target=defender)
            incoming_payload = _unit_result(incoming, target=attacker)
            self._send_json(
                {
                    "attacker": _unit_summary(attacker),
                    "defender": _unit_summary(defender),
                    "mode": mode,
                    "contexts": {
                        "outgoing": _context_detail(outgoing_context),
                        "incoming": _context_detail(incoming_context),
                    },
                    "weapon_filters": {
                        "outgoing": outgoing_weapon,
                        "incoming": incoming_weapon,
                    },
                    "multipliers": {
                        "outgoing": outgoing_multiplier,
                        "incoming": incoming_multiplier,
                    },
                    "outgoing": outgoing_payload,
                    "incoming": incoming_payload,
                    "judgement": _matchup_judgement(
                        attacker,
                        defender,
                        outgoing=outgoing_payload,
                        incoming=incoming_payload,
                    ),
                }
            )

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
    outgoing_payload = payload.get("outgoing_context") or payload.get("context") or {}
    incoming_payload = payload.get("incoming_context") or {}
    if not isinstance(outgoing_payload, dict) or not isinstance(incoming_payload, dict):
        raise ValueError("context values must be JSON objects")
    return _context_from_payload(outgoing_payload), _context_from_payload(incoming_payload)


def _context_from_payload(payload: Dict[str, Any]) -> EngagementContext:
    return EngagementContext(
        attacker_moved=_optional_bool(payload.get("attacker_moved", False), field_name="attacker_moved"),
        attacker_advanced=_optional_bool(payload.get("attacker_advanced", False), field_name="attacker_advanced"),
        target_within_half_range=_optional_bool(
            payload.get("target_within_half_range", False),
            field_name="target_within_half_range",
        ),
        target_in_cover=_optional_bool(payload.get("target_in_cover", False), field_name="target_in_cover"),
        target_model_count=_optional_positive_int(payload.get("target_model_count"), field_name="target_model_count"),
    )


def _optional_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError(f"{field_name} must be true or false")
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    raise ValueError(f"{field_name} must be true or false")


def _optional_positive_int(value: Any, *, field_name: str) -> Optional[int]:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _optional_weapon_name(value: Any) -> Optional[str]:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError("weapon filters must be strings")
    value = value.strip()
    if not value or value.casefold() == "__all__":
        return None
    return value


def _optional_unit_id(value: Any) -> Optional[str]:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError("unit ids must be strings")
    value = value.strip()
    return value or None


def _evaluate_unit_with_weapon_filter(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    *,
    context: EngagementContext,
    weapon_name: Optional[str],
    multiplier: int = 1,
) -> UnitResult:
    if not weapon_name:
        result = evaluate_unit(attacker, defender, mode, context=context)  # type: ignore[arg-type]
        return scale_unit_result(result, multiplier)

    matches = [
        weapon
        for weapon in attacker.weapons
        if weapon.type == mode and weapon.name.casefold() == weapon_name.casefold()
    ]
    if not matches:
        raise ValueError(f"{attacker.name} has no {mode} weapon named {weapon_name}")
    result = UnitResult(
        unit=attacker,
        weapons=[evaluate_weapon(attacker, defender, weapon, context=context) for weapon in matches],
        target_wounds=defender.wounds,
    )
    return scale_unit_result(result, multiplier)


def _context_detail(context: EngagementContext) -> Dict[str, Any]:
    return {
        "attacker_moved": context.attacker_moved,
        "attacker_advanced": context.attacker_advanced,
        "target_within_half_range": context.target_within_half_range,
        "target_in_cover": context.target_in_cover,
        "target_model_count": context.target_model_count,
    }


def _query_limit(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 300
    return max(1, min(1000, value))


def _unit_factions(units: Any) -> list[str]:
    return sorted({unit.faction for unit in units if unit.faction}, key=str.casefold)


def _search_units(units: Any, *, text: str = "", faction: str = "", limit: int = 300) -> list[UnitProfile]:
    needle = (text or "").casefold().strip()
    faction_key = (faction or "").casefold().strip()
    matches = []
    for unit in sorted(units, key=lambda item: item.name.casefold()):
        if faction_key and (unit.faction or "").casefold() != faction_key:
            continue
        if needle:
            searchable = " ".join([unit.name, unit.faction or "", *unit.keywords]).casefold()
            if needle not in searchable:
                continue
        matches.append(unit)
        if len(matches) >= limit:
            break
    return matches


def _unit_summary(unit: UnitProfile) -> Dict[str, Any]:
    return {
        "id": unit.unit_id,
        "name": unit.name,
        "faction": unit.faction,
        "toughness": unit.toughness,
        "save": unit.save_label,
        "wounds": unit.wounds,
        "points": unit.points,
        "models_min": unit.models_min,
        "models_max": unit.models_max,
        "source_file": unit.source_file,
        "keywords": unit.keywords,
    }


def _unit_detail(unit: UnitProfile) -> Dict[str, Any]:
    payload = _unit_summary(unit)
    payload["weapons"] = [_weapon_detail(weapon) for weapon in unit.weapons]
    payload["abilities"] = [
        {"name": ability.name, "text": ability.text, "source_file": ability.source_file}
        for ability in unit.abilities
    ]
    return payload


def _weapon_detail(weapon: WeaponProfile) -> Dict[str, Any]:
    return {
        "name": weapon.name,
        "type": weapon.type,
        "attacks": weapon.attacks.label,
        "skill": weapon.skill_label,
        "strength": weapon.strength_label or str(weapon.strength),
        "ap": weapon.ap,
        "damage": weapon.damage.label,
        "keywords": weapon.keywords,
        "source_file": weapon.source_file,
    }


def _unit_result(result: Any, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return {
        "total_damage": result.total_damage,
        "total_unsaved_wounds": result.total_unsaved_wounds,
        "expected_models_destroyed": result.expected_models_destroyed,
        "estimated_points_removed": _points_removed(target, result.expected_models_destroyed),
        "points_per_model": _points_per_model(target),
        "feel_no_pain_applied": result.feel_no_pain_applied,
        "weapons": [_weapon_result(weapon_result, target=target) for weapon_result in result.weapons],
    }


_REVIEW_FILE_LABELS = {
    "weapon_profile_review.csv": "Weapon profile review CSV",
    "suspicious_weapon_review.csv": "Suspicious weapon review CSV",
    "ability_profile_review.csv": "Ability profile review CSV",
    "ability_modifier_review.csv": "Ability modifier review CSV",
    "unit_variant_review.csv": "Duplicate unit name review CSV",
    "unit_weapon_coverage_review.csv": "Unit weapon coverage review CSV",
    "loadout_review.csv": "Loadout review CSV",
    "source_catalogue_review.csv": "Source catalogue review CSV",
    "schema_review.csv": "Schema review CSV",
    "artifact_manifest.json": "Artifact manifest JSON",
    "profile_review.md": "Profile review summary",
    "update_report.md": "Update report",
}


def _data_review_payload(data_dir: Optional[Path]) -> Dict[str, Any]:
    if not data_dir:
        return {
            "audit_report": None,
            "import_diff": None,
            "metadata": None,
            "update_report": None,
            "profile_review": None,
            "review_files": [],
        }
    return {
        "audit_report": _load_json_file(data_dir / "audit_report.json"),
        "import_diff": _load_json_file(data_dir / "import_diff.json"),
        "metadata": _load_json_file(data_dir / "metadata.json"),
        "update_report": _load_text_file(data_dir / "update_report.md"),
        "profile_review": _load_text_file(data_dir / "profile_review.md"),
        "review_files": _review_files(data_dir, href_prefix="/api/review-files/"),
    }


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_text_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return content or None


def _source_info_from_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    revisions = metadata.get("source_revisions")
    source = revisions[0] if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict) else {}
    commit = source.get("commit") or ""
    return {
        "commit": commit,
        "commit_short": str(commit)[:12] if commit else "",
        "branch": source.get("branch") or metadata.get("github_ref") or "",
        "remote_origin": source.get("remote_origin") or metadata.get("github_repo") or "",
        "dirty": bool(source.get("dirty")),
        "generated_at": metadata.get("generated_at") or "",
        "rules_edition": metadata.get("rules_edition") or "10e",
        "supported_rules_editions": metadata.get("supported_rules_editions") or ["10e"],
    }


def _review_files(data_dir: Path, *, href_prefix: str) -> list[Dict[str, Any]]:
    files = []
    for filename, label in _REVIEW_FILE_LABELS.items():
        path = data_dir / filename
        if not path.exists():
            continue
        files.append(
            {
                "label": label,
                "filename": filename,
                "href": f"{href_prefix}{filename}",
                "bytes": path.stat().st_size,
            }
        )
    return files


def _review_file_content_type(filename: str) -> str:
    if filename.endswith(".csv"):
        return "text/csv; charset=utf-8"
    if filename.endswith(".json"):
        return "application/json; charset=utf-8"
    return "text/markdown; charset=utf-8"


def _points_basis_models(unit: Optional[UnitProfile]) -> Optional[int]:
    if unit is None:
        return None
    if unit.models_min and unit.models_max:
        return max(1, round((unit.models_min + unit.models_max) / 2))
    if unit.models_max:
        return max(1, unit.models_max)
    if unit.models_min:
        return max(1, unit.models_min)
    return 1


def _points_per_model(unit: Optional[UnitProfile]) -> Optional[float]:
    models = _points_basis_models(unit)
    if unit is None or not unit.points or not models:
        return None
    return unit.points / models


def _points_removed(unit: Optional[UnitProfile], models_destroyed: Optional[float]) -> Optional[float]:
    ppm = _points_per_model(unit)
    if ppm is None or models_destroyed is None:
        return None
    return models_destroyed * ppm


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _matchup_judgement(
    attacker: UnitProfile,
    defender: UnitProfile,
    *,
    outgoing: Dict[str, Any],
    incoming: Dict[str, Any],
) -> Dict[str, Any]:
    outgoing_points = _as_float(outgoing.get("estimated_points_removed"))
    incoming_points = _as_float(incoming.get("estimated_points_removed"))
    if outgoing_points is not None and incoming_points is not None:
        outgoing_score = outgoing_points
        incoming_score = incoming_points
        basis = "points_removed"
        basis_label = "estimated points removed"
    else:
        outgoing_score = _as_float(outgoing.get("total_damage")) or 0.0
        incoming_score = _as_float(incoming.get("total_damage")) or 0.0
        basis = "damage"
        basis_label = "expected damage"

    delta = outgoing_score - incoming_score
    total = max(outgoing_score + incoming_score, 0.01)
    edge = abs(delta) / total
    confidence = "narrow"
    if edge >= 0.45:
        confidence = "decisive"
    elif edge >= 0.22:
        confidence = "clear"

    close = edge < 0.08
    winner = attacker.name if delta >= 0 else defender.name
    loser_score = incoming_score if delta >= 0 else outgoing_score
    winner_score = outgoing_score if delta >= 0 else incoming_score
    damage_context = (
        f" Damage context: {attacker.name} deals {(_as_float(outgoing.get('total_damage')) or 0.0):.2f} "
        f"and {defender.name} returns {(_as_float(incoming.get('total_damage')) or 0.0):.2f}."
    )
    points_context = (
        f" Points context: {attacker.name} is {attacker.points} pts and {defender.name} is {defender.points} pts."
        if attacker.points and defender.points
        else ""
    )

    if close:
        title = "AI judgement: too close to call"
        body = (
            f"The exchange is nearly even on {basis_label}: {attacker.name} scores {outgoing_score:.2f} "
            f"and {defender.name} returns {incoming_score:.2f}."
        )
    elif basis == "points_removed":
        title = f"AI judgement: {winner} favored ({confidence})"
        body = (
            f"{winner} is favored on estimated points removed, scoring {winner_score:.2f} while giving up "
            f"{loser_score:.2f} in return."
        )
    else:
        title = f"AI judgement: {winner} favored ({confidence})"
        body = (
            f"{winner} is projected to deal {winner_score:.2f} damage while taking {loser_score:.2f} "
            "in the return strike."
        )

    return {
        "title": title,
        "body": f"{body}{damage_context if basis == 'points_removed' else points_context}",
        "winner": None if close else winner,
        "confidence": "close" if close else confidence,
        "basis": basis,
        "outgoing_score": outgoing_score,
        "incoming_score": incoming_score,
        "edge": edge,
    }


def _weapon_result(result: Any, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return {
        "weapon": _weapon_detail(result.weapon),
        "attacks": result.attacks,
        "hits": result.hits,
        "wounds": result.wounds,
        "unsaved_wounds": result.unsaved_wounds,
        "expected_damage": result.expected_damage,
        "expected_models_destroyed": result.expected_models_destroyed,
        "estimated_points_removed": _points_removed(target, result.expected_models_destroyed),
        "hit_probability": result.hit_probability,
        "wound_probability": result.wound_probability,
        "failed_save_probability": result.failed_save_probability,
        "wound_roll": result.wound_roll_label,
        "save": result.save_used_label,
        "notes": result.ability_notes,
    }


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
