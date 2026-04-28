from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import (
    accepted_override_rows_from_suggestions,
    load_footprint_overrides_csv,
    load_footprint_suggestions_csv,
    write_footprint_overrides_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote reviewed unit-footprint suggestions into the manual override CSV."
    )
    parser.add_argument("--suggestions", type=Path, default=Path("data/10e/latest/unit_footprint_suggestions.csv"))
    parser.add_argument("--overrides", type=Path, default=Path("data/base_sizes/unit_footprint_overrides.csv"))
    parser.add_argument("--unit-id", action="append", default=[], help="Accept only a specific unit id. Repeatable.")
    parser.add_argument("--min-score", type=float, default=0.9, help="Minimum suggestion score to accept.")
    parser.add_argument("--rank", type=int, default=1, help="Suggestion rank to accept.")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to accept.")
    parser.add_argument("--apply", action="store_true", help="Write accepted rows to the overrides CSV.")
    args = parser.parse_args()

    if not args.suggestions.exists():
        parser.error(f"suggestions CSV not found: {args.suggestions}")
    suggestions = load_footprint_suggestions_csv(args.suggestions)
    overrides = load_footprint_overrides_csv(args.overrides) if args.overrides.exists() else []
    selected = accepted_override_rows_from_suggestions(
        suggestions,
        overrides,
        unit_ids=set(args.unit_id) if args.unit_id else None,
        min_score=args.min_score,
        rank=args.rank,
        limit=args.limit,
    )

    action = "Would accept" if not args.apply else "Accepted"
    print(f"{action} {len(selected)} footprint suggestion override row(s).")
    for row in selected:
        base = row.get("base_size_text") or row.get("base_type") or "unknown base"
        print(f"- {row.get('unit_id')}: {row.get('unit_name')} -> {row.get('guide_unit_name')} ({base})")

    if args.apply and selected:
        args.overrides.parent.mkdir(parents=True, exist_ok=True)
        write_footprint_overrides_csv([*overrides, *selected], args.overrides)
        print(f"Wrote {len(overrides) + len(selected)} total override row(s) to {args.overrides}.")
    elif not args.apply:
        print("Dry run only. Re-run with --apply after reviewing the listed rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
