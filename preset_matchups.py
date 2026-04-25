from __future__ import annotations

import argparse
import re
import sys

from warhammer import cli_core as LEGACY
from warhammer.formatting import format_three_decimal_text, abbreviate_weapon_keyword, normalise_weapon_label
from pathlib import Path
from typing import Dict, List, Optional
from ai_clean import resolve_api_key

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from warhammer.datasheet import load_units_from_csv as load_units_from_csv_local, load_units_from_json as load_units_from_json_local

DEFAULT_CSV_SEARCH = [Path("data/latest"), Path("data/test"), Path("data")]
DEFAULT_JSON_CANDIDATES = [Path("units.json")]


DEFAULT_REALISTIC_SCENARIO = (
    "Assume the units begin roughly 18 inches apart with line of sight. "
    "Each side may decide whether to advance to close distance or hold position before engaging. "
    "Neither side willingly retreats once combat is joined, but comment on whether kiting or staying at range would improve the outcome for either unit. "
    "Start the engagement at the furthest range of any weapon either unit carries."
)



def _safe_output(text: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


_CAPTURED_LINES: Optional[List[str]] = None


def _begin_capture() -> None:
    global _CAPTURED_LINES
    _CAPTURED_LINES = []


def _capture_line(line: str) -> None:
    if _CAPTURED_LINES is not None:
        _CAPTURED_LINES.append(line)


def _finalise_capture() -> str:
    global _CAPTURED_LINES
    lines = _CAPTURED_LINES or []
    _CAPTURED_LINES = None
    return "\n".join(lines)



def _format_move_value(unit) -> str:
    move_value = _coerce_float(getattr(unit, 'move', None))
    if move_value is None:
        return 'unknown'
    return _format_move_inches(move_value)


def _movement_charge_edge(attacker, defender) -> Optional[str]:
    a_move = getattr(attacker, 'move', None)
    d_move = getattr(defender, 'move', None)
    edge = None
    if isinstance(a_move, (int, float)) and isinstance(d_move, (int, float)):
        if a_move > d_move + 0.1:
            edge = attacker.name
        elif d_move > a_move + 0.1:
            edge = defender.name
    a_ac = getattr(attacker, 'can_advance_and_charge', False)
    d_ac = getattr(defender, 'can_advance_and_charge', False)
    if edge is None:
        if a_ac and not d_ac:
            edge = attacker.name
        elif d_ac and not a_ac:
            edge = defender.name
    return edge


def _describe_movement(attacker, defender) -> str:
    parts = []
    parts.append(f"{attacker.name}: Move {_format_move_value(attacker)}, Advance+Charge={'yes' if getattr(attacker, 'can_advance_and_charge', False) else 'no'}")
    parts.append(f"{defender.name}: Move {_format_move_value(defender)}, Advance+Charge={'yes' if getattr(defender, 'can_advance_and_charge', False) else 'no'}")
    edge = _movement_charge_edge(attacker, defender)
    if edge:
        parts.append(f"Charge edge: {edge}")
    return "Movement: " + "; ".join(parts)

FAST_MOVE_THRESHOLD = 10.0


def _coerce_float(value: object) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    try:
        cleaned = str(value).strip().replace('"', '').replace("'", '')
    except Exception:
        return None
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _format_move_inches(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return f'{int(round(value))}"'
    return f'{value:.1f}"'


def _speed_tags_for_unit(unit) -> List[str]:
    tags: List[str] = []
    move_value = _coerce_float(getattr(unit, 'move', None))
    if move_value is not None and move_value >= FAST_MOVE_THRESHOLD:
        tags.append(f"Move {_format_move_inches(move_value)}")
    if getattr(unit, 'can_advance_and_charge', False):
        tags.append('Advance+Charge')
    return tags


FAIR_SINGLE_MODEL_KEYWORDS = {
    "infantry",
    "vehicle",
    "monster",
    "character",
    "walker",
    "titanic",
    "beast",
    "cavalry",
    "daemon",
    "psyker",
    "bike",
    "biker",
}


def _unit_is_single_model(unit) -> bool:
    models_min = getattr(unit, "models_min", None)
    models_max = getattr(unit, "models_max", None)
    if models_min is not None and models_min != 1:
        return False
    if models_max is not None and models_max != 1:
        return False
    return True


def _primary_role_keywords(unit) -> set[str]:
    keywords = getattr(unit, "keywords", []) or []
    lowered = {str(keyword).strip().lower() for keyword in keywords}
    return {kw for kw in lowered if kw in FAIR_SINGLE_MODEL_KEYWORDS}


def _unit_points(unit) -> Optional[float]:
    value = getattr(unit, "points", None)
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return numeric

def _unit_supports_weapon_mode(unit, weapon_mode: str) -> bool:
    weapons = getattr(unit, 'weapons', None)
    target_mode = (weapon_mode or 'all').lower()
    if not weapons:
        return target_mode == 'all'
    if target_mode == 'all':
        return any(getattr(w, 'type', None) for w in weapons)
    for weapon in weapons:
        if str(getattr(weapon, 'type', '')).lower() == target_mode:
            return True
    return False



def _select_fair_random_pair(
    units: Dict[str, object],
    *,
    required_modes: tuple[str, ...],
    max_point_delta: Optional[float],
) -> tuple[object, object]:
    mode_checks = []
    for mode in required_modes:
        lower = mode.lower()
        if lower == 'all':
            mode_checks.extend(['melee', 'ranged'])
        else:
            mode_checks.append(lower)
    if not mode_checks:
        mode_checks = ['all']

    candidates = [
        unit
        for unit in units.values()
        if _unit_is_single_model(unit)
        and all(_unit_supports_weapon_mode(unit, mode) for mode in mode_checks)
    ]
    if not candidates:
        raise SystemExit("No single-model units available for fair duel selection.")

    rng = LEGACY.random
    rng.shuffle(candidates)

    delta = max_point_delta if (max_point_delta is not None and max_point_delta >= 0) else None

    for attacker in candidates:
        attacker_roles = _primary_role_keywords(attacker)
        if not attacker_roles:
            continue
        attacker_points = _unit_points(attacker)
        defenders: List[object] = []
        for defender in candidates:
            if defender is attacker:
                continue
            defender_roles = _primary_role_keywords(defender)
            if not defender_roles or not (attacker_roles & defender_roles):
                continue
            if delta is not None:
                defender_points = _unit_points(defender)
                if attacker_points is None or defender_points is None:
                    continue
                if abs(attacker_points - defender_points) > delta:
                    continue
            defenders.append(defender)
        if defenders:
            return attacker, rng.choice(defenders)

    raise SystemExit(
        "Unable to find a matching opponent with shared keywords and points within the specified delta. "
        "Relax the filters or provide explicit units."
    )




def _collect_fast_units(units: Dict[str, object], presets: List[str]) -> Dict[str, List[str]]:
    highlights: Dict[str, List[str]] = {}
    for preset in presets:
        entries: List[str] = []
        for defender_name in LEGACY.TARGET_PRESETS.get(preset, []):
            unit = units.get(defender_name)
            if not unit:
                continue
            tags = _speed_tags_for_unit(unit)
            if tags:
                entries.append(f"{defender_name} ({', '.join(tags)})")
        if entries:
            highlights[preset] = entries
    return highlights


def _summarise_with_ai(summary_text: str, model: str, scenario: Optional[str] = None) -> str:
    if not summary_text.strip():
        return "No matchup tables were produced to summarise."

    payload = summary_text
    if scenario:
        payload = payload + "\n\nScenario context: " + scenario

    if OpenAI is None:  # pragma: no cover - optional dependency
        raise SystemExit("The openai package is not installed. Run `pip install openai`.")

    api_key = resolve_api_key()
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You analyse Warhammer 40K matchup tables. "
                    "Summarise the attacker's performance against each preset defender in two or three concise bullet points. "
                    "Call out standout strengths, notable weaknesses, and any interesting weapon interactions. "
                    "Avoid repeating the raw numbers; focus on interpretation."
                ),
            },
            {
                "role": "user",
                "content": payload,
            },
        ],
    )
    return response.output_text  # type: ignore[return-value]





