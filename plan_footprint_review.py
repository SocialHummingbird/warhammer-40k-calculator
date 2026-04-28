from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import (
    build_footprint_review_queue,
    load_footprint_override_template_csv,
    write_footprint_review_queue_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a prioritized CSV queue from unit_footprint_override_template.csv."
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("data/10e/latest/unit_footprint_override_template.csv"),
        help="Override-template CSV to prioritize.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/10e/latest/unit_footprint_review_queue.csv"),
        help="Prioritized review queue CSV to write.",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of queue rows to write.")
    parser.add_argument("--faction-contains", default="", help="Only include rows whose faction contains this text.")
    parser.add_argument("--include-decided", action="store_true", help="Include rows that already have review_decision.")
    args = parser.parse_args()

    if not args.template.exists():
        parser.error(f"override template CSV not found: {args.template}")

    rows = load_footprint_override_template_csv(args.template)
    queue = build_footprint_review_queue(
        rows,
        include_decided=args.include_decided,
        faction_contains=args.faction_contains,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_footprint_review_queue_csv(queue, args.output)

    priority_counts: dict[str, int] = {}
    for row in queue:
        priority = row.get("review_priority", "unknown") or "unknown"
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    print(f"Wrote {len(queue)} footprint review queue row(s) to {args.output}.")
    for priority, count in sorted(priority_counts.items()):
        print(f"- {priority}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
