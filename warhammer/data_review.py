from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any, Dict, Optional

from warhammer.base_sizes import summarize_footprint_override_template


REVIEW_FILE_LABELS = {
    "weapon_profile_review.csv": "Weapon profile review CSV",
    "suspicious_weapon_review.csv": "Suspicious weapon review CSV",
    "unit_profile_review.csv": "Unit profile review CSV",
    "ability_profile_review.csv": "Ability profile review CSV",
    "ability_modifier_review.csv": "Ability modifier review CSV",
    "unit_variant_review.csv": "Duplicate unit name review CSV",
    "unit_weapon_coverage_review.csv": "Unit weapon coverage review CSV",
    "loadout_review.csv": "Loadout review CSV",
    "source_catalogue_review.csv": "Source catalogue review CSV",
    "base_size_guide.csv": "Official base-size guide CSV",
    "unit_footprint_overrides.csv": "Unit footprint manual overrides CSV",
    "unit_footprint_rejections.csv": "Unit footprint rejected suggestions CSV",
    "unit_footprint_override_template.csv": "Unit footprint override template CSV",
    "unit_footprint_review_queue.csv": "Unit footprint prioritized review queue CSV",
    "unit_footprints.csv": "Unit footprint CSV",
    "unit_footprint_review.csv": "Unit footprint review CSV",
    "unit_footprint_review.md": "Unit footprint review report",
    "unit_footprint_suggestions.csv": "Unit footprint suggestions CSV",
    "schema_review.csv": "Schema review CSV",
    "edition_status.json": "Edition status JSON",
    "edition_readiness.md": "Edition readiness report",
    "artifact_manifest.json": "Artifact manifest JSON",
    "profile_review.md": "Profile review summary",
    "update_report.md": "Update report",
}

MODEL_FILE_LABELS = {
    "matchup_centroid_model.md": "ML model audit report",
    "matchup_centroid_model.json": "ML model JSON",
    "matchup_logistic_model.md": "ML logistic model audit report",
    "matchup_logistic_model.json": "ML logistic model JSON",
    "model_comparison.md": "ML model comparison report",
}


