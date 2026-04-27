from __future__ import annotations


TABLE_ORDER = ("units", "weapons", "abilities", "keywords", "unit_keywords")


def build_update_report(
    diff: dict[str, object],
    audit_report: dict[str, object],
    *,
    review_thresholds: dict[str, int] | None = None,
) -> str:
    """Build a human-readable update and audit report."""

    source_after = diff.get("source_after", {})
    source_before = diff.get("source_before", {})
    source_url = commit_url(source_after)
    commit = str(source_after.get("commit") or "unknown")
    before_commit = str(source_before.get("commit") or "unknown")
    generated_at = str(diff.get("generated_at") or audit_report.get("generated_at") or "")
    audit_summary = audit_report.get("summary", {})
    audit_status = "PASS" if int(audit_summary.get("total", 0) or 0) == 0 else "NEEDS REVIEW"

    lines = [
        "# Warhammer Data Update Report",
        "",
        f"Generated: {generated_at}",
        f"Source: {source_after.get('remote_origin') or 'unknown'}",
        f"Branch: {source_after.get('branch') or 'unknown'}",
        f"Commit: {before_commit} -> {commit}",
        f"Commit date: {source_after.get('commit_date') or 'unknown'}",
        f"Commit subject: {source_after.get('commit_subject') or 'unknown'}",
    ]
    if source_url:
        lines.append(f"Commit URL: {source_url}")
    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"Status: {audit_status}",
            "",
            "| Severity | Samples |",
            "| --- | ---: |",
            f"| Errors | {int(audit_summary.get('error', 0) or 0)} |",
            f"| Warnings | {int(audit_summary.get('warning', 0) or 0)} |",
            f"| Info | {int(audit_summary.get('info', 0) or 0)} |",
            f"| Total | {int(audit_summary.get('total', 0) or 0)} |",
            "",
        ]
    )

    issue_lines = audit_issue_lines(audit_report)
    if issue_lines:
        lines.extend(["### Audit Issues", "", *issue_lines, ""])
    else:
        lines.extend(["No audit issues were reported.", ""])

    if review_thresholds:
        lines.extend(
            [
                "## Review Gate Thresholds",
                "",
                "| Metric | Accepted count |",
                "| --- | ---: |",
                *review_threshold_lines(review_thresholds),
                "",
            ]
        )

    row_counts = audit_report.get("row_counts", {})
    lines.extend(
        [
            "## Current Row Counts",
            "",
            "| Table | Rows |",
            "| --- | ---: |",
        ]
    )
    for table in TABLE_ORDER:
        lines.append(f"| {table} | {int(row_counts.get(table, 0) or 0)} |")

    lines.extend(
        [
            "",
            "## Manual Review Files",
            "",
            "- `profile_review.md`: summary of imported profile counts and largest factions.",
            "- `weapon_profile_review.csv`: every imported weapon profile joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.",
            "- `suspicious_weapon_review.csv`: missing, unparsable, zero, or extreme weapon characteristics with severity/category labels for manual review.",
            "- `unit_profile_review.csv`: every imported unit with core stat, points, and model-count validation for manual review.",
            "- `ability_profile_review.csv`: every imported ability profile joined to unit name, faction, and source file where applicable.",
            "- `ability_modifier_review.csv`: derived ability effects that the calculator applies during matchup math.",
            "- `unit_variant_review.csv`: duplicate-name unit rows joined to IDs, faction context, and source file.",
            "- `unit_weapon_coverage_review.csv`: each unit's ranged/melee weapon counts and coverage category.",
            "- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need loadout selection.",
            "- `source_catalogue_review.csv`: per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.",
            "- `edition_status.json`: edition readiness, ruleset availability, source commit, and calculation status.",
            "- `edition_readiness.md`: readable edition compatibility and migration checklist.",
            "- `artifact_manifest.json`: file sizes and SHA-256 hashes for generated data artifacts.",
            "- `schema_review.csv`: required versus actual importer CSV columns for schema auditing.",
        ]
    )

    lines.extend(
        [
            "",
            "## Import Diff",
            "",
            "| Table | Before | After | Delta | Added | Removed | Changed |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    tables = diff.get("tables", {})
    for table in TABLE_ORDER:
        table_diff = tables.get(table, {})
        lines.append(
            f"| {table} | {int(table_diff.get('before_count', 0) or 0)} "
            f"| {int(table_diff.get('after_count', 0) or 0)} "
            f"| {int(table_diff.get('delta', 0) or 0):+d} "
            f"| {int(table_diff.get('added_count', 0) or 0)} "
            f"| {int(table_diff.get('removed_count', 0) or 0)} "
            f"| {int(table_diff.get('changed_count', 0) or 0)} |"
        )

    sample_lines = diff_sample_lines(diff)
    if sample_lines:
        lines.extend(["", "### Diff Samples", "", *sample_lines])

    lines.append("")
    return "\n".join(lines)


def review_threshold_lines(review_thresholds: dict[str, int]) -> list[str]:
    labels = {
        "audit_warnings": "Audit warnings",
        "suspicious_weapon_warnings": "Suspicious weapon warnings",
        "unit_profile_warnings": "Unit profile warnings",
        "loadout_warnings": "Loadout warnings",
        "no_weapon_units": "No-weapon units",
    }
    return [
        f"| {labels.get(key, key)} | {int(value)} |"
        for key, value in sorted(review_thresholds.items())
    ]


def commit_url(source: dict[str, object]) -> str:
    remote = str(source.get("remote_origin") or "")
    commit = str(source.get("commit") or "")
    if not remote or not commit:
        return ""
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.split(":", 1)[1]
    if remote.startswith("https://github.com/"):
        return f"{remote}/commit/{commit}"
    return ""


def audit_issue_lines(audit_report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    sections = audit_report.get("sections", {})
    for section_name in ("schema", "units", "weapons", "abilities", "unit_keywords"):
        section = sections.get(section_name, {})
        for issue in section.get("issues", []):
            samples = ", ".join(str(sample) for sample in issue.get("samples", []))
            lines.append(
                f"- [{str(issue.get('severity', 'info')).upper()}] "
                f"{section_name}: {issue.get('label')} - {samples}"
            )
    return lines


def diff_sample_lines(diff: dict[str, object]) -> list[str]:
    lines: list[str] = []
    tables = diff.get("tables", {})
    for table in TABLE_ORDER:
        table_diff = tables.get(table, {})
        for key, label in (
            ("added_samples", "Added"),
            ("removed_samples", "Removed"),
            ("changed_samples", "Changed"),
        ):
            samples = [str(sample) for sample in table_diff.get(key, [])]
            if samples:
                lines.append(f"- {table} {label.lower()}: {', '.join(samples)}")
    return lines
