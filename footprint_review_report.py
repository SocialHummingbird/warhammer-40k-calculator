from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.footprint_review import render_footprint_review_report, write_footprint_review_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Markdown review report for unit footprint matching.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/10e/latest"))
    parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")
    parser.add_argument(
        "--row-limit",
        type=int,
        default=30,
        help="Maximum number of high-confidence suggestion and queue rows to include in report tables.",
    )
    parser.add_argument(
        "--high-score-threshold",
        type=float,
        default=0.8,
        help="Minimum rank-1 suggestion score to include in the high-confidence suggestion table.",
    )
    args = parser.parse_args()

    if args.output:
        output = write_footprint_review_report(
            args.data_dir,
            args.output,
            high_score_threshold=args.high_score_threshold,
            row_limit=args.row_limit,
        )
        print(f"Wrote {output}")
    else:
        print(
            render_footprint_review_report(
                args.data_dir,
                high_score_threshold=args.high_score_threshold,
                row_limit=args.row_limit,
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