def data_review_payload(
    data_dir: Optional[Path],
    *,
    edition: str = "10e",
    model_dir: Optional[Path] = None,
    model_path: Optional[Path] = None,
) -> Dict[str, Any]:
    model_audit_path = model_path.with_suffix(".md") if model_path else (model_dir / "matchup_centroid_model.md" if model_dir else None)
    model_comparison_path = model_dir / "model_comparison.md" if model_dir else None
    if not data_dir:
        return {
            "audit_report": None,
            "import_diff": None,
            "metadata": None,
            "edition_status": None,
            "artifact_manifest": None,
            "verification_report": None,
            "suspicious_weapon_summary": None,
            "unit_profile_summary": None,
            "loadout_summary": None,
            "source_catalogue_summary": None,
            "unit_variant_summary": None,
            "weapon_coverage_summary": None,
            "unit_footprint_summary": None,
            "unit_footprint_suggestion_summary": None,
            "unit_footprint_template_summary": None,
            "unit_footprint_queue_summary": None,
            "unit_footprint_review": None,
            "ability_modifier_summary": None,
            "schema_summary": None,
            "update_report": None,
            "profile_review": None,
            "edition_readiness": load_text_file(data_dir / "edition_readiness.md") if data_dir else None,
            "model_audit": load_text_file(model_audit_path) if model_audit_path else None,
            "model_comparison": load_text_file(model_comparison_path) if model_comparison_path else None,
            "review_files": [],
            "model_files": model_files(model_dir, href_prefix=f"/api/ml-model-files/{edition}/", selected_model_path=model_path) if model_dir else [],
            "edition": edition,
        }
    return {
        "audit_report": load_json_file(data_dir / "audit_report.json"),
        "import_diff": load_json_file(data_dir / "import_diff.json"),
        "metadata": load_json_file(data_dir / "metadata.json"),
        "edition_status": load_json_file(data_dir / "edition_status.json"),
        "artifact_manifest": load_json_file(data_dir / "artifact_manifest.json"),
        "verification_report": artifact_verification_report(data_dir),
        "suspicious_weapon_summary": suspicious_weapon_summary(data_dir / "suspicious_weapon_review.csv"),
        "unit_profile_summary": unit_profile_summary(data_dir / "unit_profile_review.csv"),
        "loadout_summary": loadout_summary(data_dir / "loadout_review.csv"),
        "source_catalogue_summary": source_catalogue_summary(data_dir / "source_catalogue_review.csv"),
        "unit_variant_summary": unit_variant_summary(data_dir / "unit_variant_review.csv"),
        "weapon_coverage_summary": weapon_coverage_summary(data_dir / "unit_weapon_coverage_review.csv"),
        "unit_footprint_summary": unit_footprint_summary(data_dir / "unit_footprint_review.csv"),
        "unit_footprint_suggestion_summary": unit_footprint_suggestion_summary(data_dir / "unit_footprint_suggestions.csv"),
        "unit_footprint_template_summary": unit_footprint_template_summary(
            data_dir / "unit_footprint_override_template.csv",
            data_dir / "unit_footprint_overrides.csv",
        ),
        "unit_footprint_queue_summary": unit_footprint_queue_summary(data_dir / "unit_footprint_review_queue.csv"),
        "unit_footprint_review": load_text_file(data_dir / "unit_footprint_review.md"),
        "ability_modifier_summary": ability_modifier_summary(data_dir / "ability_modifier_review.csv"),
        "schema_summary": schema_summary(data_dir / "schema_review.csv"),
        "update_report": load_text_file(data_dir / "update_report.md"),
        "profile_review": load_text_file(data_dir / "profile_review.md"),
        "edition_readiness": load_text_file(data_dir / "edition_readiness.md"),
        "model_audit": load_text_file(model_audit_path) if model_audit_path else None,
        "model_comparison": load_text_file(model_comparison_path) if model_comparison_path else None,
        "review_files": review_files(data_dir, href_prefix=f"/api/review-files/{edition}/"),
        "model_files": model_files(model_dir, href_prefix=f"/api/ml-model-files/{edition}/", selected_model_path=model_path) if model_dir else [],
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


def artifact_verification_report(data_dir: Path) -> Optional[Dict[str, Any]]:
    if not (data_dir / "artifact_manifest.json").exists():
        return None
    try:
        from verify_artifacts import verify_artifacts

        return verify_artifacts(data_dir)
    except (OSError, ValueError, KeyError, ImportError, json.JSONDecodeError) as exc:
        return {
            "data_dir": str(data_dir),
            "ok": False,
            "ok_count": 0,
            "failed_count": 1,
            "artifact_count": 1,
            "results": [
                {
                    "filename": "artifact_manifest.json",
                    "status": "error",
                    "ok": False,
                    "error": str(exc),
                }
            ],
        }


def suspicious_weapon_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for row in rows:
        severity = (row.get("review_severity") or "unknown").strip() or "unknown"
        category = (row.get("review_category") or "unknown").strip() or "unknown"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        for reason in (row.get("review_reason") or "").split("; "):
            reason = reason.strip()
            if reason:
                by_reason[reason] = by_reason.get(reason, 0) + 1

    return {
        "total": len(rows),
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_reason": dict(sorted(by_reason.items(), key=lambda item: (-item[1], item[0]))),
        "rows": [_suspicious_weapon_row(row) for row in rows[:row_limit]],
        "row_limit": row_limit,
    }


def _suspicious_weapon_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "severity": row.get("review_severity", ""),
        "category": row.get("review_category", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "weapon_name": row.get("weapon_name", ""),
        "weapon_type": row.get("weapon_type", ""),
        "attacks": row.get("attacks", ""),
        "strength": row.get("strength", ""),
        "ap": row.get("ap", ""),
        "damage": row.get("damage", ""),
        "damage_parse_status": row.get("damage_parse_status", ""),
        "raw_damage_throughput": row.get("raw_damage_throughput", ""),
        "review_reason": row.get("review_reason", ""),
        "source_file": row.get("source_file", ""),
    }


def unit_profile_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    issue_rows = []
    for row in rows:
        severity = (row.get("review_severity") or "ok").strip() or "ok"
        category = (row.get("review_category") or "ok").strip() or "ok"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        if severity == "ok":
            continue
        issue_rows.append(row)
        for reason in (row.get("review_reason") or "").split("; "):
            reason = reason.strip()
            if reason:
                by_reason[reason] = by_reason.get(reason, 0) + 1

    return {
        "total": len(rows),
        "issue_total": len(issue_rows),
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_reason": dict(sorted(by_reason.items(), key=lambda item: (-item[1], item[0]))),
        "rows": [_unit_profile_row(row) for row in issue_rows[:row_limit]],
        "row_limit": row_limit,
    }


def _unit_profile_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "severity": row.get("review_severity", ""),
        "category": row.get("review_category", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "unit_id": row.get("unit_id", ""),
        "source_file": row.get("source_file", ""),
        "toughness": row.get("toughness", ""),
        "save": row.get("save", ""),
        "wounds": row.get("wounds", ""),
        "points": row.get("points", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "review_reason": row.get("review_reason", ""),
    }


def loadout_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for row in rows:
        severity = (row.get("review_severity") or "unknown").strip() or "unknown"
        category = (row.get("review_category") or "unknown").strip() or "unknown"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        for reason in (row.get("review_reason") or "").split("; "):
            reason = reason.strip()
            if reason:
                by_reason[reason] = by_reason.get(reason, 0) + 1

    return {
        "total": len(rows),
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_reason": dict(sorted(by_reason.items(), key=lambda item: (-item[1], item[0]))),
        "rows": [_loadout_row(row) for row in rows[:row_limit]],
        "row_limit": row_limit,
    }


def _loadout_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "severity": row.get("review_severity", ""),
        "category": row.get("review_category", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "source_file": row.get("source_file", ""),
        "points": row.get("points", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "total_weapons": row.get("total_weapons", ""),
        "ranged_weapons": row.get("ranged_weapons", ""),
        "ranged_weapons_with_range": row.get("ranged_weapons_with_range", ""),
        "ranged_weapons_missing_range": row.get("ranged_weapons_missing_range", ""),
        "melee_weapons": row.get("melee_weapons", ""),
        "coverage": row.get("coverage", ""),
        "review_reason": row.get("review_reason", ""),
    }


def source_catalogue_summary(path: Path, *, row_limit: int = 20) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    totals = {
        "units": 0,
        "weapon_profiles": 0,
        "suspicious_weapon_profiles": 0,
        "unit_profile_issue_rows": 0,
        "loadout_review_rows": 0,
        "duplicate_name_unit_rows": 0,
        "no_weapon_units": 0,
        "ranged_weapons_missing_range": 0,
    }
    for row in rows:
        for key in totals:
            totals[key] += _csv_int(row.get(key, ""))

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            -_csv_int(row.get("unit_profile_issue_rows", "")),
            -_csv_int(row.get("suspicious_weapon_profiles", "")),
            -_csv_int(row.get("loadout_review_rows", "")),
            -_csv_int(row.get("units", "")),
            row.get("source_file", "").casefold(),
        ),
    )

    return {
        "total": len(rows),
        "totals": totals,
        "rows": [_source_catalogue_row(row) for row in sorted_rows[:row_limit]],
        "row_limit": row_limit,
    }


def _source_catalogue_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "source_file": row.get("source_file", ""),
        "source_url": row.get("source_url", ""),
        "factions": row.get("factions", ""),
        "units": row.get("units", ""),
        "weapon_profiles": row.get("weapon_profiles", ""),
        "ability_profiles": row.get("ability_profiles", ""),
        "suspicious_weapon_profiles": row.get("suspicious_weapon_profiles", ""),
        "unit_profile_issue_rows": row.get("unit_profile_issue_rows", ""),
        "loadout_review_rows": row.get("loadout_review_rows", ""),
        "duplicate_name_unit_rows": row.get("duplicate_name_unit_rows", ""),
        "no_weapon_units": row.get("no_weapon_units", ""),
        "ranged_weapons_missing_range": row.get("ranged_weapons_missing_range", ""),
    }


