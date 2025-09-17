import argparse
import json
from pathlib import Path
from typing import Dict

from warhammer.calculator import EngagementMode, UnitResult, evaluate_unit
from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.profiles import UnitProfile, load_units
from warhammer.reference import build_reference


def main() -> None:
    args = _parse_args()

    if args.csv_dir:
        units = _load_units_from_csv(args.csv_dir)
    else:
        json_path = args.data or Path("units.json")
        units = _load_units_from_json(json_path)

    if args.reference:
        _output_reference(units, args.reference)
        return

    if args.list_units:
        _print_unit_catalog(units)
        return

    attacker = _require_unit(units, args.attacker)
    defender = _require_unit(units, args.defender)
    mode: EngagementMode = args.mode

    attacker_result = evaluate_unit(attacker, defender, mode)
    defender_result = evaluate_unit(defender, attacker, mode)

    _print_result_header(attacker.name, defender.name, mode)
    _print_unit_result(attacker_result, target_name=defender.name)

    print()
    _print_result_header(defender.name, attacker.name, mode, prefix="Damage Received")
    _print_unit_result(defender_result, target_name=attacker.name)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warhammer 40K damage calculator")
    parser.add_argument("--data", type=Path, help="Path to the unit data JSON file")
    parser.add_argument(
        "--csv-dir",
        type=Path,
        help="Directory containing importer CSV outputs (units.csv, weapons.csv, etc.)",
    )
    parser.add_argument("--attacker", required=False, help="Name of the attacking unit")
    parser.add_argument("--defender", required=False, help="Name of the defending unit")
    parser.add_argument("--mode", choices=["ranged", "melee"], default="ranged", help="Engagement mode")
    parser.add_argument("--list-units", action="store_true", help="List available units and exit")
    parser.add_argument(
        "--reference",
        metavar="OUT",
        help="Write keyword/ability reference to file (use '-' for stdout)",
    )

    args = parser.parse_args()
    if args.csv_dir and args.data:
        parser.error("Choose either --data or --csv-dir, not both")

    if not args.list_units and not args.reference and (not args.attacker or not args.defender):
        parser.error("--attacker and --defender are required unless --list-units or --reference is used")
    return args


