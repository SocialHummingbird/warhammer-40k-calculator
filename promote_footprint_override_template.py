from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import (
    accepted_override_rows_from_template,
    load_footprint_override_template_csv,
    load_footprint_overrides_csv,
    summarize_footprint_override_template,
    write_footprint_overrides_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Promote reviewed rows from unit_footprint_override_template.csv into "
            "the manual unit_footprint_overrides.csv file."
        )
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("data/10e/latest/unit_footprint_override_template.csv"),
        help="Reviewed override-template CSV. Rows from the prioritized queue use the same review columns.",
    )
    parser.add_argument(
        "--queue",
        type=Path,
        help=(
            "Reviewed prioritized queue CSV to promote instead of --template. "
            "Use this when you reviewed unit_footprint_review_queue.csv directly."
        ),
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=Path("data/base_sizes/unit_footprint_overrides.csv"),
        help="Manual footprint override CSV to update.",
    )
    parser.add_argument("--unit-id", action="append", default=[], help="Promote only a specific unit id. Repeatable.")
    parser.add_argument("--limit", type=int, help="Maximum number of reviewed rows to promote.")
    parser.add_argument("--allow-invalid", action="store_true", help="Allow --apply even when reviewed rows are invalid.")
    parser.add_argument("--apply", action="store_true", help="Write promoted rows to the overrides CSV.")
    args = parser.parse_args()

    input_path = args.queue or args.template
    input_label = "queue" if args.queue else "template"
    if not input_path.exists():
        parser.error(f"{input_label} CSV not found: {input_path}")

    template_rows = load_footprint_override_template_csv(input_path)
    overrides = load_footprint_overrides_csv(args.overrides) if args.overrides.exists() else []
    unit_ids = set(args.unit_id) if args.unit_id else None
    summary = summarize_footprint_override_template(template_rows, overrides, unit_ids=unit_ids)
    counts = summary["counts"]
    print(
        f"{input_label.title()} review status: "
        f"{counts['accept_suggestion_ready']} suggestion-ready, "
        f"{counts['override_ready']} override-ready, "
        f"{counts['invalid']} invalid, "
        f"{counts['blank']} blank, "
        f"{counts['rejected']} rejected/skipped, "
        f"{counts['already_overridden']} already overridden."
    )
    issues = list(summary["issues"])
    if issues:
        print("Invalid reviewed row(s):")
        for issue in issues[:20]:
            print(
                f"- {issue.get('unit_id')}: {issue.get('unit_name')} "
                f"({issue.get('review_decision')}) - {issue.get('reason')}"
            )
        if len(issues) > 20:
            print(f"- {len(issues) - 20} additional invalid row(s) omitted.")
        if args.apply and not args.allow_invalid:
            print("Not applying because invalid reviewed rows are present. Fix them or pass --allow-invalid.")
            return 1

    selected = accepted_override_rows_from_template(
        template_rows,
        overrides,
        unit_ids=unit_ids,
        limit=args.limit,
    )

    action = "Would promote" if not args.apply else "Promoted"
    print(f"{action} {len(selected)} reviewed footprint override row(s).")
    for row in selected:
        base = row.get("base_size_text") or row.get("base_type") or "unknown base"
        print(f"- {row.get('unit_id')}: {row.get('unit_name')} -> {row.get('guide_unit_name')} ({base})")

    if args.apply and selected:
        args.overrides.parent.mkdir(parents=True, exist_ok=True)
        write_footprint_overrides_csv([*overrides, *selected], args.overrides)
        print(f"Wrote {len(overrides) + len(selected)} total override row(s) to {args.overrides}.")
    elif not args.apply:
        print(
            "Dry run only. Set review_decision to accept_suggestion or override, "
            "then re-run with --apply after reviewing the listed rows. "
            "You can pass --queue when promoting from unit_footprint_review_queue.csv."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