def _load_cli_core():
    return LEGACY


LEGACY = _load_cli_core()

# Patch data-loading helpers to reuse the Python implementations that deduplicate
# duplicate unit names without printing long warning lists.
if hasattr(LEGACY, "_load_units_from_csv"):
    LEGACY._load_units_from_csv = load_units_from_csv_local  # type: ignore[attr-defined]
if hasattr(LEGACY, "_load_units_from_json"):
    LEGACY._load_units_from_json = load_units_from_json_local  # type: ignore[attr-defined]

# Adjust defender labels to include explicit Unit Stats / Points rows for better
# readability without widening the tables.
if hasattr(LEGACY, "_format_unit_defense_label"):
    _original_format_unit_defense_label = LEGACY._format_unit_defense_label  # type: ignore[attr-defined]

    def _wrapped_format_unit_defense_label(unit, ppm_basis, ppm_info=None):
        return _original_format_unit_defense_label(unit, ppm_basis, ppm_info)

    LEGACY._format_unit_defense_label = _wrapped_format_unit_defense_label  # type: ignore[attr-defined]

if hasattr(LEGACY, "_build_weapon_table"):
    _original_build_weapon_table = LEGACY._build_weapon_table  # type: ignore[attr-defined]

    def _wrapped_build_weapon_table(attacker, targets, weapon_mode, ppm_basis):
        table = _original_build_weapon_table(attacker, targets, weapon_mode, ppm_basis)
        if not table:
            return table

        name_header = list(table.get("name_header", []))
        stats_header = list(table.get("stats_header", []))
        rows = [list(row) for row in table.get("rows", [])]
        if len(name_header) > 1 and name_header[1] == "Weapon Profile":
            table["rows"] = rows
            return table
        if not name_header or len(stats_header) != len(name_header):
            table["rows"] = rows
            return table

        def _split_cells(label: str) -> tuple[str, str]:
            if " (" in label and label.endswith(")"):
                stats_text, meta_text = label.split(" (", 1)
                return stats_text.strip(), meta_text[:-1].strip()
            return label.strip(), ""

        def _format_points(meta: str) -> str:
            if not meta:
                return ""
            parts: list[str] = []
            for chunk in meta.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                lower = chunk.lower()
                if lower.startswith("models "):
                    parts.append("M: " + chunk.split(" ", 1)[1])
                elif lower.startswith("ppm"):
                    if ":" in chunk:
                        value = chunk.split(":", 1)[1].strip()
                    else:
                        value = chunk.partition(" ")[2].strip()
                    parts.append("PPM: " + value)
                else:
                    parts.append(chunk)
            return "; ".join(parts)

        def _format_weapon_profile(weapon) -> str:
            attack_label = str(getattr(weapon.attacks, "label", getattr(weapon.attacks, "name", weapon.attacks)))
            skill_label = weapon.skill_label or ("Auto" if getattr(weapon, "auto_hits", False) else "N/A")
            type_raw = (getattr(weapon, "type", "") or "").lower()
            if type_raw == "melee":
                type_label = "[M]"
            elif type_raw == "ranged":
                type_label = "[R]"
            elif type_raw:
                type_label = f"[{type_raw[:1].upper()}]"
            else:
                type_label = ""

            attack_segment = f"A{attack_label}"
            if type_label:
                attack_segment = f"{type_label} {attack_segment}"

            strength_segment = f"S{weapon.strength}"
            ap_segment = f"AP{weapon.ap}"
            damage_label = str(getattr(weapon.damage, "label", weapon.damage))
            if damage_label.upper().startswith("D"):
                damage_segment = damage_label
            else:
                damage_segment = f"D{damage_label}"

            parts = [
                attack_segment,
                skill_label,
                strength_segment,
                ap_segment,
                damage_segment,
            ]
            profile_text = " | ".join(parts)

            extras: list[str] = []
            extras.extend(getattr(weapon, "keywords", []) or [])
            if getattr(weapon, "lethal_hits", False) and "Lethal Hits" not in extras:
                extras.append("Lethal Hits")
            if getattr(weapon, "sustained_hits", 0):
                extras.append(f"Sustained Hits {weapon.sustained_hits}")
            if getattr(weapon, "devastating_wounds", False) and "Devastating Wounds" not in extras:
                extras.append("Devastating Wounds")
            if getattr(weapon, "melta", None) is not None:
                extras.append(f"Melta {weapon.melta}")
            if getattr(weapon, "rapid_fire", None) is not None:
                extras.append(f"Rapid Fire {weapon.rapid_fire}")
            for target, roll in getattr(weapon, "anti_rules", []) or []:
                extras.append(f"Anti-{target} {roll}+")
            if getattr(weapon, "hit_modifier", 0):
                extras.append(f"Hit mod {weapon.hit_modifier:+d}")
            if getattr(weapon, "wound_modifier", 0):
                extras.append(f"Wound mod {weapon.wound_modifier:+d}")
            if getattr(weapon, "reroll_hits", "none") not in {"", "none"}:
                extras.append(f"Reroll hits: {weapon.reroll_hits}")
            if getattr(weapon, "reroll_wounds", "none") not in {"", "none"}:
                extras.append(f"Reroll wounds: {weapon.reroll_wounds}")

            seen_extras: set[str] = set()
            abbr_extras: list[str] = []
            for extra in extras:
                abbr = abbreviate_weapon_keyword(extra)
                if not abbr or abbr in seen_extras:
                    continue
                seen_extras.add(abbr)
                abbr_extras.append(abbr)

            if abbr_extras:
                profile_text += f" ({'; '.join(abbr_extras)})"
            return profile_text
        attacker_profile = table.get("attacker")
        weapon_lookup: dict[str, list] = {}
        if attacker_profile is not None:
            for weapon in getattr(attacker_profile, "weapons", []) or []:
                raw_name = str(weapon.name)
                normalised_name = normalise_weapon_label(raw_name)
                weapon_lookup.setdefault(raw_name, []).append(weapon)
                if normalised_name != raw_name:
                    weapon_lookup.setdefault(normalised_name, []).append(weapon)

        reformatted_stats: list[str] = ["Unit Stats"]
        points_row: list[str] = ["Points"]
        for cell in stats_header[1:]:
            stats_text, meta_text = _split_cells(cell)
            reformatted_stats.append(stats_text)
            points_row.append(_format_points(meta_text))

        if rows:
            name_header[0] = "Weapon"
            name_header.insert(1, "Weapon Profile")
            reformatted_stats[0] = ""
            reformatted_stats.insert(1, "A / Skill / S / AP / D")
            points_row.insert(1, "")

            updated_rows = []
            for row in rows:
                label = normalise_weapon_label(str(row[0]))
                candidates = weapon_lookup.get(label)
                if not candidates and " (" in label:
                    candidates = weapon_lookup.get(label.split(" (", 1)[0])
                profile_text = _format_weapon_profile(candidates[0]) if candidates else ""
                updated_rows.append([label, profile_text] + row[1:])
            rows = updated_rows

        table["name_header"] = name_header
        table["stats_header"] = reformatted_stats
        table["_extra_header_rows"] = [points_row]
        table["rows"] = rows
        return table


    LEGACY._build_weapon_table = _wrapped_build_weapon_table  # type: ignore[attr-defined]