def _load_units_from_json(path: Path) -> Dict[str, UnitProfile]:
    if not path.exists():
        raise SystemExit(f"Data file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if "units" not in payload or not isinstance(payload["units"], list):
        raise SystemExit("Data file must contain a top-level 'units' list")

    units = load_units(payload["units"])
    return {unit.name.lower(): unit for unit in units}


def _load_units_from_csv(directory: Path) -> Dict[str, UnitProfile]:
    if not directory.exists():
        raise SystemExit(f"CSV directory not found: {directory}")

    profiles_by_id = load_units_from_directory(directory)
    if not profiles_by_id:
        raise SystemExit(f"No units found in CSV directory: {directory}")

    units: Dict[str, UnitProfile] = {}
    for profile in profiles_by_id.values():
        key = profile.name.lower()
        if key in units:
            raise SystemExit(f"Duplicate unit name detected in CSV data: {profile.name}")
        units[key] = profile
    return units


def _print_unit_catalog(units: Dict[str, UnitProfile]) -> None:
    print("Available units:\n")
    for unit in sorted(units.values(), key=lambda u: u.name):
        weapon_summary = ", ".join(f"{weapon.name} ({weapon.type})" for weapon in unit.weapons)
        invul_text = f", Invul {unit.invulnerable_label}" if unit.invulnerable_label else ""
        fnp_text = f", FNP {unit.feel_no_pain_label}" if unit.feel_no_pain_label else ""
        cap_text = f", Damage Cap {unit.damage_cap:g}" if unit.damage_cap is not None else ""
        keywords_text = f", Keywords: {', '.join(unit.keywords)}" if unit.keywords else ""
        abilities_text = f", Abilities: {', '.join(ability.name for ability in unit.abilities)}" if unit.abilities else ""
        print(
            f"- {unit.name}: T{unit.toughness}, Save {unit.save_label}{invul_text}{fnp_text}{cap_text}, "
            f"Wounds {unit.wounds}. Weapons: {weapon_summary or 'None'}{keywords_text}{abilities_text}"
        )


def _require_unit(units: Dict[str, UnitProfile], name: str) -> UnitProfile:
    try:
        return units[name.lower()]
    except KeyError:
        available = ", ".join(sorted(unit.name for unit in units.values()))
        raise SystemExit(f"Unknown unit '{name}'. Available units: {available}") from None


def _print_result_header(attacker_name: str, defender_name: str, mode: EngagementMode, *, prefix: str = "Output") -> None:
    title = f"{prefix}: {attacker_name} vs {defender_name} ({mode.title()} weapons)"
    print(title)
    print("=" * len(title))


def _print_unit_result(result: UnitResult, *, target_name: str) -> None:
    if not result.weapons:
        print(f"No weapons available in this mode for {result.unit.name}.")
        return

    for weapon_result in result.weapons:
        weapon = weapon_result.weapon
        unsaved_text = f"{weapon_result.unsaved_wounds:.2f} unsaved"
        if weapon_result.fnp_success_probability > 0:
            unsaved_text += f" ({weapon_result.unsaved_wounds_before_fnp:.2f} before FNP)"
        print(
            f"{weapon.name}: {weapon.attacks.label} attacks -> {weapon_result.hits:.2f} hits -> "
            f"{weapon_result.wounds:.2f} wounds -> {unsaved_text} -> "
            f"{weapon_result.expected_damage:.2f} dmg"
        )
        print(
            f"  Hit {weapon.skill_label} ({weapon_result.hit_probability:.2%}), "
            f"Wound {weapon_result.wound_roll_label} ({weapon_result.wound_probability:.2%}), "
            f"Save {weapon_result.save_used_label}, fail chance {weapon_result.failed_save_probability:.2%}"
        )
        if weapon_result.critical_hits > 0 or weapon_result.extra_hits > 0 or weapon_result.auto_wounds > 0:
            details = []
            if weapon_result.critical_hits > 0:
                details.append(f"crit {weapon_result.critical_hits:.2f}")
            if weapon_result.extra_hits > 0:
                details.append(f"extra hits {weapon_result.extra_hits:.2f}")
            if weapon_result.auto_wounds > 0:
                details.append(f"auto wounds {weapon_result.auto_wounds:.2f}")
            print(f"  Critical effects: {', '.join(details)}")
        if weapon_result.ability_notes:
            print(f"  Abilities: {', '.join(weapon_result.ability_notes)}")
        if weapon_result.devastating_wounds > 0:
            print(f"  Devastating wounds bypass saves: {weapon_result.devastating_wounds:.2f}")
        if weapon_result.damage_cap_applied is not None:
            print(f"  Damage per unsaved wound capped at {weapon_result.damage_cap_applied:g}")
        if weapon_result.fnp_success_probability > 0:
            label = weapon_result.target_fnp_label or "Feel No Pain"
            print(
                f"  {label} ignores {weapon_result.fnp_success_probability:.2%} of unsaved wounds"
            )
        if weapon_result.expected_models_destroyed is not None:
            print(f"  Expected {weapon_result.expected_models_destroyed:.2f} {target_name} models destroyed")

    total_line = (
        f"Total unsaved wounds: {result.total_unsaved_wounds:.2f} "
        f"(before FNP {result.total_unsaved_wounds_before_fnp:.2f}). "
        f"Total expected damage: {result.total_damage:.2f}."
    )
    print(total_line)
    if result.expected_models_destroyed is not None:
        print(f"Average models destroyed: {result.expected_models_destroyed:.2f} {target_name}.")


def _output_reference(units: Dict[str, UnitProfile], destination: str) -> None:
    reference_text = build_reference(units.values())
    if destination.strip() == "-":
        print(reference_text)
        return

    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(reference_text, encoding="utf-8")
    print(f"Wrote reference to {output_path}")


if __name__ == "__main__":
    main()
