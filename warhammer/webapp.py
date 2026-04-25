from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .calculator import EngagementContext, evaluate_unit
from .datasheet import load_units_from_csv, load_units_from_json
from .profiles import UnitProfile, WeaponProfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_JSON_PATH = PROJECT_ROOT / "units.json"
WEB_ROOT = PROJECT_ROOT / "web"


class AppState:
    def __init__(self, *, csv_dir: Optional[Path], json_path: Optional[Path]) -> None:
        if csv_dir:
            self.data_dir = csv_dir
            self.units = load_units_from_csv(csv_dir)
            self.source = str(csv_dir)
        elif json_path:
            self.data_dir = DEFAULT_CSV_DIR if DEFAULT_CSV_DIR.exists() else None
            self.units = load_units_from_json(json_path)
            self.source = str(json_path)
        elif DEFAULT_CSV_DIR.exists():
            self.data_dir = DEFAULT_CSV_DIR
            self.units = load_units_from_csv(DEFAULT_CSV_DIR)
            self.source = str(DEFAULT_CSV_DIR)
        else:
            self.data_dir = None
            self.units = load_units_from_json(DEFAULT_JSON_PATH)
            self.source = str(DEFAULT_JSON_PATH)

        self.units_by_name = {unit.name.casefold(): unit for unit in self.units.values()}

    def require_unit(self, name: str) -> UnitProfile:
        key = (name or "").casefold()
        unit = self.units_by_name.get(key)
        if unit is None:
            raise KeyError(name)
        return unit


def create_handler(state: AppState) -> type[SimpleHTTPRequestHandler]:
    class WarhammerHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json({"ok": True, "source": state.source, "units": len(state.units)})
                return
            if parsed.path == "/api/data-review":
                self._send_json(_data_review_payload(state.data_dir))
                return
            if parsed.path == "/api/units":
                query = parse_qs(parsed.query)
                text = query.get("q", [""])[0] or ""
                faction = query.get("faction", [""])[0] or ""
                limit = _query_limit(query.get("limit", ["300"])[0])
                units = _search_units(state.units_by_name.values(), text=text, faction=faction, limit=limit)
                self._send_json(
                    {
                        "units": [_unit_summary(unit) for unit in units],
                        "factions": _unit_factions(state.units_by_name.values()),
                    }
                )
                return
            if parsed.path == "/api/unit":
                query = parse_qs(parsed.query)
                try:
                    unit = state.require_unit(query.get("name", [""])[0])
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
                attacker = state.require_unit(str(payload.get("attacker", "")))
                defender = state.require_unit(str(payload.get("defender", "")))
                mode = str(payload.get("mode", "ranged")).lower()
                if mode not in {"ranged", "melee"}:
                    raise ValueError("mode must be ranged or melee")
                outgoing_context, incoming_context = _contexts_from_payload(payload)
            except KeyError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, f"Unknown unit: {exc.args[0]}")
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            outgoing = evaluate_unit(attacker, defender, mode, context=outgoing_context)
            incoming = evaluate_unit(defender, attacker, mode, context=incoming_context)
            self._send_json(
                {
                    "attacker": _unit_summary(attacker),
                    "defender": _unit_summary(defender),
                    "mode": mode,
                    "contexts": {
                        "outgoing": _context_detail(outgoing_context),
                        "incoming": _context_detail(incoming_context),
                    },
                    "outgoing": _unit_result(outgoing),
                    "incoming": _unit_result(incoming),
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
        "name": unit.name,
        "faction": unit.faction,
        "toughness": unit.toughness,
        "save": unit.save_label,
        "wounds": unit.wounds,
        "points": unit.points,
        "models_min": unit.models_min,
        "models_max": unit.models_max,
        "keywords": unit.keywords,
    }


def _unit_detail(unit: UnitProfile) -> Dict[str, Any]:
    payload = _unit_summary(unit)
    payload["weapons"] = [_weapon_detail(weapon) for weapon in unit.weapons]
    payload["abilities"] = [{"name": ability.name, "text": ability.text} for ability in unit.abilities]
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
    }


def _unit_result(result: Any) -> Dict[str, Any]:
    return {
        "total_damage": result.total_damage,
        "total_unsaved_wounds": result.total_unsaved_wounds,
        "expected_models_destroyed": result.expected_models_destroyed,
        "feel_no_pain_applied": result.feel_no_pain_applied,
        "weapons": [_weapon_result(weapon_result) for weapon_result in result.weapons],
    }


def _data_review_payload(data_dir: Optional[Path]) -> Dict[str, Any]:
    if not data_dir:
        return {"audit_report": None, "import_diff": None, "metadata": None}
    return {
        "audit_report": _load_json_file(data_dir / "audit_report.json"),
        "import_diff": _load_json_file(data_dir / "import_diff.json"),
        "metadata": _load_json_file(data_dir / "metadata.json"),
    }


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _weapon_result(result: Any) -> Dict[str, Any]:
    return {
        "weapon": _weapon_detail(result.weapon),
        "attacks": result.attacks,
        "hits": result.hits,
        "wounds": result.wounds,
        "unsaved_wounds": result.unsaved_wounds,
        "expected_damage": result.expected_damage,
        "expected_models_destroyed": result.expected_models_destroyed,
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
