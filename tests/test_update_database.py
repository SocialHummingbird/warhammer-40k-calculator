from update_database import _build_artifact_manifest, _build_import_diff, _build_update_report


def test_build_import_diff_counts_added_removed_and_changed_rows():
    before = {
        "units": {
            "u1": {"unit_id": "u1", "name": "Old"},
            "u2": {"unit_id": "u2", "name": "Removed"},
        },
        "weapons": {},
        "abilities": {},
        "keywords": {},
        "unit_keywords": {},
    }
    after = {
        "units": {
            "u1": {"unit_id": "u1", "name": "New"},
            "u3": {"unit_id": "u3", "name": "Added"},
        },
        "weapons": {},
        "abilities": {},
        "keywords": {},
        "unit_keywords": {},
    }

    diff = _build_import_diff(before, after, source_before={}, source_after={})

    unit_diff = diff["tables"]["units"]
    assert unit_diff["before_count"] == 2
    assert unit_diff["after_count"] == 2
    assert unit_diff["added_count"] == 1
    assert unit_diff["removed_count"] == 1
    assert unit_diff["changed_count"] == 1
    assert unit_diff["added_samples"] == ["u3"]
    assert unit_diff["removed_samples"] == ["u2"]
    assert unit_diff["changed_samples"] == ["u1"]


def test_build_update_report_summarises_source_audit_and_diff():
    diff = {
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
    audit_report = {
        "row_counts": {"units": 2, "weapons": 0, "abilities": 0, "keywords": 0, "unit_keywords": 0},
        "summary": {"error": 0, "warning": 0, "info": 0, "total": 0},
        "sections": {"units": {"issues": []}, "weapons": {"issues": []}, "abilities": {"issues": []}, "unit_keywords": {"issues": []}},
    }

    report = _build_update_report(diff, audit_report)

    assert "# Warhammer Data Update Report" in report
    assert "Status: PASS" in report
    assert "https://github.com/BSData/wh40k-10e/commit/abcdef" in report
    assert "| units | 1 | 2 | +1 | 1 | 0 | 1 |" in report
    assert "- units added: u2" in report
    assert "loadout_review.csv" in report
    assert "artifact_manifest.json" in report


def test_build_artifact_manifest_hashes_generated_files(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    (tmp_path / "weapons.csv").write_text("weapon_id,unit_id,name\nw1,u1,Gun\n", encoding="utf-8")

    manifest = _build_artifact_manifest(tmp_path, {"commit": "abc"})

    assert manifest["source"]["commit"] == "abc"
    assert manifest["artifacts"]["units.csv"]["bytes"] > 0
    assert len(manifest["artifacts"]["units.csv"]["sha256"]) == 64
    assert "artifact_manifest.json" not in manifest["artifacts"]