def unit_variant_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_name: dict[str, list[Dict[str, str]]] = {}
    for row in rows:
        name = row.get("unit_name", "")
        if name:
            by_name.setdefault(name, []).append(row)

    grouped_rows = []
    for name, variants in by_name.items():
        factions = sorted({row.get("faction", "") for row in variants if row.get("faction")}, key=str.casefold)
        sources = sorted({row.get("source_file", "") for row in variants if row.get("source_file")}, key=str.casefold)
        points = sorted({row.get("points", "") for row in variants if row.get("points")}, key=str.casefold)
        grouped_rows.append(
            {
                "unit_name": name,
                "variant_count": str(len(variants)),
                "factions": "; ".join(factions),
                "source_files": "; ".join(sources),
                "points": "; ".join(points),
            }
        )

    grouped_rows.sort(
        key=lambda row: (
            -_csv_int(row.get("variant_count", "")),
            row.get("unit_name", "").casefold(),
        )
    )
    return {
        "total_rows": len(rows),
        "duplicate_names": len(grouped_rows),
        "max_variant_count": max((_csv_int(row["variant_count"]) for row in grouped_rows), default=0),
        "rows": grouped_rows[:row_limit],
        "row_limit": row_limit,
    }


def weapon_coverage_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_coverage: dict[str, int] = {}
    for row in rows:
        coverage = (row.get("coverage") or "unknown").strip() or "unknown"
        by_coverage[coverage] = by_coverage.get(coverage, 0) + 1
    ranged_with_range_total = sum(_csv_int(row.get("ranged_weapons_with_range", "")) for row in rows)
    ranged_missing_range_total = sum(_csv_int(row.get("ranged_weapons_missing_range", "")) for row in rows)

    no_weapon_rows = [row for row in rows if (row.get("coverage") or "").strip() == "no_weapons"]
    no_weapon_rows.sort(key=lambda row: (row.get("faction", "").casefold(), row.get("unit_name", "").casefold()))
    return {
        "total": len(rows),
        "by_coverage": dict(sorted(by_coverage.items())),
        "no_weapon_total": len(no_weapon_rows),
        "ranged_weapons_with_range": ranged_with_range_total,
        "ranged_weapons_missing_range": ranged_missing_range_total,
        "rows": [_weapon_coverage_row(row) for row in no_weapon_rows[:row_limit]],
        "row_limit": row_limit,
    }


