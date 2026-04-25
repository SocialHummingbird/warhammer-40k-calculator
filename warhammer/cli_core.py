from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .calculator import EngagementMode, evaluate_unit, evaluate_weapon
from .datasheet import load_units_from_csv as _load_units_from_csv
from .datasheet import load_units_from_json as _load_units_from_json
from .formatting import abbreviate_weapon_keyword, format_three_decimal_text, normalise_weapon_label
from .profiles import UnitProfile, WeaponProfile
from .reference import build_reference


DEFAULT_PPM_BASIS = "average"
PRESET_ORDER = ["core", "infantry", "elite", "vehicles", "monsters", "titans", "primarchs"]
TARGET_PRESETS = {
    "core": [
        "Cadian Command Squad",
        "Boyz",
        "Intercessor Squad",
        "Terminator Squad",
        "Custodian Guard",
        "Necron Warriors",
    ],
    "infantry": ["Guardian Defenders", "Kabalite Warriors", "Heavy Intercessor Squad", "Strike Squad"],
    "elite": [
        "Bladeguard Veteran Squad",
        "Incubi",
        "Blightlord Terminators",
        "Custodian Wardens",
        "Tyranid Warriors with Melee Bio-Weapons",
        "Zoanthropes",
    ],
    "vehicles": ["Canis Rex", "The Silent King", "Firestrike Servo-Turrets", "Thunderfire Cannon [Legends]", "Rhino"],
    "monsters": ["Carnifexes", "Avatar of Khaine", "C'tan Shard of the Void Dragon", "Talos", "Ghazghkull Thraka"],
    "titans": ["Warhound Titan", "Reaver Titan", "Warlord Titan", "Warbringer Nemesis Titan"],
    "primarchs": ["Roboute Guilliman", "Lion El'Jonson", "Mortarion", "Magnus the Red", "Angron"],
}
TARGET_PRESETS["all"] = [name for preset in PRESET_ORDER for name in TARGET_PRESETS[preset]]


def _safe_print(text: str = "") -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


def _require_unit(units: Dict[str, UnitProfile], name: str) -> UnitProfile:
    key = name.casefold()
    if key in units:
        return units[key]
    for unit in units.values():
        if unit.name.casefold() == key:
            return unit
    matches = [unit.name for unit in units.values() if key in unit.name.casefold()]
    if len(matches) == 1:
        return _require_unit(units, matches[0])
    if matches:
        preview = ", ".join(sorted(matches)[:10])
        raise SystemExit(f"Ambiguous unit name '{name}'. Matches: {preview}")
    raise SystemExit(f"Unknown unit: {name}")


def _filter_weapons_for_table(attacker: UnitProfile, weapon_mode: str) -> List[WeaponProfile]:
    mode = (weapon_mode or "all").lower()
    if mode == "all":
        return list(attacker.weapons)
    return [weapon for weapon in attacker.weapons if weapon.type == mode]


def _select_random_attacker(units: Dict[str, UnitProfile], weapon_mode: str) -> UnitProfile:
    candidates = [unit for unit in units.values() if _filter_weapons_for_table(unit, weapon_mode)]
    if not candidates:
        raise SystemExit(f"No units have weapons for mode: {weapon_mode}")
    return random.choice(candidates)


def _print_unit_catalog(units: Dict[str, UnitProfile]) -> None:
    print("Available units:\n")
    for unit in sorted(units.values(), key=lambda item: item.name.casefold()):
        weapons = ", ".join(f"{weapon.name} ({weapon.type})" for weapon in unit.weapons) or "none"
        print(f"- {unit.name}: T{unit.toughness}, Save {unit.save_label}, Wounds {unit.wounds}. Weapons: {weapons}")


def _print_result_header(
    attacker_name: str,
    defender_name: str,
    mode: EngagementMode,
    *,
    prefix: str = "Output",
) -> None:
    title = f"{prefix}: {attacker_name} vs {defender_name} ({mode.title()} weapons)"
    print(title)
    print("=" * len(title))