if hasattr(LEGACY, "_print_attacker_summary"):
    _original_print_attacker_summary = LEGACY._print_attacker_summary  # type: ignore[attr-defined]

    def _wrapped_print_attacker_summary(attacker, weapon_mode, prefix=""):
        label = f"{prefix}: " if prefix else ""
        _capture_line(f"{label}Attacker summary for {attacker.name} ({weapon_mode})")
        return _original_print_attacker_summary(attacker, weapon_mode, prefix=prefix)

    LEGACY._print_attacker_summary = _wrapped_print_attacker_summary  # type: ignore[attr-defined]

if hasattr(LEGACY, "_print_weapon_table_data"):
    _original_print_weapon_table_data = LEGACY._print_weapon_table_data  # type: ignore[attr-defined]

    def _wrapped_print_weapon_table_data(table):
        name_header = [str(value) for value in table.get("name_header", [])]
        stats_header = [str(value) for value in table.get("stats_header", [])]
        extra_header_rows = [
            [str(value) for value in row]
            for row in table.get("_extra_header_rows", [])
        ]
        rows = [[str(value) for value in row] for row in table.get("rows", [])]
        note = str(table.get("note", ""))

        col_count = len(name_header)
        if col_count == 0 or len(stats_header) != col_count:
            return _original_print_weapon_table_data(table)

        def _pad(row: list[str]) -> list[str]:
            if len(row) < col_count:
                row = row + [""] * (col_count - len(row))
            elif len(row) > col_count:
                row = row[:col_count]
            return row

        stats_header = _pad(stats_header)
        extra_header_rows = [_pad(row) for row in extra_header_rows]
        rows = [_pad(row) for row in rows]

        name_header = [format_three_decimal_text(value) for value in name_header]
        stats_header = [format_three_decimal_text(value) for value in stats_header]
        extra_header_rows = [
            [format_three_decimal_text(value) for value in row]
            for row in extra_header_rows
        ]
        rows = [
            [format_three_decimal_text(value) for value in row]
            for row in rows
        ]
        note = format_three_decimal_text(note)

        col_widths = [len(value) for value in name_header]

        def _update_widths(row: list[str]) -> None:
            for idx, value in enumerate(row):
                col_widths[idx] = max(col_widths[idx], len(value))

        _update_widths(stats_header)
        for header in extra_header_rows:
            _update_widths(header)
        for row in rows:
            _update_widths(row)

        def _format_row(values: list[str]) -> str:
            formatted: list[str] = []
            for idx, value in enumerate(values):
                if idx == 0:
                    formatted.append(value.ljust(col_widths[idx]))
                else:
                    formatted.append(value.rjust(col_widths[idx]))
            return " | ".join(formatted)

        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        def _safe_print(line: str) -> None:
            _capture_line(line)
            print(line.encode(encoding, errors="replace").decode(encoding))

        _safe_print(_format_row(name_header))
        _safe_print(_format_row(stats_header))
        for header in extra_header_rows:
            _safe_print(_format_row(header))

        separator = "-+-".join("-" * width for width in col_widths)
        _safe_print(separator)
        for row in rows:
            _safe_print(_format_row(row))
        if note:
            _capture_line("")
            print()
            _safe_print(note)

    LEGACY._print_weapon_table_data = _wrapped_print_weapon_table_data  # type: ignore[attr-defined]