def unit_footprint_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        severity = (row.get("review_severity") or "unknown").strip() or "unknown"
        category = (row.get("review_category") or "unknown").strip() or "unknown"
        status = (row.get("footprint_status") or "unknown").strip() or "unknown"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            {"warning": 0, "error": 1, "info": 2}.get((row.get("review_severity") or "").casefold(), 3),
            row.get("faction", "").casefold(),
            row.get("unit_name", "").casefold(),
        ),
    )
    return {
        "total": len(rows),
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_status": dict(sorted(by_status.items())),
        "rows": [_unit_footprint_row(row) for row in sorted_rows[:row_limit]],
        "row_limit": row_limit,
    }


def unit_footprint_suggestion_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_faction: dict[str, int] = {}
    by_score_band: dict[str, int] = {}
    units_with_suggestions: set[str] = set()
    for row in rows:
        faction = (row.get("faction") or "unknown").strip() or "unknown"
        by_faction[faction] = by_faction.get(faction, 0) + 1
        units_with_suggestions.add(row.get("unit_id") or row.get("unit_name") or "")
        score = _csv_float(row.get("suggestion_score", ""))
        if score >= 0.75:
            band = "high"
        elif score >= 0.65:
            band = "medium"
        else:
            band = "low"
        by_score_band[band] = by_score_band.get(band, 0) + 1

    top_rows = sorted(
        rows,
        key=lambda row: (
            _csv_int(row.get("suggestion_rank", "999")),
            -_csv_float(row.get("suggestion_score", "")),
            row.get("faction", "").casefold(),
            row.get("unit_name", "").casefold(),
        ),
    )
    return {
        "total": len(rows),
        "unit_total": len({unit for unit in units_with_suggestions if unit}),
        "by_score_band": dict(sorted(by_score_band.items())),
        "by_faction": dict(sorted(by_faction.items(), key=lambda item: (-item[1], item[0]))),
        "rows": [_unit_footprint_suggestion_row(row) for row in top_rows[:row_limit]],
        "row_limit": row_limit,
    }


