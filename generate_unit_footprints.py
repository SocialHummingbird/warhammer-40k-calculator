from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import generate_unit_footprint_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Match imported units to official base-size guide rows.")
    parser.add_argument("--csv-dir", type=Path, default=Path("data/10e/latest"))
    parser.add_argument("--base-guide", type=Path, default=Path("data/base_sizes/base_size_guide.csv"))
    parser.add_argument("--unit-footprints", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--overrides", type=Path, default=Path("data/base_sizes/unit_footprint_overrides.csv"))
    parser.add_argument("--rejections", type=Path, default=Path("data/base_sizes/unit_footprint_rejections.csv"))
    parser.add_argument("--suggestions", type=Path)
    parser.add_argument("--override-template", type=Path)
    parser.add_argument("--review-queue", type=Path)
    args = parser.parse_args()

    units_csv = args.csv_dir / "units.csv"
    if not units_csv.exists():
        parser.error(f"units.csv not found: {units_csv}")
    if not args.base_guide.exists():
        parser.error(f"base-size guide CSV not found: {args.base_guide}. Run import_base_sizes.py first.")

    unit_footprints = args.unit_footprints or (args.csv_dir / "unit_footprints.csv")
    review = args.review or (args.csv_dir / "unit_footprint_review.csv")
    suggestions = args.suggestions or (args.csv_dir / "unit_footprint_suggestions.csv")
    override_template = args.override_template or (args.csv_dir / "unit_footprint_override_template.csv")
    review_queue = args.review_queue or (args.csv_dir / "unit_footprint_review_queue.csv")
    summary = generate_unit_footprint_artifacts(
        units_csv=units_csv,
        base_size_csv=args.base_guide,
        unit_footprints_csv=unit_footprints,
        review_csv=review,
        overrides_csv=args.overrides,
        rejections_csv=args.rejections,
        suggestions_csv=suggestions,
        override_template_csv=override_template,
        review_queue_csv=review_queue,
    )
    print(
        "Wrote unit footprints: "
        f"{summary['footprints']} units, {summary['guide_rows']} guide rows, "
        f"{summary['review_rows']} review rows, {summary['suggestions']} suggestions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