def _print_unit_result(result, *, target_name: str) -> None:
    if not result.weapons:
        print("No weapons available for this mode.")
        return
    for weapon_result in result.weapons:
        weapon = weapon_result.weapon
        print(
            f"{weapon.name}: {weapon_result.attacks:g} attacks -> "
            f"{weapon_result.hits:.2f} hits -> {weapon_result.wounds:.2f} wounds -> "
            f"{weapon_result.unsaved_wounds:.2f} unsaved -> {weapon_result.expected_damage:.2f} dmg"
        )
        print(
            f"  Hit {weapon.skill_label} ({weapon_result.hit_probability:.2%}), "
            f"Wound {weapon_result.wound_roll_label} ({weapon_result.wound_probability:.2%}), "
            f"Save {weapon_result.save_used_label}, fail chance {weapon_result.failed_save_probability:.2%}"
        )
        models = weapon_result.expected_models_destroyed
        if models is not None:
            print(f"  Expected {models:.2f} {target_name} models destroyed")
        if weapon_result.ability_notes:
            print("  Notes: " + ", ".join(weapon_result.ability_notes))
    print(
        f"Total unsaved wounds: {result.total_unsaved_wounds:.2f} "
        f"(before FNP {result.total_unsaved_wounds_before_fnp:.2f}). "
        f"Total expected damage: {result.total_damage:.2f}."
    )
    models = result.expected_models_destroyed
    if models is not None:
        print(f"Average models destroyed: {models:.2f} {target_name}.")


def _print_attacker_summary(attacker: UnitProfile, weapon_mode: str, *, prefix: str) -> None:
    faction = f" ({attacker.faction})" if attacker.faction else ""
    print(f"{prefix}: {attacker.name}{faction} using {weapon_mode} weapons")


def _resolve_unit_models(unit: UnitProfile) -> Tuple[Optional[int], Optional[int]]:
    return unit.models_min, unit.models_max


def _estimate_models_per_unit(unit: UnitProfile) -> int:
    minimum, maximum = _resolve_unit_models(unit)
    if minimum and maximum:
        return max(1, round((minimum + maximum) / 2))
    if maximum:
        return max(1, maximum)
    if minimum:
        return max(1, minimum)
    return 1


def _models_for_ppm(unit: UnitProfile, ppm_basis: str) -> int:
    minimum, maximum = _resolve_unit_models(unit)
    if ppm_basis == "min" and minimum:
        return max(1, minimum)
    if ppm_basis == "max" and maximum:
        return max(1, maximum)
    return _estimate_models_per_unit(unit)


def _ppm_info(unit: UnitProfile, ppm_basis: str) -> Dict[str, object]:
    models = _models_for_ppm(unit, ppm_basis)
    points = unit.points or 0
    ppm = (points / models) if points and models else 0.0
    minimum, maximum = _resolve_unit_models(unit)
    min_ppm = (points / maximum) if points and maximum else None
    max_ppm = (points / minimum) if points and minimum else None
    return {
        "models": models,
        "models_min": minimum,
        "models_max": maximum,
        "points": points,
        "ppm": ppm,
        "min_ppm": min_ppm,
        "max_ppm": max_ppm,
    }


def _format_unit_defense_label(unit: UnitProfile, ppm_basis: str, ppm_info: Optional[Dict[str, object]] = None) -> str:
    ppm_info = ppm_info or _ppm_info(unit, ppm_basis)
    bits = [f"T{unit.toughness}", f"W{unit.wounds}", unit.save_label]
    if unit.invulnerable_label:
        bits.append(unit.invulnerable_label)
    return " ".join(bits) + f" {float(ppm_info['points']):.3f}pts"


