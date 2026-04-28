from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import shutil
from typing import Optional, Sequence


DATA_ARTIFACTS: tuple[str, ...] = (
    "units.csv",
    "weapons.csv",
    "abilities.csv",
    "keywords.csv",
    "unit_keywords.csv",
    "metadata.json",
    "edition_status.json",
    "edition_readiness.md",
    "audit_report.json",
    "schema_review.csv",
    "import_diff.json",
    "update_report.md",
    "weapon_profile_review.csv",
    "suspicious_weapon_review.csv",
    "unit_profile_review.csv",
    "ability_profile_review.csv",
    "ability_modifier_review.csv",
    "unit_variant_review.csv",
    "unit_weapon_coverage_review.csv",
    "loadout_review.csv",
    "source_catalogue_review.csv",
    "base_size_guide.csv",
    "unit_footprint_overrides.csv",
    "unit_footprint_rejections.csv",
    "unit_footprint_override_template.csv",
    "unit_footprint_review_queue.csv",
    "unit_footprints.csv",
    "unit_footprint_review.csv",
    "unit_footprint_review.md",
    "unit_footprint_suggestions.csv",
    "profile_review.md",
)

ARTIFACTS: tuple[str, ...] = (*DATA_ARTIFACTS, "artifact_manifest.json")


def snapshot_name_from_source(source_after: dict[str, object], *, timestamp: datetime | None = None) -> str:
    commit = str(source_after.get("commit") or "unknown")
    if commit and commit != "unknown":
        return commit[:12]
    return (timestamp or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


def copy_artifacts(source_dir: Path, target_dir: Path, *, artifacts: Sequence[str] = ARTIFACTS) -> None:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        source = Path(source_dir) / artifact
        if source.exists():
            shutil.copy2(source, target / artifact)


def write_snapshot(
    csv_dir: Path,
    snapshot_dir: Path,
    source_after: dict[str, object],
    *,
    artifacts: Sequence[str] = ARTIFACTS,
) -> Path:
    target = Path(snapshot_dir) / snapshot_name_from_source(source_after)
    copy_artifacts(csv_dir, target, artifacts=artifacts)
    return target


def build_artifact_manifest(
    csv_dir: Path,
    source_after: dict[str, object],
    *,
    linked_ml_artifacts: Optional[dict[str, object]] = None,
    data_artifacts: Sequence[str] = DATA_ARTIFACTS,
    project_root: Path | None = None,
) -> dict[str, object]:
    artifacts = {}
    for filename in data_artifacts:
        path = Path(csv_dir) / filename
        if not path.exists():
            continue
        artifacts[filename] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": source_after,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "linked_ml_artifacts": linked_ml_artifact_payload(
            linked_ml_artifacts,
            base_dir=Path(csv_dir),
            project_root=project_root,
        ),
    }


def linked_ml_artifact_payload(
    payload: Optional[dict[str, object]],
    *,
    base_dir: Path,
    project_root: Path | None = None,
) -> dict[str, object]:
    if not payload:
        return {}
    linked: dict[str, object] = {
        "edition": payload.get("edition", ""),
        "feature_set": payload.get("feature_set", ""),
        "model_type": payload.get("model_type", ""),
        "feature_rows": payload.get("feature_rows", 0),
        "artifacts": {},
    }
    artifacts: dict[str, dict[str, object]] = {}
    for key, path_key in (
        ("feature_csv", "feature_path"),
        ("model_json", "model_path"),
        ("model_audit", "audit_path"),
        ("model_comparison", "comparison_path"),
    ):
        raw_path = payload.get(path_key)
        if not raw_path:
            continue
        path = Path(str(raw_path))
        if not path.exists():
            continue
        artifacts[key] = {
            "path": portable_manifest_path(path, base_dir=base_dir, project_root=project_root),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    linked["artifacts"] = artifacts
    return linked


def portable_manifest_path(path: Path, *, base_dir: Path, project_root: Path | None = None) -> str:
    try:
        return Path(path).resolve().relative_to(Path(base_dir).resolve()).as_posix()
    except ValueError:
        pass
    if project_root is not None:
        try:
            return Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix()
        except ValueError:
            pass
    return str(Path(path).resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
