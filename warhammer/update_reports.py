from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audit_import import build_audit_report, write_audit_report, write_schema_review
from review_profiles import write_profile_review
from warhammer.edition_readiness import render_edition_readiness_report
from warhammer.edition_status import build_edition_status
from warhammer.file_io import write_json_file, write_text_file
from warhammer.update_report import build_update_report


@dataclass(frozen=True)
class GeneratedReports:
    audit_report: dict[str, object]
    schema_review_rows: int
    profile_review_counts: dict[str, int]
    edition_status: dict[str, object]


def write_generated_reports(
    *,
    csv_dir: Path,
    edition: str,
    source_after: dict[str, object],
    diff: dict[str, object],
    project_root: Path,
    review_thresholds: dict[str, int] | None = None,
) -> GeneratedReports:
    audit_report = build_audit_report(csv_dir)
    write_audit_report(audit_report, Path(csv_dir) / "audit_report.json")
    schema_review_rows = write_schema_review(csv_dir)
    profile_review_counts = write_profile_review(csv_dir)
    edition_status = build_edition_status(csv_dir, edition, source_after, audit_report)
    write_json_file(Path(csv_dir) / "edition_status.json", edition_status)
    write_text_file(
        Path(csv_dir) / "edition_readiness.md",
        render_edition_readiness_report(edition_status, project_root=project_root),
    )
    write_text_file(Path(csv_dir) / "update_report.md", build_update_report(diff, audit_report, review_thresholds=review_thresholds))
    return GeneratedReports(
        audit_report=audit_report,
        schema_review_rows=schema_review_rows,
        profile_review_counts=profile_review_counts,
        edition_status=edition_status,
    )
