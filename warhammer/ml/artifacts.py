from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from warhammer.edition_status import edition_dir_name


@dataclass(frozen=True)
class MlArtifactPaths:
    edition: str
    feature_path: Path
    model_path: Path
    audit_path: Path
    comparison_path: Path


def ml_model_filename(model_type: str) -> str:
    normalized = str(model_type or "centroid").strip().lower().replace("-", "_")
    if normalized in {"centroid", "nearest_centroid"}:
        return "matchup_centroid_model.json"
    if normalized == "logistic_regression":
        return "matchup_logistic_model.json"
    return f"matchup_{normalized}_model.json"


def ml_feature_path(edition: str, *, ml_root: Path) -> Path:
    return Path(ml_root) / edition_dir_name(edition) / "matchup_training_rows.csv"


def ml_model_path(edition: str, *, model_root: Path, model_type: str = "centroid") -> Path:
    return Path(model_root) / edition_dir_name(edition) / ml_model_filename(model_type)


def ml_artifact_paths(
    edition: str,
    *,
    ml_root: Path,
    model_root: Path,
    model_type: str = "centroid",
) -> MlArtifactPaths:
    resolved_edition = edition_dir_name(edition)
    feature_path = ml_feature_path(resolved_edition, ml_root=ml_root)
    model_path = ml_model_path(resolved_edition, model_root=model_root, model_type=model_type)
    return MlArtifactPaths(
        edition=resolved_edition,
        feature_path=feature_path,
        model_path=model_path,
        audit_path=model_path.with_suffix(".md"),
        comparison_path=model_path.parent / "model_comparison.md",
    )
