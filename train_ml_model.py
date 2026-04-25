#!/usr/bin/env python3
"""Train a dependency-free baseline advisory model from matchup feature rows."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from warhammer.ml.audit import write_model_audit_report
from warhammer.ml.model import FEATURE_COLUMN_SETS, read_feature_csv, train_from_csv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_training_rows.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "models" / "10e" / "matchup_centroid_model.json"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    model = train_from_csv(
        args.features,
        args.output,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
        feature_set=args.feature_set,
    )
    validation = model["validation"]
    accuracy = validation["accuracy"]
    accuracy_text = "n/a" if accuracy is None else f"{accuracy:.3f}"
    print(f"Wrote {model['model_type']} to {args.output}")
    print(f"Labels: {', '.join(model['labels'])}")
    print(f"Training rows: {model['training_rows']}; validation rows: {model['validation_rows']}")
    print(f"Validation accuracy: {accuracy_text} ({validation['correct']}/{validation['total']})")
    if not args.no_report:
        report_path = args.report or args.output.with_suffix(".md")
        write_model_audit_report(
            model,
            report_path,
            feature_rows=read_feature_csv(args.features),
            model_path=args.output,
            feature_path=args.features,
        )
        print(f"Wrote ML audit report to {report_path}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a baseline advisory matchup model")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Feature CSV produced by export_ml_features.py")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Model JSON file to write")
    parser.add_argument("--report", type=Path, default=None, help="Markdown audit report to write")
    parser.add_argument("--no-report", action="store_true", help="Skip writing the Markdown audit report")
    parser.add_argument(
        "--feature-set",
        choices=sorted(FEATURE_COLUMN_SETS),
        default="pre_match",
        help="Named feature set to train with. 'pre_match' excludes calculator output metrics.",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.2, help="Fraction of rows reserved for validation")
    parser.add_argument("--seed", type=int, default=40, help="Shuffle seed for train/validation split")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
