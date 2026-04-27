from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from warhammer.edition_status import edition_dir_name


DEFAULT_EDITION = "10e"


@dataclass(frozen=True)
class UpdatePaths:
    project_root: Path
    data_dir: Path
    repo_dir: Path
    legacy_latest_dir: Path
    ml_dir: Path
    model_dir: Path


def default_update_paths(project_root: Path) -> UpdatePaths:
    root = Path(project_root)
    data_dir = root / "data"
    return UpdatePaths(
        project_root=root,
        data_dir=data_dir,
        repo_dir=data_dir / "wh40k-10e",
        legacy_latest_dir=data_dir / "latest",
        ml_dir=data_dir / "ml",
        model_dir=root / "models",
    )


def edition_latest_dir(edition: str, *, data_dir: Path, default_edition: str = DEFAULT_EDITION) -> Path:
    return Path(data_dir) / edition_dir_name(edition, default=default_edition) / "latest"


def edition_snapshot_dir(edition: str, *, data_dir: Path, default_edition: str = DEFAULT_EDITION) -> Path:
    return Path(data_dir) / edition_dir_name(edition, default=default_edition) / "snapshots"
