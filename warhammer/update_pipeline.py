from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from warhammer.artifact_manifest import copy_artifacts
from warhammer.base_sizes import generate_unit_footprint_artifacts
from warhammer.command_runner import run_command
from warhammer.data_review import data_review_payload
from warhammer.data_review_summary import (
    build_current_review_thresholds,
    build_data_review_gate_failures,
    build_review_threshold_summary_lines,
    normalize_review_thresholds,
)
from warhammer.footprint_review import write_footprint_review_report
from warhammer.file_io import read_json_object, write_json_file
from warhammer.import_diff import build_import_diff, load_tables
from warhammer.ml.model import MODEL_TYPES
from warhammer.ml.update import refresh_ml_artifacts
from warhammer.source_update import fast_forward_source, source_metadata
from warhammer.update_args import parse_update_args
from warhammer.update_commands import bsdata_import_command
from warhammer.update_config import DEFAULT_EDITION, default_update_paths
from warhammer.update_finalize import finalize_update_artifacts
from warhammer.update_reports import write_generated_reports
from warhammer.update_summary import print_update_summary


CommandRunner = Callable[[Sequence[str], Path | None], None]
MessageSink = Callable[[str], None]


def run_update(
    argv: Sequence[str] | None,
    *,
    project_root: Path,
    python_executable: str = sys.executable,
    command_runner: CommandRunner | None = None,
    message_sink: MessageSink = print,
) -> int:
    paths = default_update_paths(project_root)
    runner = command_runner or (lambda command, cwd=None: run_command(command, cwd=cwd))
    args = parse_update_args(argv, paths=paths, model_types=sorted(MODEL_TYPES), default_edition=DEFAULT_EDITION)
    repo_dir = args.repo_dir.resolve()
    csv_dir = args.csv_dir.resolve()
    legacy_latest_dir = args.legacy_latest_dir.resolve() if args.legacy_latest_dir else None
    review_thresholds = _review_gate_thresholds(args) if args.fail_on_review_issues else {}

    if legacy_latest_dir and csv_dir != legacy_latest_dir and not csv_dir.exists() and legacy_latest_dir.exists():
        copy_artifacts(legacy_latest_dir, csv_dir)

    before = load_tables(csv_dir)
    source_before = source_metadata(repo_dir)

    if not args.skip_fetch:
        fast_forward_source(repo_dir, remote=args.remote, branch=args.branch, command_runner=lambda command: runner(command, None))

    source_after = source_metadata(repo_dir)

    runner(
        bsdata_import_command(
            repo_dir=repo_dir,
            csv_dir=csv_dir,
            edition=args.edition,
            python_executable=python_executable,
        ),
        project_root,
    )
    _refresh_unit_footprints(csv_dir=csv_dir, project_root=project_root, message_sink=message_sink)

    after = load_tables(csv_dir)
    diff = build_import_diff(before, after, source_before=source_before, source_after=source_after)
    write_json_file(csv_dir / "import_diff.json", diff)

    reports = write_generated_reports(
        csv_dir=csv_dir,
        edition=args.edition,
        source_after=source_after,
        diff=diff,
        project_root=project_root,
        review_thresholds=review_thresholds,
    )

    ml_artifacts = None
    if not args.skip_ml:
        ml_artifacts = refresh_ml_artifacts(
            csv_dir=csv_dir,
            edition=args.edition,
            max_rows=args.ml_max_rows,
            strategy=args.ml_strategy,
            seed=args.ml_seed,
            feature_set=args.ml_feature_set,
            model_type=args.ml_model_type,
            label_overrides_path=args.ml_labels,
            label_key_columns=args.ml_label_key_columns,
            ml_root=paths.ml_dir,
            model_root=paths.model_dir,
            project_root=project_root,
            command_runner=lambda command, cwd: runner(command, cwd),
            python_executable=python_executable,
            message_sink=message_sink,
        )

    finalized = finalize_update_artifacts(
        csv_dir=csv_dir,
        source_after=source_after,
        ml_artifacts=ml_artifacts,
        skip_html=args.skip_html,
        skip_snapshot=args.skip_snapshot,
        snapshot_dir=args.snapshot_dir.resolve(),
        legacy_latest_dir=legacy_latest_dir,
        skip_legacy_latest=args.skip_legacy_latest,
        project_root=project_root,
        command_runner=lambda command, cwd: runner(command, cwd),
        python_executable=python_executable,
    )

    print_update_summary(
        source_before,
        source_after,
        diff,
        reports.audit_report,
        finalized.snapshot_path,
        reports.profile_review_counts,
        reports.schema_review_rows,
        ml_artifacts,
    )
    if args.fail_on_review_issues or args.write_review_thresholds:
        selected_model_path = ml_artifacts.get("model_path") if ml_artifacts else None
        payload = data_review_payload(
            csv_dir,
            edition=args.edition,
            model_dir=paths.model_dir / args.edition,
            model_path=selected_model_path if isinstance(selected_model_path, Path) else None,
        )
    else:
        payload = None

    if args.fail_on_review_issues:
        for line in build_review_threshold_summary_lines(review_thresholds):
            message_sink(line)
        failures = build_data_review_gate_failures(
            payload or {},
            fail_on_warnings=args.review_fail_on_warnings,
            thresholds=review_thresholds,
        )
        if failures:
            message_sink("Data review gate failed:")
            for failure in failures:
                message_sink(f"- {failure}")
            return 1
        message_sink("Data review gate passed.")
    if args.write_review_thresholds:
        threshold_path = args.write_review_thresholds.resolve()
        write_json_file(threshold_path, build_current_review_thresholds(payload or {}))
        message_sink(f"Wrote review thresholds to {threshold_path}")
    return 0


