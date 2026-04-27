#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from warhammer.release_verification import build_release_checks, run_release_checks


PROJECT_ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the release verification suite.")
    parser.add_argument(
        "--data-dir",
        action="append",
        type=Path,
        dest="data_dirs",
        help="Generated data directory to verify. May be passed more than once.",
    )
    parser.add_argument("--review-data-dir", type=Path, default=PROJECT_ROOT / "data" / "10e" / "latest")
    parser.add_argument("--thresholds", type=Path, default=PROJECT_ROOT / "config" / "review_thresholds_10e.json")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-review-gate", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_dirs = args.data_dirs or [
        PROJECT_ROOT / "data" / "10e" / "latest",
        PROJECT_ROOT / "data" / "latest",
        PROJECT_ROOT / "data" / "10e" / "snapshots" / "32b4525d9f69",
    ]
    thresholds = args.thresholds if args.thresholds and args.thresholds.exists() else None
    checks = build_release_checks(
        python_executable=sys.executable,
        data_dirs=data_dirs,
        review_data_dir=args.review_data_dir,
        thresholds=thresholds,
        skip_tests=args.skip_tests,
        skip_review_gate=args.skip_review_gate,
    )
    return run_release_checks(checks, project_root=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
