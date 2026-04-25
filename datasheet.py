
import argparse
import sys
from pathlib import Path

from warhammer.datasheet import (
    load_units_from_csv,
    load_units_from_json,
    print_unit_datasheet,
)


def _merge_supplements(units: dict[str, object], supplements: list[Path]) -> None:
    for supplement in supplements:
        extras = load_units_from_json(supplement)
        units.update(extras)


def _require_unit(units, name: str):
    key = name.casefold()
    try:
        return units[key]
    except KeyError:
        available = ", ".join(sorted(u.name for u in units.values()))
        raise SystemExit(f"Unknown unit '{name}'. Available units: {available}") from None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a parsed datasheet for a unit")
    parser.add_argument("--unit", required=True, help="Name of the unit to display")
    parser.add_argument("--csv-dir", type=Path, help="Directory containing importer CSV outputs")
    parser.add_argument("--data", type=Path, help="Path to the unit data JSON file")
    parser.add_argument(
        "--prefer-faction",
        help="When duplicate unit names exist, prefer this faction (case-insensitive substring match)",
    )
    parser.add_argument(
        "--supplement",
        action="append",
        type=Path,
        metavar="JSON",
        help="Path to supplemental unit JSON file to merge (repeatable)",
    )
    parser.add_argument(
        "--include-crusade",
        action="store_true",
        help="Include Crusade upgrades and battle scars in the datasheet output",
    )
    args = parser.parse_args()
    if args.csv_dir and args.data:
        parser.error("Choose either --data or --csv-dir, not both")
    if not args.csv_dir and not args.data:
        parser.error("Provide --csv-dir or --data to load units")
    return args


def main() -> None:
    args = _parse_args()

    if args.csv_dir:
        units = load_units_from_csv(args.csv_dir, prefer_faction=args.prefer_faction)
    else:
        units = load_units_from_json(args.data)

    if args.supplement:
        _merge_supplements(units, args.supplement)

    unit = _require_unit(units, args.unit)
    print_unit_datasheet(unit, include_crusade=args.include_crusade)


if __name__ == "__main__":
    main()