def unit_footprint_template_summary(
    path: Path,
    overrides_path: Path | None = None,
    *,
    row_limit: int = 30,
) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        override_rows = []
        if overrides_path and overrides_path.exists():
            with overrides_path.open(newline="", encoding="utf-8") as handle:
                override_rows = list(csv.DictReader(handle))
    except OSError:
        return None

    summary = summarize_footprint_override_template(rows, override_rows)
    counts = summary["counts"]
    ready_total = int(counts.get("accept_suggestion_ready", 0)) + int(counts.get("override_ready", 0))
    invalid_rows = list(summary["issues"])
    return {
        "total": counts.get("total", len(rows)),
        "ready_total": ready_total,
        "invalid_total": counts.get("invalid", 0),
        "blank_total": counts.get("blank", 0),
        "rejected_total": counts.get("rejected", 0),
        "already_overridden_total": counts.get("already_overridden", 0),
        "by_status": dict(sorted(counts.items())),
        "rows": [_unit_footprint_template_issue_row(row) for row in invalid_rows[:row_limit]],
        "row_limit": row_limit,
    }


def unit_footprint_queue_summary(path: Path, *, row_limit: int = 20) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_priority: dict[str, int] = {}
    by_faction: dict[str, int] = {}
    for row in rows:
        priority = (row.get("review_priority") or "unknown").strip() or "unknown"
        faction = (row.get("faction_contains") or "unknown").strip() or "unknown"
        by_priority[priority] = by_priority.get(priority, 0) + 1
        by_faction[faction] = by_faction.get(faction, 0) + 1

    return {
        "total": len(rows),
        "by_priority": dict(sorted(by_priority.items())),
        "by_faction": dict(sorted(by_faction.items(), key=lambda item: (-item[1], item[0]))),
        "rows": [_unit_footprint_queue_row(row) for row in rows[:row_limit]],
        "row_limit": row_limit,
    }


def _unit_footprint_queue_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "review_rank": row.get("review_rank", ""),
        "review_priority": row.get("review_priority", ""),
        "review_hint": row.get("review_hint", ""),
        "unit_id": row.get("unit_id", ""),
        "unit_name": row.get("unit_name", ""),
        "faction": row.get("faction_contains", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "suggestion_score": row.get("suggestion_score", ""),
        "suggested_guide_faction": row.get("suggested_guide_faction", ""),
        "suggested_guide_unit_name": row.get("suggested_guide_unit_name", ""),
        "suggested_guide_model_name": row.get("suggested_guide_model_name", ""),
        "suggested_base_size_text": row.get("suggested_base_size_text", ""),
    }


def _unit_footprint_template_issue_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "unit_id": row.get("unit_id", ""),
        "unit_name": row.get("unit_name", ""),
        "review_decision": row.get("review_decision", ""),
        "reason": row.get("reason", ""),
    }


def _unit_footprint_suggestion_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "unit_id": row.get("unit_id", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "suggestion_rank": row.get("suggestion_rank", ""),
        "suggestion_score": row.get("suggestion_score", ""),
        "suggestion_reason": row.get("suggestion_reason", ""),
        "guide_faction": row.get("guide_faction", ""),
        "guide_unit_name": row.get("guide_unit_name", ""),
        "guide_model_name": row.get("guide_model_name", ""),
        "base_size_text": row.get("base_size_text", ""),
        "base_type": row.get("base_type", ""),
        "base_shape": row.get("base_shape", ""),
        "base_width_mm": row.get("base_width_mm", ""),
        "base_depth_mm": row.get("base_depth_mm", ""),
    }


def _unit_footprint_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "severity": row.get("review_severity", ""),
        "category": row.get("review_category", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "footprint_status": row.get("footprint_status", ""),
        "base_type": row.get("base_type", ""),
        "base_shape": row.get("base_shape", ""),
        "base_width_mm": row.get("base_width_mm", ""),
        "base_depth_mm": row.get("base_depth_mm", ""),
        "guide_faction": row.get("guide_faction", ""),
        "guide_unit_name": row.get("guide_unit_name", ""),
        "guide_model_name": row.get("guide_model_name", ""),
        "match_method": row.get("match_method", ""),
        "match_confidence": row.get("match_confidence", ""),
        "review_reason": row.get("review_reason", ""),
    }


