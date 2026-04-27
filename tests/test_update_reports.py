import json

import warhammer.update_reports as update_reports
from warhammer.update_reports import write_generated_reports


def test_write_generated_reports_writes_all_report_artifacts(monkeypatch, tmp_path):
    calls = []
    audit_report = {"summary": {"error": 0, "warning": 1, "info": 2, "total": 3}}
    edition_status = {"edition": "10e", "status": "ready"}
    profile_counts = {"weapon_profiles": 10, "ability_profiles": 5}

    def fake_build_audit_report(csv_dir):
        calls.append(("build_audit_report", csv_dir))
        return audit_report

    def fake_write_audit_report(report, path):
        calls.append(("write_audit_report", report, path))
        path.write_text(json.dumps(report), encoding="utf-8")

    def fake_write_schema_review(csv_dir):
        calls.append(("write_schema_review", csv_dir))
        return 4

    def fake_write_profile_review(csv_dir):
        calls.append(("write_profile_review", csv_dir))
        return profile_counts

    def fake_build_edition_status(csv_dir, edition, source_after, report):
        calls.append(("build_edition_status", csv_dir, edition, source_after, report))
        return edition_status

    monkeypatch.setattr(update_reports, "build_audit_report", fake_build_audit_report)
    monkeypatch.setattr(update_reports, "write_audit_report", fake_write_audit_report)
    monkeypatch.setattr(update_reports, "write_schema_review", fake_write_schema_review)
    monkeypatch.setattr(update_reports, "write_profile_review", fake_write_profile_review)
    monkeypatch.setattr(update_reports, "build_edition_status", fake_build_edition_status)
    monkeypatch.setattr(update_reports, "render_edition_readiness_report", lambda status, project_root: "# Ready\n")
    monkeypatch.setattr(
        update_reports,
        "build_update_report",
        lambda diff, report, review_thresholds=None: calls.append(("build_update_report", review_thresholds)) or "# Update\n",
    )

    result = write_generated_reports(
        csv_dir=tmp_path,
        edition="10e",
        source_after={"commit": "abc"},
        diff={"tables": {}},
        project_root=tmp_path.parent,
        review_thresholds={"loadout_warnings": 143},
    )

    assert result.audit_report == audit_report
    assert result.schema_review_rows == 4
    assert result.profile_review_counts == profile_counts
    assert result.edition_status == edition_status
    assert json.loads((tmp_path / "audit_report.json").read_text(encoding="utf-8")) == audit_report
    assert json.loads((tmp_path / "edition_status.json").read_text(encoding="utf-8")) == edition_status
    assert (tmp_path / "edition_readiness.md").read_text(encoding="utf-8") == "# Ready\n"
    assert (tmp_path / "update_report.md").read_text(encoding="utf-8") == "# Update\n"
    assert [call[0] for call in calls] == [
        "build_audit_report",
        "write_audit_report",
        "write_schema_review",
        "write_profile_review",
        "build_edition_status",
        "build_update_report",
    ]
    assert ("build_update_report", {"loadout_warnings": 143}) in calls
