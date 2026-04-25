#!/usr/bin/env python3
"""Export deterministic matchup feature rows for future advisory ML models."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.ml.features import iter_matchup_feature_rows, sample_matchup_feature_rows, write_matchup_feature_csv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "10e" / "latest"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "ml" / "10e" / "matchup_training_rows.csv"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    units = load_units_from_directory(args.csv_dir)
    modes = tuple(mode.strip().lower() for mode in args.modes.split(",") if mode.strip())
    if args.strategy == "sample":
        if args.max_rows is None:
            raise SystemExit("--strategy sample requires a positive --max-rows value")
        rows = sample_matchup_feature_rows(
            units.values(),
            edition=args.edition,
            modes=modes,
            row_count=args.max_rows,
            seed=args.seed,
        )
    else:
        rows = iter_matchup_feature_rows(
            units.values(),
            edition=args.edition,
            modes=modes,
            max_rows=args.max_rows,
        )
    count = write_matchup_feature_csv(rows, args.output)
    print(f"Wrote {count} matchup feature rows to {args.output}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export deterministic Warhammer matchup feature rows")
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR, help="Directory containing imported CSV data")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV file to write")
    parser.add_argument("--edition", default="10e", help="Rules edition to evaluate")
    parser.add_argument("--modes", default="ranged,melee", help="Comma-separated modes to export")
    parser.add_argument("--max-rows", type=int, default=10000, help="Maximum rows to emit; use 0 for no limit")
    parser.add_argument("--strategy", choices=["sample", "sequential"], default="sample", help="Row selection strategy")
    parser.add_argument("--seed", type=int, default=40, help="Random seed used by --strategy sample")
    args = parser.parse_args(argv)
    if args.max_rows is not None and args.max_rows <= 0:
        args.max_rows = None
    return args


if __name__ == "__main__":
    raise SystemExit(main())