def _weapon_coverage_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "source_file": row.get("source_file", ""),
        "points": row.get("points", ""),
        "models_min": row.get("models_min", ""),
        "models_max": row.get("models_max", ""),
        "total_weapons": row.get("total_weapons", ""),
        "ranged_weapons": row.get("ranged_weapons", ""),
        "ranged_weapons_with_range": row.get("ranged_weapons_with_range", ""),
        "ranged_weapons_missing_range": row.get("ranged_weapons_missing_range", ""),
        "melee_weapons": row.get("melee_weapons", ""),
        "coverage": row.get("coverage", ""),
    }


def ability_modifier_summary(path: Path, *, row_limit: int = 30) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_type: dict[str, int] = {}
    by_grant: dict[str, int] = {}
    for row in rows:
        modifier_type = (row.get("modifier_type") or "unknown").strip() or "unknown"
        by_type[modifier_type] = by_type.get(modifier_type, 0) + 1
        for grant in (row.get("grants") or "").split("; "):
            grant = grant.strip()
            if grant:
                by_grant[grant] = by_grant.get(grant, 0) + 1

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("modifier_type", "").casefold(),
            row.get("faction", "").casefold(),
            row.get("unit_name", "").casefold(),
            row.get("source", "").casefold(),
        ),
    )
    return {
        "total": len(rows),
        "by_type": dict(sorted(by_type.items())),
        "by_grant": dict(sorted(by_grant.items())),
        "rows": [_ability_modifier_row(row) for row in sorted_rows[:row_limit]],
        "row_limit": row_limit,
    }


def _ability_modifier_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "modifier_type": row.get("modifier_type", ""),
        "faction": row.get("faction", ""),
        "unit_name": row.get("unit_name", ""),
        "selection_type": row.get("selection_type", ""),
        "source_file": row.get("source_file", ""),
        "source": row.get("source", ""),
        "description": row.get("description", ""),
        "hit_modifier": row.get("hit_modifier", ""),
        "wound_modifier": row.get("wound_modifier", ""),
        "reroll_hits": row.get("reroll_hits", ""),
        "reroll_wounds": row.get("reroll_wounds", ""),
        "grants": row.get("grants", ""),
        "anti_rules": row.get("anti_rules", ""),
        "ignores_cover": row.get("ignores_cover", ""),
        "damage_reduction": row.get("damage_reduction", ""),
    }


def schema_summary(path: Path, *, row_limit: int = 20) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None

    by_status: dict[str, int] = {}
    for row in rows:
        status = (row.get("status") or "unknown").strip() or "unknown"
        by_status[status] = by_status.get(status, 0) + 1

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            0 if (row.get("status") or "").strip().lower() != "pass" else 1,
            row.get("table", "").casefold(),
        ),
    )
    return {
        "total": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "rows": [_schema_row(row) for row in sorted_rows[:row_limit]],
        "row_limit": row_limit,
    }


def _schema_row(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "table": row.get("table", ""),
        "file": row.get("file", ""),
        "status": row.get("status", ""),
        "required_count": row.get("required_count", ""),
        "actual_count": row.get("actual_count", ""),
        "missing_columns": row.get("missing_columns", ""),
        "extra_columns": row.get("extra_columns", ""),
        "required_columns": row.get("required_columns", ""),
        "actual_columns": row.get("actual_columns", ""),
    }


def _csv_int(value: str) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _csv_float(value: str) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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


def model_files(
    model_dir: Optional[Path],
    *,
    href_prefix: str,
    selected_model_path: Optional[Path] = None,
) -> list[Dict[str, Any]]:
    if not model_dir:
        return []
    labels = dict(MODEL_FILE_LABELS)
    if selected_model_path:
        labels.setdefault(selected_model_path.name, "Selected ML model JSON")
        labels.setdefault(selected_model_path.with_suffix(".md").name, "Selected ML model audit report")
    files = []
    for filename, label in labels.items():
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


def download_file_request_parts(path: str, *, prefix: str, default_edition: str) -> tuple[str, str]:
    remainder = path[len(prefix) :] if path.startswith(prefix) else path
    parts = [part for part in remainder.split("/") if part]
    if len(parts) >= 2:
        return parts[0], Path(parts[-1]).name
    return default_edition, Path(parts[-1] if parts else "").name
