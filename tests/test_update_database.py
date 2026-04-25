from update_database import (
    _build_artifact_manifest,
    _build_edition_status,
    _build_import_diff,
    _build_update_report,
    _csv_data_row_count,
    _edition_latest_dir,
    _edition_snapshot_dir,
    _ml_feature_path,
    _ml_model_path,
    _parse_args,
)


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
    assert "edition_status.json" in report
    assert "artifact_manifest.json" in report


def test_build_artifact_manifest_hashes_generated_files(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    (tmp_path / "weapons.csv").write_text("weapon_id,unit_id,name\nw1,u1,Gun\n", encoding="utf-8")
    (tmp_path / "edition_status.json").write_text('{"edition":"10e"}\n', encoding="utf-8")

    manifest = _build_artifact_manifest(tmp_path, {"commit": "abc"})

    assert manifest["source"]["commit"] == "abc"
    assert manifest["artifacts"]["units.csv"]["bytes"] > 0
    assert manifest["artifacts"]["edition_status.json"]["bytes"] > 0
    assert len(manifest["artifacts"]["units.csv"]["sha256"]) == 64
    assert "artifact_manifest.json" not in manifest["artifacts"]


def test_build_edition_status_reports_ready_supported_edition(tmp_path):
    (tmp_path / "metadata.json").write_text(
        '{"rules_edition":"10e","counts":{"units":1,"weapons":2}}\n',
        encoding="utf-8",
    )
    audit_report = {"summary": {"error": 0, "warning": 1, "info": 0, "total": 1}}

    status = _build_edition_status(tmp_path, "10e", {"commit": "abc", "dirty": False}, audit_report)

    assert status["edition"] == "10e"
    assert status["rules_available"] is True
    assert status["calculations_enabled"] is True
    assert status["status"] == "ready"
    assert status["blockers"] == []
    assert status["counts"]["weapons"] == 2


def test_build_edition_status_blocks_unsupported_edition(tmp_path):
    (tmp_path / "metadata.json").write_text('{"rules_edition":"11e","counts":{"units":1}}\n', encoding="utf-8")

    status = _build_edition_status(tmp_path, "11e", {"commit": "abc"}, {"summary": {"error": 0}})

    assert status["edition"] == "11e"
    assert status["rules_available"] is False
    assert status["calculations_enabled"] is False
    assert status["status"] == "blocked"
    assert "Ruleset not implemented" in status["blockers"]


def test_update_defaults_use_edition_scoped_data_paths():
    args = _parse_args(["--edition", "10e"])

    assert args.csv_dir == _edition_latest_dir("10e")
    assert args.snapshot_dir == _edition_snapshot_dir("10e")
    assert args.skip_ml is False
    assert args.ml_max_rows == 10000
    assert args.ml_strategy == "sample"
    assert args.ml_feature_set == "pre_match"


def test_ml_artifact_paths_are_edition_scoped():
    assert _ml_feature_path("10e").as_posix().endswith("data/ml/10e/matchup_training_rows.csv")
    assert _ml_model_path("10e").as_posix().endswith("models/10e/matchup_centroid_model.json")


def test_csv_data_row_count_excludes_header(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    assert _csv_data_row_count(path) == 2