def _format_points_row(info: Dict[str, object]) -> str:
    minimum = info.get("models_min")
    maximum = info.get("models_max")
    if minimum and maximum and minimum != maximum:
        models_text = f"{minimum}-{maximum}"
    else:
        models_text = str(minimum or maximum or info.get("models") or 1)
    ppm = float(info.get("ppm") or 0.0)
    text = f"M: {models_text}; PPM: {ppm:.3f}"
    min_ppm = info.get("min_ppm")
    max_ppm = info.get("max_ppm")
    if min_ppm is not None and max_ppm is not None and abs(float(min_ppm) - float(max_ppm)) > 1e-9:
        text += f" [{float(min_ppm):.1f}-{float(max_ppm):.1f}]"
    return text


def _format_weapon_profile(weapon: WeaponProfile) -> str:
    type_label = "[M]" if weapon.type == "melee" else "[R]" if weapon.type == "ranged" else ""
    parts = [
        f"{type_label} A{weapon.attacks.label}".strip(),
        weapon.skill_label,
        f"S{weapon.strength}",
        f"AP{weapon.ap}",
        weapon.damage.label if weapon.damage.label.upper().startswith("D") else f"D{weapon.damage.label}",
    ]
    text = " | ".join(parts)
    extras: List[str] = []
    extras.extend(weapon.keywords or [])
    if weapon.lethal_hits:
        extras.append("Lethal Hits")
    if weapon.sustained_hits:
        extras.append(f"Sustained Hits {weapon.sustained_hits}")
    if weapon.devastating_wounds:
        extras.append("Devastating Wounds")
    if weapon.melta is not None:
        extras.append(f"Melta {weapon.melta}")
    if weapon.rapid_fire is not None:
        extras.append(f"Rapid Fire {weapon.rapid_fire}")
    for target, roll in weapon.anti_rules:
        extras.append(f"Anti-{target} {roll}+")
    abbreviated: List[str] = []
    seen: set[str] = set()
    for extra in extras:
        abbr = abbreviate_weapon_keyword(extra)
        if abbr and abbr != "-" and abbr not in seen:
            abbreviated.append(abbr)
            seen.add(abbr)
    if abbreviated:
        text += f" ({'; '.join(abbreviated)})"
    return text


def _build_weapon_table(attacker: UnitProfile, targets: Iterable[UnitProfile], weapon_mode: str, ppm_basis: str):
    target_list = list(targets)
    weapons = _filter_weapons_for_table(attacker, weapon_mode)
    if not weapons or not target_list:
        return None
    infos = [_ppm_info(target, ppm_basis) for target in target_list]
    name_header = ["Weapon", "Weapon Profile"] + [target.name for target in target_list]
    stats_header = ["", "A / Skill / S / AP / D"] + [
        _format_unit_defense_label(target, ppm_basis, info) for target, info in zip(target_list, infos)
    ]
    points_row = ["Points", ""] + [_format_points_row(info) for info in infos]
    rows: List[List[str]] = []
    for weapon in weapons:
        row = [normalise_weapon_label(weapon.name), _format_weapon_profile(weapon)]
        for target, info in zip(target_list, infos):
            result = evaluate_weapon(attacker, target, weapon)
            models = result.expected_models_destroyed or 0.0
            points_removed = models * float(info.get("ppm") or 0.0)
            row.append(f"{result.expected_damage:.3f} / {models:.3f} / {points_removed:.3f}pts")
        rows.append(row)
    return {
        "attacker": attacker,
        "targets": target_list,
        "name_header": name_header,
        "stats_header": stats_header,
        "_extra_header_rows": [points_row],
        "rows": rows,
        "note": f"Cells show expected damage / models destroyed / target points removed per volley (PPM basis: {ppm_basis}).",
    }