def _refresh_unit_footprints(*, csv_dir: Path, project_root: Path, message_sink: MessageSink) -> None:
    base_guide = project_root / "data" / "base_sizes" / "base_size_guide.csv"
    units_csv = csv_dir / "units.csv"
    if not base_guide.exists() or not units_csv.exists():
        return
    (csv_dir / "base_size_guide.csv").write_bytes(base_guide.read_bytes())
    overrides = project_root / "data" / "base_sizes" / "unit_footprint_overrides.csv"
    if overrides.exists():
        (csv_dir / "unit_footprint_overrides.csv").write_bytes(overrides.read_bytes())
    rejections = project_root / "data" / "base_sizes" / "unit_footprint_rejections.csv"
    if rejections.exists():
        (csv_dir / "unit_footprint_rejections.csv").write_bytes(rejections.read_bytes())
    summary = generate_unit_footprint_artifacts(
        units_csv=units_csv,
        base_size_csv=base_guide,
        unit_footprints_csv=csv_dir / "unit_footprints.csv",
        review_csv=csv_dir / "unit_footprint_review.csv",
        overrides_csv=overrides if overrides.exists() else None,
        rejections_csv=rejections if rejections.exists() else None,
        suggestions_csv=csv_dir / "unit_footprint_suggestions.csv",
        override_template_csv=csv_dir / "unit_footprint_override_template.csv",
        review_queue_csv=csv_dir / "unit_footprint_review_queue.csv",
    )
    write_footprint_review_report(csv_dir)
    message_sink(
        "Updated unit footprint artifacts: "
        f"{summary['footprints']} units, {summary['review_rows']} review rows, "
        f"{summary['suggestions']} suggestions."
    )


def _review_gate_thresholds(args: object) -> dict[str, int]:
    thresholds = normalize_review_thresholds(read_json_object(args.review_thresholds)) if args.review_thresholds else {}
    thresholds.update(
        {
            key: value
            for key, value in {
                "audit_warnings": args.max_audit_warnings,
                "suspicious_weapon_warnings": args.max_suspicious_weapon_warnings,
                "unit_profile_warnings": args.max_unit_profile_warnings,
                "loadout_warnings": args.max_loadout_warnings,
                "no_weapon_units": args.max_no_weapon_units,
            }.items()
            if value is not None
        }
    )
    return thresholds
