from __future__ import annotations

import sys
from collections.abc import Callable, Collection, Sequence
from pathlib import Path

from warhammer.edition_status import edition_dir_name
from warhammer.import_diff import csv_data_row_count
from warhammer.ml.artifacts import ml_artifact_paths
from warhammer.rules import available_rulesets


CommandRunner = Callable[[Sequence[str], Path | None], None]
MessageSink = Callable[[str], None]


def refresh_ml_artifacts(
    *,
    csv_dir: Path,
    edition: str,
    max_rows: int,
    strategy: str,
    seed: int,
    feature_set: str,
    model_type: str,
    ml_root: Path,
    model_root: Path,
    project_root: Path,
    command_runner: CommandRunner,
    python_executable: str = sys.executable,
    supported_rulesets: Collection[str] | None = None,
    message_sink: MessageSink | None = None,
) -> dict[str, object] | None:
    resolved_edition = edition_dir_name(edition)
    supported = set(supported_rulesets) if supported_rulesets is not None else available_rulesets()
    if resolved_edition not in supported:
        if message_sink is not None:
            message_sink(f"Skipping ML refresh for unsupported rules edition: {resolved_edition}")
        return None

    paths = ml_artifact_paths(
        resolved_edition,
        ml_root=ml_root,
        model_root=model_root,
        model_type=model_type,
    )
    feature_path = paths.feature_path
    model_path = paths.model_path

    command_runner(
        [
            python_executable,
            "export_ml_features.py",
            "--csv-dir",
            str(csv_dir),
            "--output",
            str(feature_path),
            "--edition",
            resolved_edition,
            "--max-rows",
            str(max_rows),
            "--strategy",
            strategy,
            "--seed",
            str(seed),
        ],
        project_root,
    )
    command_runner(
        [
            python_executable,
            "train_ml_model.py",
            "--features",
            str(feature_path),
            "--output",
            str(model_path),
            "--feature-set",
            feature_set,
            "--model-type",
            model_type,
            "--seed",
            str(seed),
        ],
        project_root,
    )
    command_runner(
        [
            python_executable,
            "compare_ml_models.py",
            "--features",
            str(feature_path),
            "--feature-set",
            feature_set,
            "--seed",
            str(seed),
            "--output",
            str(paths.comparison_path),
        ],
        project_root,
    )
    command_runner(
        [
            python_executable,
            "verify_ml_artifacts.py",
            "--features",
            str(feature_path),
            "--model",
            str(model_path),
        ],
        project_root,
    )
    return {
        "edition": resolved_edition,
        "feature_path": feature_path,
        "model_path": model_path,
        "audit_path": paths.audit_path,
        "comparison_path": paths.comparison_path,
        "feature_rows": csv_data_row_count(feature_path),
        "feature_set": feature_set,
        "model_type": model_type,
    }
