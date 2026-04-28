from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import (
    load_footprint_rejections_csv,
    load_footprint_suggestions_csv,
    rejected_rows_from_suggestions,
    write_footprint_rejections_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mark reviewed unit-footprint suggestions as rejected so they are not resurfaced."
    )
    parser.add_argument("--suggestions", type=Path, default=Path("data/10e/latest/unit_footprint_suggestions.csv"))
    parser.add_argument("--rejections", type=Path, default=Path("data/base_sizes/unit_footprint_rejections.csv"))
    parser.add_argument("--unit-id", action="append", default=[], help="Reject only a specific unit id. Repeatable.")
    parser.add_argument("--min-score", type=float, default=0.8, help="Minimum suggestion score to reject.")
    parser.add_argument("--rank", type=int, default=1, help="Suggestion rank to reject.")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to reject.")
    parser.add_argument(
        "--reason",
        default="Reviewed and not accepted as a safe official base-size match.",
        help="Review reason to write into the rejection CSV.",
    )
    parser.add_argument("--apply", action="store_true", help="Write rejected rows to the rejections CSV.")
    args = parser.parse_args()

    if not args.suggestions.exists():
        parser.error(f"suggestions CSV not found: {args.suggestions}")
    suggestions = load_footprint_suggestions_csv(args.suggestions)
    rejections = load_footprint_rejections_csv(args.rejections) if args.rejections.exists() else []
    selected = rejected_rows_from_suggestions(
        suggestions,
        rejections,
        unit_ids=set(args.unit_id) if args.unit_id else None,
        min_score=args.min_score,
        rank=args.rank,
        reason=args.reason,
        limit=args.limit,
    )

    action = "Would reject" if not args.apply else "Rejected"
    print(f"{action} {len(selected)} footprint suggestion row(s).")
    for row in selected:
        base = row.get("base_size_text") or "unknown base"
        print(f"- {row.get('unit_id')}: {row.get('unit_name')} -> {row.get('guide_unit_name')} ({base})")

    if args.apply and selected:
        args.rejections.parent.mkdir(parents=True, exist_ok=True)
        write_footprint_rejections_csv([*rejections, *selected], args.rejections)
        print(f"Wrote {len(rejections) + len(selected)} total rejection row(s) to {args.rejections}.")
    elif not args.apply:
        print("Dry run only. Re-run with --apply after reviewing the listed rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