def _list_presets() -> None:
    print("Preset defender tables:")
    for preset in LEGACY.PRESET_ORDER:
        defenders = ", ".join(LEGACY.TARGET_PRESETS[preset])
        print(f"  {preset}: {defenders}")
    extra = sorted(set(LEGACY.TARGET_PRESETS.keys()) - set(LEGACY.PRESET_ORDER))
    if extra:
        print("\nAdditional preset aliases:")
        for preset in extra:
            defenders = ", ".join(LEGACY.TARGET_PRESETS[preset])
            print(f"  {preset}: {defenders}")


def _normalise_presets(requested: Optional[List[str]]) -> List[str]:
    if not requested:
        return list(LEGACY.PRESET_ORDER)
    lookup = {name.casefold(): name for name in LEGACY.TARGET_PRESETS}
    resolved: List[str] = []
    missing: List[str] = []
    for raw in requested:
        key = raw.casefold()
        match = lookup.get(key)
        if not match:
            missing.append(raw)
            continue
        if match not in resolved:
            resolved.append(match)
    if missing:
        raise SystemExit(
            f"Unknown preset name(s): {', '.join(missing)}. Use --list-presets to see available tables."
        )
    return resolved


def _load_units_from_sources(csv_dir: Optional[Path], data_path: Optional[Path], prefer_faction: Optional[str]) -> Dict[str, LEGACY.UnitProfile]:
    if csv_dir and data_path:
        raise SystemExit("Specify only one of --csv-dir or --data, not both.")

    if csv_dir:
        return load_units_from_csv_local(csv_dir, prefer_faction=prefer_faction)

    if data_path:
        return load_units_from_json_local(data_path)

    for candidate in DEFAULT_CSV_SEARCH:
        try:
            return load_units_from_csv_local(candidate, prefer_faction=prefer_faction)
        except SystemExit:
            continue

    for candidate in DEFAULT_JSON_CANDIDATES:
        if candidate.exists():
            return load_units_from_json_local(candidate)

    raise SystemExit(
        "Could not locate unit data. Provide --csv-dir pointing at importer output or --data pointing at units.json."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrapper around the source-backed CLI to print preset matchup tables using the original rules engine.",
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        help="Directory containing importer CSV outputs (defaults to common data/ paths).",
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Path to units.json (used when CSV data is unavailable).",
    )
    parser.add_argument(
        "--prefer-faction",
        help="When duplicate unit names exist, prefer this faction (case-insensitive substring).",
    )
    parser.add_argument(
        "--attacker",
        help="Name of the attacking unit. If omitted, a random attacker is selected.",
    )
    parser.add_argument(
        "--random-fair-duel",
        action="store_true",
        help=("Select a random single-model attacker and defender that share a primary keyword and have similar points."),
    )
    parser.add_argument(
        "--max-point-delta",
        type=float,
        default=40.0,
        metavar="PTS",
        help=("Maximum points difference allowed when pairing fair random duels; set a negative value to disable the points filter."),
    )

    parser.add_argument(
        "--fair-require-both",
        action="store_true",
        help="Require random fair duels to use units that have both melee and ranged weapons.",
    )

    parser.add_argument(
        "--weapon-mode",
        choices=["all", "ranged", "melee"],
        default="all",
        help="Limit weapon tables to ranged, melee, or all weapons (default: all).",
    )
    parser.add_argument(
        "--ppm-basis",
        choices=["min", "average", "max"],
        default=LEGACY.DEFAULT_PPM_BASIS,
        help="Model count basis for points-per-model calculations (default from CLI).",
    )
    parser.add_argument(
        "--preset",
        dest="presets",
        action="append",
        metavar="NAME",
        help="Limit output to the specified preset table (repeatable). Defaults to all presets.",
    )
    parser.add_argument(
        "--defender",
        help="Name of a specific defending unit for a direct duel (requires --attacker).",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Optional path to export the generated tables (md or csv).",
    )
    parser.add_argument(
        "--scenario",
        help="Optional engagement scenario prompt (use 'realistic' for a default approach analysis).",
    )
    parser.add_argument(
        "--export-format",
        choices=["md", "csv"],
        default="md",
        help="Format to use when exporting tables (default: md).",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Generate a concise AI summary of the printed matchup tables.",
    )
    parser.add_argument(
        "--explain-model",
        default="gpt-5-mini",
        help="OpenAI model ID to use when --explain is enabled (default: gpt-5-mini).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional RNG seed applied before selecting a random attacker.",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available preset tables and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    capture_enabled = bool(args.explain)
    if capture_enabled:
        _begin_capture()

    if args.list_presets:
        _list_presets()
        if capture_enabled:
            _finalise_capture()
        return

    if args.seed is not None:
        LEGACY.random.seed(args.seed)

    units = _load_units_from_sources(args.csv_dir, args.data, args.prefer_faction)

    csv_dir = args.csv_dir
    if csv_dir:
        LEGACY._print_dataset_metadata(csv_dir)
        if capture_enabled:
            _capture_line(f"Dataset: {csv_dir}")

    if args.random_fair_duel:
        if args.attacker or args.defender:
            raise SystemExit('--random-fair-duel cannot be combined with --attacker/--defender.')
        if args.presets:
            raise SystemExit('--random-fair-duel is incompatible with --preset filtering.')
        if args.weapon_mode.lower() == 'all' or args.fair_require_both:
            required_modes = ('melee', 'ranged')
        else:
            required_modes = (args.weapon_mode,)

        fair_attacker, fair_defender = _select_fair_random_pair(
            units, required_modes=required_modes, max_point_delta=args.max_point_delta
        )

        if set(required_modes) == {'melee', 'ranged'}:
            args.weapon_mode = 'all'

        attacker_points = _unit_points(fair_attacker)
        defender_points = _unit_points(fair_defender)
        if attacker_points is not None and defender_points is not None:
            diff = abs(attacker_points - defender_points)
            selection_message = (
                f"Random fair duel selected: {fair_attacker.name} ({attacker_points:g}pts) vs "
                f"{fair_defender.name} ({defender_points:g}pts) | delta_pts={diff:g}"
            )
        else:
            selection_message = (
                f"Random fair duel selected: {fair_attacker.name} vs {fair_defender.name}"
            )
        print(selection_message)
        if capture_enabled:
            _capture_line(selection_message)
        args.attacker = fair_attacker.name
        args.defender = fair_defender.name

    if args.attacker:
        attacker = LEGACY._require_unit(units, args.attacker)
        selection_message = f"Attacker selected: {attacker.name} using {args.weapon_mode} weapons"
    else:
        attacker = LEGACY._select_random_attacker(units, args.weapon_mode)
        selection_message = f"Random attacker selected: {attacker.name} using {args.weapon_mode} weapons"

    print(selection_message)
    if capture_enabled:
        _capture_line(selection_message)

    tables_printed = False
    scenario_prompt = None
    if args.scenario:
        if args.scenario.strip().lower() == "realistic":
            scenario_prompt = DEFAULT_REALISTIC_SCENARIO
        else:
            scenario_prompt = args.scenario.strip()
        scenario_message = f"Scenario note: {scenario_prompt}"
        print(scenario_message)
        if capture_enabled:
            _capture_line(scenario_message)

    if args.defender:
        if not args.attacker:
            raise SystemExit("--defender requires --attacker.")
        if args.presets:
            raise SystemExit("--defender cannot be combined with --preset.")
        defender = LEGACY._require_unit(units, args.defender)
        duel_label = f"Duel: {attacker.name} vs {defender.name} ({args.weapon_mode})"
        print(duel_label)
        if capture_enabled:
            _capture_line(duel_label)

        movement_summary = _describe_movement(attacker, defender)
        if movement_summary:
            print(movement_summary)
            if capture_enabled:
                _capture_line(movement_summary)
            if scenario_prompt:
                scenario_prompt = f"{scenario_prompt} Movement comparison: {movement_summary}"

        LEGACY._print_attacker_summary(attacker, args.weapon_mode, prefix="Duel")
        table = LEGACY._build_weapon_table(attacker, [defender], args.weapon_mode, args.ppm_basis)
        if not table:
            message = "No valid weapons available for this duel."
            print(message)
            if capture_enabled:
                _capture_line(message)
        else:
            LEGACY._print_weapon_table_data(table)

        return_label = f"Return strike: {defender.name} vs {attacker.name} ({args.weapon_mode})"
        print(return_label)
        if capture_enabled:
            _capture_line(return_label)
        LEGACY._print_attacker_summary(defender, args.weapon_mode, prefix="Return")
        reverse_table = LEGACY._build_weapon_table(defender, [attacker], args.weapon_mode, args.ppm_basis)
        if not reverse_table:
            message = "No valid weapons available for the defending unit."
            print(message)
            if capture_enabled:
                _capture_line(message)
        else:
            LEGACY._print_weapon_table_data(reverse_table)

        tables_printed = True
    else:
        presets = _normalise_presets(args.presets)
        if capture_enabled:
            _capture_line("Selected presets: " + ", ".join(presets))
        fast_highlights = _collect_fast_units(units, presets)
        if fast_highlights:
            threshold_value = (
                str(int(FAST_MOVE_THRESHOLD))
                if float(FAST_MOVE_THRESHOLD).is_integer()
                else f"{FAST_MOVE_THRESHOLD:.1f}"
            )
            header = f'Fast defenders (>={threshold_value}" move or Advance+Charge):'
            print(header)
            if capture_enabled:
                _capture_line(header)
            for preset_name in presets:
                entries = fast_highlights.get(preset_name)
                if not entries:
                    continue
                line = f"  {preset_name}: {', '.join(entries)}"
                print(line)
                if capture_enabled:
                    _capture_line(line)
        LEGACY._print_attacker_summary(attacker, args.weapon_mode, prefix="Preset")
        LEGACY._print_weapon_tables_for_presets(
            units,
            attacker,
            presets,
            args.weapon_mode,
            args.ppm_basis,
            export_path=args.export,
            export_format=args.export_format,
        )
        tables_printed = True

    if capture_enabled and tables_printed:
        summary_text = _finalise_capture()
        if summary_text.strip():
            print("\n=== AI summary ===")
            try:
                report = _summarise_with_ai(summary_text, args.explain_model, scenario_prompt)
            except SystemExit:
                raise
            except Exception as exc:
                _safe_output(f"Failed to generate AI summary: {exc}")
            else:
                _safe_output(report)
        else:
            print("\n=== AI summary ===")
            _safe_output("No matchup tables were produced to summarise.")



if __name__ == "__main__":
    main()





