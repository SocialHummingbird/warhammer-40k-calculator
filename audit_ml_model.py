#!/usr/bin/env python3
"""Write a Markdown audit report for a saved advisory ML model."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from warhammer.ml.audit import write_model_audit_report
from warhammer.ml.model import load_model, read_feature_csv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_training_rows.csv"
DEFAULT_MODEL = PROJECT_ROOT / "models" / "10e" / "matchup_centroid_model.json"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    model = load_model(args.model)
    feature_rows = read_feature_csv(args.features) if args.features.exists() else []
    output = args.output or args.model.with_suffix(".md")
    write_model_audit_report(
        model,
        output,
        feature_rows=feature_rows,
        model_path=args.model,
        feature_path=args.features if args.features.exists() else None,
    )
    print(f"Wrote ML model audit report to {output}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a saved Warhammer advisory ML model")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Model JSON file to audit")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Feature CSV used to train the model")
    parser.add_argument("--output", type=Path, default=None, help="Markdown report to write")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
