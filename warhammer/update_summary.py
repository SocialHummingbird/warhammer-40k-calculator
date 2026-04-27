from __future__ import annotations

from pathlib import Path
from typing import Optional


def build_update_summary_lines(
    source_before: dict[str, object],
    source_after: dict[str, object],
    diff: dict[str, object],
    audit_report: dict[str, object],
    snapshot_path: Optional[Path],
    profile_review_counts: dict[str, int],
    schema_review_rows: int,
    ml_artifacts: Optional[dict[str, object]] = None,
) -> list[str]:
    lines = [
        "Database update complete.",
        f"Source: {source_after.get('remote_origin')}",
        f"Commit: {source_before.get('commit')} -> {source_after.get('commit')}",
        f"Subject: {source_after.get('commit_subject')}",
        "Rows:",
    ]
    for table, table_diff in diff["tables"].items():
        lines.append(
            f"  {table}: {table_diff['before_count']} -> {table_diff['after_count']} "
            f"({table_diff['delta']:+d}), changed {table_diff['changed_count']}"
        )
    summary = audit_report["summary"]
    lines.extend(
        [
            f"Audit samples: {summary['error']} errors, {summary['warning']} warnings, {summary['info']} info",
            f"Schema review: {schema_review_rows} table rows",
            "Profile review: "
            f"{profile_review_counts['weapon_profiles']} weapons, "
            f"{profile_review_counts.get('suspicious_weapon_profiles', 0)} suspicious weapon rows, "
            f"{profile_review_counts.get('unit_profile_issue_rows', 0)} unit profile issue rows, "
            f"{profile_review_counts['ability_profiles']} abilities, "
            f"{profile_review_counts.get('ability_modifiers', 0)} ability modifier rows, "
            f"{profile_review_counts.get('unit_name_variants', 0)} duplicate-name unit rows, "
            f"{profile_review_counts.get('unit_weapon_coverage_rows', 0)} weapon coverage rows, "
            f"{profile_review_counts.get('loadout_review_rows', 0)} loadout review rows, "
            f"{profile_review_counts.get('source_catalogue_review_rows', 0)} source catalogue rows",
        ]
    )
    if snapshot_path:
        lines.append(f"Snapshot: {snapshot_path}")
    if ml_artifacts:
        lines.append(
            "ML artifacts: "
            f"{ml_artifacts['feature_rows']} feature rows, "
            f"feature set {ml_artifacts['feature_set']}, "
            f"model type {ml_artifacts.get('model_type', 'centroid')}, "
            f"model {ml_artifacts['model_path']}"
        )
    return lines


def print_update_summary(
    source_before: dict[str, object],
    source_after: dict[str, object],
    diff: dict[str, object],
    audit_report: dict[str, object],
    snapshot_path: Optional[Path],
    profile_review_counts: dict[str, int],
    schema_review_rows: int,
    ml_artifacts: Optional[dict[str, object]] = None,
) -> None:
    for line in build_update_summary_lines(
        source_before,
        source_after,
        diff,
        audit_report,
        snapshot_path,
        profile_review_counts,
        schema_review_rows,
        ml_artifacts,
    ):
        print(line)
