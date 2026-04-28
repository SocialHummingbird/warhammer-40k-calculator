#!/usr/bin/env python3
"""Export or validate a human labelling queue for advisory ML training."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from warhammer.ml.label_review import build_label_review_rows, validate_label_review_rows, write_label_review_csv
from warhammer.ml.model import read_feature_csv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_training_rows.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_label_queue.csv"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.validate_labels:
        with args.validate_labels.open("r", encoding="utf-8", newline="") as handle:
            summary = validate_label_review_rows(csv.DictReader(handle), key_columns=args.label_key_columns)
        print(json.dumps(summary, indent=2))
        return 0 if summary["valid"] else 1

    rows = build_label_review_rows(
        read_feature_csv(args.features),
        limit=args.limit,
        strategy=args.strategy,
        seed=args.seed,
    )
    count = write_label_review_csv(rows, args.output)
    print(f"Wrote {count} ML label review rows to {args.output}")
    print("Fill winner_label with one of: attacker, defender, close")
    print(
        "Retrain with: "
        f"python train_ml_model.py --features {args.features} --labels {args.output} "
        "--label-key-columns edition mode attacker_id defender_id"
    )
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export matchup rows for human ML label review")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Feature CSV produced by export_ml_features.py")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Label queue CSV to write")
    parser.add_argument("--limit", type=int, default=200, help="Maximum review rows to export; use -1 for all rows")
    parser.add_argument(
        "--strategy",
        choices=["uncertain", "random", "sequential"],
        default="uncertain",
        help="How to choose rows for review. 'uncertain' prioritizes close/low-confidence rows.",
    )
    parser.add_argument("--seed", type=int, default=40, help="Random seed used by --strategy random")
    parser.add_argument("--validate-labels", type=Path, default=None, help="Validate an existing filled label CSV instead of exporting")
    parser.add_argument(
        "--label-key-columns",
        nargs="+",
        default=["edition", "mode", "attacker_id", "defender_id"],
        help="Columns used to identify duplicate/missing label rows during validation.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        args.limit = None
    return args


if __name__ == "__main__":
    raise SystemExit(main())
