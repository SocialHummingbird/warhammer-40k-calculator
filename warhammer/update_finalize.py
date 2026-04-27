from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from warhammer.artifact_manifest import build_artifact_manifest, copy_artifacts, write_snapshot
from warhammer.file_io import write_json_file
from warhammer.update_commands import local_html_export_command


CommandRunner = Callable[[Sequence[str], Path | None], None]


@dataclass(frozen=True)
class FinalizedArtifacts:
    snapshot_path: Path | None


def finalize_update_artifacts(
    *,
    csv_dir: Path,
    source_after: dict[str, object],
    ml_artifacts: dict[str, object] | None,
    skip_html: bool,
    skip_snapshot: bool,
    snapshot_dir: Path,
    legacy_latest_dir: Path | None,
    skip_legacy_latest: bool,
    project_root: Path,
    command_runner: CommandRunner,
    python_executable: str = sys.executable,
) -> FinalizedArtifacts:
    csv_path = Path(csv_dir)
    write_json_file(
        csv_path / "artifact_manifest.json",
        build_artifact_manifest(
            csv_path,
            source_after,
            linked_ml_artifacts=ml_artifacts,
            project_root=project_root,
        ),
    )

    if not skip_html:
        command_runner(
            local_html_export_command(
                csv_dir=csv_path,
                ml_artifacts=ml_artifacts,
                python_executable=python_executable,
            ),
            project_root,
        )

    snapshot_path = None
    if not skip_snapshot:
        snapshot_path = write_snapshot(csv_path, snapshot_dir, source_after)

    if legacy_latest_dir and csv_path != Path(legacy_latest_dir) and not skip_legacy_latest:
        copy_artifacts(csv_path, Path(legacy_latest_dir))

    return FinalizedArtifacts(snapshot_path=snapshot_path)
