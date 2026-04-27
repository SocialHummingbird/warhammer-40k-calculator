from warhammer.update_report import audit_issue_lines, build_update_report, commit_url, diff_sample_lines, review_threshold_lines


def _diff():
    return {
        "generated_at": "2026-04-25T12:00:00Z",
        "source_before": {"commit": "old"},
        "source_after": {
            "remote_origin": "https://github.com/BSData/wh40k-10e.git",
            "branch": "main",
            "commit": "abcdef",
            "commit_date": "2026-04-21 17:44:59 +0100",
            "commit_subject": "Fix data",
        },
        "tables": {
            "units": {
                "before_count": 1,
                "after_count": 2,
                "delta": 1,
                "added_count": 1,
                "removed_count": 0,
                "changed_count": 1,
                "added_samples": ["u2"],
                "removed_samples": [],
                "changed_samples": ["u1"],
            },
            "weapons": {"before_count": 0, "after_count": 0, "delta": 0, "added_count": 0, "removed_count": 0, "changed_count": 0},
            "abilities": {"before_count": 0, "after_count": 0, "delta": 0, "added_count": 0, "removed_count": 0, "changed_count": 0},
            "keywords": {"before_count": 0, "after_count": 0, "delta": 0, "added_count": 0, "removed_count": 0, "changed_count": 0},
            "unit_keywords": {"before_count": 0, "after_count": 0, "delta": 0, "added_count": 0, "removed_count": 0, "changed_count": 0},
        },
    }


def _audit_report():
    return {
        "row_counts": {"units": 2, "weapons": 0, "abilities": 0, "keywords": 0, "unit_keywords": 0},
        "summary": {"error": 0, "warning": 0, "info": 0, "total": 0},
        "sections": {"units": {"issues": []}, "weapons": {"issues": []}, "abilities": {"issues": []}, "unit_keywords": {"issues": []}},
    }


def test_build_update_report_summarises_source_audit_and_diff():
    report = build_update_report(_diff(), _audit_report())

    assert "# Warhammer Data Update Report" in report
    assert "Status: PASS" in report
    assert "https://github.com/BSData/wh40k-10e/commit/abcdef" in report
    assert "| units | 1 | 2 | +1 | 1 | 0 | 1 |" in report
    assert "- units added: u2" in report
    assert "loadout_review.csv" in report
    assert "unit_profile_review.csv" in report
    assert "edition_status.json" in report
    assert "artifact_manifest.json" in report


def test_build_update_report_can_include_review_gate_thresholds():
    report = build_update_report(
        _diff(),
        _audit_report(),
        review_thresholds={
            "suspicious_weapon_warnings": 18,
            "loadout_warnings": 143,
            "no_weapon_units": 16,
        },
    )

    assert "## Review Gate Thresholds" in report
    assert "| Suspicious weapon warnings | 18 |" in report
    assert "| Loadout warnings | 143 |" in report
    assert "| No-weapon units | 16 |" in report


def test_review_threshold_lines_formats_known_and_unknown_thresholds():
    assert review_threshold_lines({"audit_warnings": 0, "custom": 3}) == [
        "| Audit warnings | 0 |",
        "| custom | 3 |",
    ]


def test_commit_url_normalizes_github_urls():
    assert commit_url({"remote_origin": "git@github.com:BSData/wh40k-10e.git", "commit": "abc"}) == "https://github.com/BSData/wh40k-10e/commit/abc"
    assert commit_url({"remote_origin": "https://example.com/repo.git", "commit": "abc"}) == ""
    assert commit_url({"remote_origin": "", "commit": "abc"}) == ""


def test_audit_issue_lines_and_diff_sample_lines_format_samples():
    audit = {
        "sections": {
            "weapons": {
                "issues": [
                    {"severity": "warning", "label": "Missing damage", "samples": ["Gun", "Blade"]},
                ]
            }
        }
    }

    assert audit_issue_lines(audit) == ["- [WARNING] weapons: Missing damage - Gun, Blade"]
    assert diff_sample_lines(_diff()) == ["- units added: u2", "- units changed: u1"]