def _print_weapon_table_data(table) -> None:
    if not table:
        return
    headers = [[str(value) for value in table.get("name_header", [])]]
    headers.append([str(value) for value in table.get("stats_header", [])])
    headers.extend([[str(value) for value in row] for row in table.get("_extra_header_rows", [])])
    rows = [[str(value) for value in row] for row in table.get("rows", [])]
    all_rows = headers + rows
    col_count = max((len(row) for row in all_rows), default=0)
    padded = [row + [""] * (col_count - len(row)) for row in all_rows]
    formatted = [[format_three_decimal_text(value) for value in row] for row in padded]
    widths = [0] * col_count
    for row in formatted:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def format_row(values: List[str]) -> str:
        cells = []
        for idx, value in enumerate(values):
            cells.append(value.ljust(widths[idx]) if idx == 0 else value.rjust(widths[idx]))
        return " | ".join(cells)

    print(format_row(formatted[0]))
    print(format_row(formatted[1]))
    for row in formatted[2 : len(headers)]:
        print(format_row(row))
    print("-+-".join("-" * width for width in widths))
    for row in formatted[len(headers) :]:
        print(format_row(row))
    note = table.get("note")
    if note:
        print()
        print(format_three_decimal_text(str(note)))


def _export_weapon_tables(entries: List[Dict[str, object]], destination: Path, export_format: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if export_format == "csv":
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            for entry in entries:
                table = entry["table"]
                writer.writerow([entry.get("title", "")])
                writer.writerow(table["name_header"])
                writer.writerow(table["stats_header"])
                for extra in table.get("_extra_header_rows", []):
                    writer.writerow(extra)
                writer.writerows(table["rows"])
                writer.writerow([])
        return

    lines: List[str] = []
    for entry in entries:
        table = entry["table"]
        title = str(entry.get("title") or "Weapon table")
        lines.append(f"## {title}")
        rows = [table["name_header"], table["stats_header"], *table.get("_extra_header_rows", []), *table["rows"]]
        if not rows:
            continue
        lines.append("| " + " | ".join(str(value) for value in rows[0]) + " |")
        lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
        for row in rows[1:]:
            lines.append("| " + " | ".join(str(value) for value in row) + " |")
        if table.get("note"):
            lines.append("")
            lines.append(str(table["note"]))
        lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")


def _print_weapon_tables_for_presets(
    units: Dict[str, UnitProfile],
    attacker: UnitProfile,
    presets: List[str],
    weapon_mode: str,
    ppm_basis: str,
    *,
    export_path: Optional[Path],
    export_format: str,
) -> None:
    export_entries: List[Dict[str, object]] = []
    for preset in presets:
        targets = [_require_unit(units, name) for name in TARGET_PRESETS[preset] if name.casefold() in units]
        if not targets:
            print(f"No targets found for preset: {preset}")
            continue
        title = f"Preset: {preset.title()} - Attacker: {attacker.name}"
        print()
        print(title)
        print("-" * len(title))
        table = _build_weapon_table(attacker, targets, weapon_mode, ppm_basis)
        if not table:
            print("No valid weapons available for this preset.")
            continue
        _print_weapon_table_data(table)
        export_entries.append({"title": title, "table": table})
    if export_path and export_entries:
        _export_weapon_tables(export_entries, export_path, export_format)


def _print_dataset_metadata(csv_dir: Path) -> None:
    metadata_path = csv_dir / "metadata.json"
    if not metadata_path.exists():
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    counts = metadata.get("counts") or {}
    repo = metadata.get("github_repo") or metadata.get("sources") or "CSV"
    ref = metadata.get("github_ref") or "local"
    generated = metadata.get("generated_at") or "unknown"
    print(f"Data: {repo}, {ref}, units={counts.get('units', '?')}, {generated}")
    print()


def _load_units(args: argparse.Namespace) -> Dict[str, UnitProfile]:
    if args.csv_dir and args.data:
        raise SystemExit("Specify only one of --csv-dir or --data.")
    if args.csv_dir:
        return _load_units_from_csv(args.csv_dir, prefer_faction=args.prefer_faction)
    return _load_units_from_json(args.data or Path("units.json"))


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Warhammer 40K damage calculator")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--csv-dir", type=Path)
    parser.add_argument("--attacker")
    parser.add_argument("--prefer-faction")
    parser.add_argument("--defender")
    parser.add_argument("--mode", choices=["ranged", "melee"], default="ranged")
    parser.add_argument("--random-matchup", action="store_true")
    parser.add_argument("--random-battle", action="store_true")
    parser.add_argument("--weapon-table", action="store_true")
    parser.add_argument("--weapon-tables-all-presets", action="store_true")
    parser.add_argument("--weapon-tables-all-presets-random", action="store_true")
    parser.add_argument("--targets", action="append", default=[])
    parser.add_argument("--targets-preset", action="append", choices=["all", *PRESET_ORDER])
    parser.add_argument("--weapon-table-combined", action="store_true")
    parser.add_argument("--weapon-mode", choices=["all", "ranged", "melee"], default="all")
    parser.add_argument("--ppm-basis", choices=["min", "average", "max"], default=DEFAULT_PPM_BASIS)
    parser.add_argument("--export-table", type=Path)
    parser.add_argument("--export-format", choices=["md", "csv"], default="md")
    parser.add_argument("--supplement", type=Path, action="append", default=[])
    parser.add_argument("--list-units", action="store_true")
    parser.add_argument("--reference")
    args = parser.parse_args(argv)

    units = _load_units(args)
    for supplement in args.supplement:
        units.update(_load_units_from_json(supplement))

    if args.csv_dir:
        _print_dataset_metadata(args.csv_dir)
    if args.list_units:
        _print_unit_catalog(units)
        return
    if args.reference:
        markdown = build_reference(units.values())
        if args.reference == "-":
            _safe_print(markdown)
        else:
            Path(args.reference).write_text(markdown, encoding="utf-8")
        return

    if args.weapon_tables_all_presets_random:
        attacker = _select_random_attacker(units, args.weapon_mode)
        print(f"Random attacker selected: {attacker.name} using {args.weapon_mode} weapons")
        _print_weapon_tables_for_presets(
            units,
            attacker,
            PRESET_ORDER,
            args.weapon_mode,
            args.ppm_basis,
            export_path=args.export_table,
            export_format=args.export_format,
        )
        return

    if args.weapon_tables_all_presets:
        if not args.attacker:
            raise SystemExit("--weapon-tables-all-presets requires --attacker")
        attacker = _require_unit(units, args.attacker)
        _print_attacker_summary(attacker, args.weapon_mode, prefix="Attacker")
        _print_weapon_tables_for_presets(
            units,
            attacker,
            PRESET_ORDER,
            args.weapon_mode,
            args.ppm_basis,
            export_path=args.export_table,
            export_format=args.export_format,
        )
        return

    if args.weapon_table:
        if not args.attacker:
            raise SystemExit("--weapon-table requires --attacker")
        attacker = _require_unit(units, args.attacker)
        target_names = list(args.targets)
        for preset in args.targets_preset or []:
            target_names.extend(TARGET_PRESETS[preset])
        if not target_names:
            raise SystemExit("--weapon-table requires --targets or --targets-preset")
        targets = [_require_unit(units, name) for name in target_names]
        _print_attacker_summary(attacker, args.weapon_mode, prefix="Attacker")
        print()
        table = _build_weapon_table(attacker, targets, args.weapon_mode, args.ppm_basis)
        if not table:
            print("No valid weapons available.")
            return
        _print_weapon_table_data(table)
        if args.export_table:
            _export_weapon_tables([{"title": f"Attacker: {attacker.name}", "table": table}], args.export_table, args.export_format)
        return

    if args.random_matchup or args.random_battle:
        attacker = _select_random_attacker(units, args.mode)
        defenders = [unit for unit in units.values() if unit is not attacker]
        defender = random.choice(defenders)
    else:
        if not args.attacker or not args.defender:
            raise SystemExit("Specify --attacker and --defender, or use a table/random option.")
        attacker = _require_unit(units, args.attacker)
        defender = _require_unit(units, args.defender)

    result = evaluate_unit(attacker, defender, args.mode)
    _print_result_header(attacker.name, defender.name, args.mode)
    _print_unit_result(result, target_name=defender.name)
    print()
    reverse = evaluate_unit(defender, attacker, args.mode)
    _print_result_header(defender.name, attacker.name, args.mode, prefix="Damage Received")
    _print_unit_result(reverse, target_name=attacker.name)
