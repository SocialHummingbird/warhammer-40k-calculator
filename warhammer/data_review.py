from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


REVIEW_FILE_LABELS = {
    "weapon_profile_review.csv": "Weapon profile review CSV",
    "suspicious_weapon_review.csv": "Suspicious weapon review CSV",
    "ability_profile_review.csv": "Ability profile review CSV",
    "ability_modifier_review.csv": "Ability modifier review CSV",
    "unit_variant_review.csv": "Duplicate unit name review CSV",
    "unit_weapon_coverage_review.csv": "Unit weapon coverage review CSV",
    "loadout_review.csv": "Loadout review CSV",
    "source_catalogue_review.csv": "Source catalogue review CSV",
    "schema_review.csv": "Schema review CSV",
    "edition_status.json": "Edition status JSON",
    "artifact_manifest.json": "Artifact manifest JSON",
    "profile_review.md": "Profile review summary",
    "update_report.md": "Update report",
}

MODEL_FILE_LABELS = {
    "matchup_centroid_model.md": "ML model audit report",
    "matchup_centroid_model.json": "ML model JSON",
}


def data_review_payload(data_dir: Optional[Path], *, edition: str = "10e", model_dir: Optional[Path] = None) -> Dict[str, Any]:
    if not data_dir:
        return {
            "audit_report": None,
            "import_diff": None,
            "metadata": None,
            "edition_status": None,
            "update_report": None,
            "profile_review": None,
            "model_audit": load_text_file(model_dir / "matchup_centroid_model.md") if model_dir else None,
            "review_files": [],
            "model_files": model_files(model_dir, href_prefix=f"/api/ml-model-files/{edition}/") if model_dir else [],
            "edition": edition,
        }
    return {
        "audit_report": load_json_file(data_dir / "audit_report.json"),
        "import_diff": load_json_file(data_dir / "import_diff.json"),
        "metadata": load_json_file(data_dir / "metadata.json"),
        "edition_status": load_json_file(data_dir / "edition_status.json"),
        "update_report": load_text_file(data_dir / "update_report.md"),
        "profile_review": load_text_file(data_dir / "profile_review.md"),
        "model_audit": load_text_file(model_dir / "matchup_centroid_model.md") if model_dir else None,
        "review_files": review_files(data_dir, href_prefix=f"/api/review-files/{edition}/"),
        "model_files": model_files(model_dir, href_prefix=f"/api/ml-model-files/{edition}/") if model_dir else [],
        "edition": edition,
    }


def load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_text_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return content or None


def source_info_from_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    revisions = metadata.get("source_revisions")
    source = revisions[0] if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict) else {}
    commit = source.get("commit") or ""
    return {
        "commit": commit,
        "commit_short": str(commit)[:12] if commit else "",
        "branch": source.get("branch") or metadata.get("github_ref") or "",
        "remote_origin": source.get("remote_origin") or metadata.get("github_repo") or "",
        "dirty": bool(source.get("dirty")),
        "generated_at": metadata.get("generated_at") or "",
        "rules_edition": metadata.get("rules_edition") or "10e",
        "supported_rules_editions": metadata.get("supported_rules_editions") or ["10e"],
    }


def review_files(data_dir: Path, *, href_prefix: str) -> list[Dict[str, Any]]:
    files = []
    for filename, label in REVIEW_FILE_LABELS.items():
        path = data_dir / filename
        if not path.exists():
            continue
        files.append(
            {
                "label": label,
                "filename": filename,
                "href": f"{href_prefix}{filename}",
                "bytes": path.stat().st_size,
            }
        )
    return files


def model_files(model_dir: Optional[Path], *, href_prefix: str) -> list[Dict[str, Any]]:
    if not model_dir:
        return []
    files = []
    for filename, label in MODEL_FILE_LABELS.items():
        path = model_dir / filename
        if not path.exists():
            continue
        files.append(
            {
                "label": label,
                "filename": filename,
                "href": f"{href_prefix}{filename}",
                "bytes": path.stat().st_size,
            }
        )
    return files


def review_file_content_type(filename: str) -> str:
    if filename.endswith(".csv"):
        return "text/csv; charset=utf-8"
    if filename.endswith(".json"):
        return "application/json; charset=utf-8"
    return "text/markdown; charset=utf-8"
