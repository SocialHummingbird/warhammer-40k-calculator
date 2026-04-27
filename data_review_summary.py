from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from warhammer.data_review import data_review_payload
from warhammer.data_review_summary import (
    build_current_review_thresholds,
    build_data_review_gate_failures,
    build_review_threshold_summary_lines,
    normalize_review_thresholds,
    render_data_review_summary,
)
from warhammer.file_io import read_json_object, write_json_file


PROJECT_ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarise generated Warhammer data review artifacts.")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "10e" / "latest")
    parser.add_argument("--edition", default="10e")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print the full review payload as JSON instead of text.")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit non-zero when blocking audit issues are present.")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Treat warning-severity audit rows as blocking when used with --fail-on-issues.",
    )
    parser.add_argument("--max-audit-warnings", type=int, default=None, help="Fail when audit warnings exceed this count.")
    parser.add_argument(
        "--max-suspicious-weapon-warnings",
        type=int,
        default=None,
        help="Fail when suspicious weapon warnings exceed this count.",
    )
    parser.add_argument(
        "--max-unit-profile-warnings",
        type=int,
        default=None,
        help="Fail when unit profile warnings exceed this count.",
    )
    parser.add_argument(
        "--max-loadout-warnings",
        type=int,
        default=None,
        help="Fail when loadout review warnings exceed this count.",
    )
    parser.add_argument("--max-no-weapon-units", type=int, default=None, help="Fail when no-weapon unit count exceeds this count.")
    parser.add_argument("--thresholds", type=Path, default=None, help="JSON file with accepted review-gate threshold counts.")
    parser.add_argument("--write-thresholds", type=Path, default=None, help="Write current review-gate threshold counts to this JSON file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    model_dir = args.model_dir or (PROJECT_ROOT / "models" / args.edition)
    payload = data_review_payload(args.data_dir, edition=args.edition, model_dir=model_dir, model_path=args.model)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_data_review_summary(payload), end="")
    if args.write_thresholds:
        write_json_file(args.write_thresholds, build_current_review_thresholds(payload))
        print(f"Wrote review thresholds to {args.write_thresholds}")
    if not args.fail_on_issues:
        return 0
    thresholds = normalize_review_thresholds(read_json_object(args.thresholds)) if args.thresholds else {}
    thresholds.update({key: value for key, value in _threshold_overrides(args).items() if value is not None})
    if thresholds and not args.json:
        for line in build_review_threshold_summary_lines(thresholds):
            print(line)
    failures = build_data_review_gate_failures(
        payload,
        fail_on_warnings=args.fail_on_warnings,
        thresholds=thresholds,
    )
    if not failures:
        if not args.json:
            print("Data review gate passed.")
        return 0
    print("Data review gate failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    return 1


def _threshold_overrides(args: argparse.Namespace) -> dict[str, int | None]:
    return {
        "audit_warnings": args.max_audit_warnings,
        "suspicious_weapon_warnings": args.max_suspicious_weapon_warnings,
        "unit_profile_warnings": args.max_unit_profile_warnings,
        "loadout_warnings": args.max_loadout_warnings,
        "no_weapon_units": args.max_no_weapon_units,
    }


if __name__ == "__main__":
    raise SystemExit(main())
