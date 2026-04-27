from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from warhammer.update_config import DEFAULT_EDITION, UpdatePaths, edition_latest_dir, edition_snapshot_dir


def build_update_arg_parser(
    *,
    paths: UpdatePaths,
    model_types: Sequence[str],
    default_edition: str = DEFAULT_EDITION,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update BSData source, regenerate CSVs, audit, diff, and local HTML")
    parser.add_argument("--repo-dir", type=Path, default=paths.repo_dir, help="Local BSData Git checkout")
    parser.add_argument("--csv-dir", type=Path, help="Output directory for generated CSVs")
    parser.add_argument("--snapshot-dir", type=Path, help="Directory for versioned snapshots")
    parser.add_argument("--remote", default="origin", help="Git remote to fetch from")
    parser.add_argument("--branch", default="main", help="Git branch to fast-forward")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch or merge the BSData checkout")
    parser.add_argument("--skip-ml", action="store_true", help="Do not regenerate ML feature/model artifacts")
    parser.add_argument("--ml-max-rows", type=int, default=10000, help="Maximum ML feature rows to export")
    parser.add_argument("--ml-strategy", choices=["sample", "sequential"], default="sample", help="ML feature row selection strategy")
    parser.add_argument("--ml-seed", type=int, default=40, help="Random seed for sampled ML feature exports")
    parser.add_argument("--ml-feature-set", choices=["pre_match", "full"], default="pre_match", help="ML feature set to train")
    parser.add_argument(
        "--ml-model-type",
        choices=sorted(model_types),
        default="centroid",
        help="ML model trainer to use during updates",
    )
    parser.add_argument("--skip-html", action="store_true", help="Do not regenerate the standalone local HTML")
    parser.add_argument("--skip-snapshot", action="store_true", help="Do not copy generated data into the edition snapshot directory")
    parser.add_argument(
        "--fail-on-review-issues",
        action="store_true",
        help="Exit non-zero after update when the generated data review gate finds blocking issues",
    )
    parser.add_argument(
        "--review-fail-on-warnings",
        action="store_true",
        help="Treat warning-severity review rows as blocking when used with --fail-on-review-issues",
    )
    parser.add_argument("--review-thresholds", type=Path, default=None, help="JSON file with accepted review-gate threshold counts")
    parser.add_argument("--write-review-thresholds", type=Path, default=None, help="Write current review-gate threshold counts after a successful refresh")
    parser.add_argument("--max-audit-warnings", type=int, default=None, help="Fail review gate when audit warnings exceed this count")
    parser.add_argument(
        "--max-suspicious-weapon-warnings",
        type=int,
        default=None,
        help="Fail review gate when suspicious weapon warnings exceed this count",
    )
    parser.add_argument(
        "--max-unit-profile-warnings",
        type=int,
        default=None,
        help="Fail review gate when unit profile warnings exceed this count",
    )
    parser.add_argument(
        "--max-loadout-warnings",
        type=int,
        default=None,
        help="Fail review gate when loadout review warnings exceed this count",
    )
    parser.add_argument("--max-no-weapon-units", type=int, default=None, help="Fail review gate when no-weapon units exceed this count")
    parser.add_argument("--edition", default=default_edition, help="Rules edition represented by the imported data")
    parser.add_argument(
        "--legacy-latest-dir",
        type=Path,
        default=paths.legacy_latest_dir,
        help="Compatibility mirror for older commands that still read data/latest",
    )
    parser.add_argument("--skip-legacy-latest", action="store_true", help="Do not update the data/latest compatibility mirror")
    return parser


def parse_update_args(
    argv: Sequence[str] | None,
    *,
    paths: UpdatePaths,
    model_types: Sequence[str],
    default_edition: str = DEFAULT_EDITION,
) -> argparse.Namespace:
    parser = build_update_arg_parser(paths=paths, model_types=model_types, default_edition=default_edition)
    args = parser.parse_args(argv)
    if args.csv_dir is None:
        args.csv_dir = edition_latest_dir(args.edition, data_dir=paths.data_dir, default_edition=default_edition)
    if args.snapshot_dir is None:
        args.snapshot_dir = edition_snapshot_dir(args.edition, data_dir=paths.data_dir, default_edition=default_edition)
    if args.ml_strategy == "sample" and args.ml_max_rows <= 0:
        parser.error("--ml-strategy sample requires --ml-max-rows to be positive")
    return args
