#!/usr/bin/env python3
"""Compare advisory ML model types on the same feature CSV without writing model artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from warhammer.ml.comparison import compare_model_types, render_comparison_report
from warhammer.ml.model import FEATURE_COLUMN_SETS, MODEL_TYPES, read_feature_csv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_training_rows.csv"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    rows = read_feature_csv(args.features)
    results = compare_model_types(
        rows,
        model_types=args.model_type,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
        feature_set=args.feature_set,
    )
    if args.json:
        output = json.dumps({"features": str(args.features), "results": results}, indent=2)
    else:
        output = render_comparison_report(results)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote ML model comparison to {args.output}")
    else:
        print(output)
    return 0 if all(row["ok"] for row in results) else 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare advisory ML model types on one feature CSV")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Feature CSV produced by export_ml_features.py")
    parser.add_argument(
        "--model-type",
        action="append",
        choices=sorted(MODEL_TYPES),
        default=None,
        help="Model trainer to include. Repeat to compare several. Defaults to centroid and logistic_regression.",
    )
    parser.add_argument(
        "--feature-set",
        choices=sorted(FEATURE_COLUMN_SETS),
        default="pre_match",
        help="Named feature set to compare with.",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.2, help="Fraction of rows reserved for validation")
    parser.add_argument("--seed", type=int, default=40, help="Shuffle seed for train/validation split")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--output", type=Path, help="Optional file to write instead of printing the report")
    args = parser.parse_args(argv)
    args.model_type = args.model_type or ["centroid", "logistic_regression"]
    return args


if __name__ == "__main__":
    raise SystemExit(main())
