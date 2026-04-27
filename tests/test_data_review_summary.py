import json
import subprocess
import sys

from warhammer.data_review_summary import (
    build_current_review_thresholds,
    build_data_review_gate_failures,
    build_data_review_summary_lines,
    build_review_threshold_summary_lines,
    normalize_review_thresholds,
    render_data_review_summary,
)


def test_render_data_review_summary_includes_terminal_audit_counts():
    payload = {
        "edition": "10e",
        "metadata": {
            "generated_at": "2026-04-25T12:00:00Z",
            "counts": {"units": 10, "weapons": 24},
            "source_revisions": [
                {
                    "commit": "32b4525d9f69f062f3458d517c6cf82512ef6fef",
                    "remote_origin": "https://github.com/BSData/wh40k-10e.git",
                    "dirty": False,
                }
            ],
        },
        "edition_status": {"edition": "10e", "status": "ready"},
        "verification_report": {"ok": True, "ok_count": 5, "artifact_count": 5, "failed_count": 0},
        "audit_report": {"summary": {"error": 1, "warning": 2, "info": 3}},
        "suspicious_weapon_summary": {
            "total": 4,
            "by_severity": {"error": 1, "warning": 3},
            "by_category": {"missing_damage": 1, "extreme_profile": 3},
        },
        "unit_profile_summary": {
            "total": 10,
            "issue_total": 2,
            "by_severity": {"ok": 8, "warning": 2},
            "by_category": {"ok": 8, "unit_points_unset": 2},
        },
        "loadout_summary": {
            "total": 6,
            "by_severity": {"info": 4, "warning": 2},
            "by_category": {"legends_profile": 4, "many_profiles": 2},
        },
        "weapon_coverage_summary": {"total": 10, "no_weapon_total": 1, "by_coverage": {"both": 8, "no_weapons": 1, "melee_only": 1}},
        "schema_summary": {"total": 5, "by_status": {"pass": 5}},
        "unit_variant_summary": {"duplicate_names": 3, "total_rows": 7, "max_variant_count": 3},
        "ability_modifier_summary": {"total": 9, "by_type": {"attack_modifier": 8, "damage_reduction": 1}},
        "source_catalogue_summary": {
            "total": 2,
            "totals": {"units": 10, "weapon_profiles": 24, "suspicious_weapon_profiles": 4},
        },
        "review_files": [{"filename": "unit_profile_review.csv"}],
        "model_files": [{"filename": "matchup_centroid_model.json"}],
    }

    rendered = render_data_review_summary(payload)

    assert "Data review summary (10e)" in rendered
    assert "Edition status: ready" in rendered
    assert "Source: https://github.com/BSData/wh40k-10e.git @ 32b4525d9f69" in rendered
    assert "Rows: units 10, weapons 24" in rendered
    assert "Artifacts: pass, 5/5 ok, 0 failed" in rendered
    assert "Audit samples: 1 errors, 2 warnings, 3 info" in rendered
    assert "Suspicious weapons: 4" in rendered
    assert "Unit profile issues: 2" in rendered
    assert "Weapon coverage: 1 no-weapon units / 10 units" in rendered
    assert "Review files: 1 available" in rendered
    assert rendered.endswith("\n")


def test_build_data_review_summary_lines_tolerates_sparse_payload():
    lines = build_data_review_summary_lines({"edition": "11e"})

    assert lines == ["Data review summary (11e)", "Edition status: unknown"]


def test_build_data_review_gate_failures_blocks_errors_and_failed_checks():
    payload = {
        "edition_status": {"status": "blocked"},
        "verification_report": {"ok": False, "failed_count": 2, "artifact_count": 8},
        "schema_summary": {"by_status": {"pass": 4, "fail": 1}},
        "audit_report": {"summary": {"error": 1, "warning": 2}},
        "suspicious_weapon_summary": {"by_severity": {"warning": 3}},
        "unit_profile_summary": {"by_severity": {"error": 4}},
        "loadout_summary": {"by_severity": {"warning": 5}},
    }

    failures = build_data_review_gate_failures(payload)

    assert failures == [
        "edition status is blocked",
        "artifact verification failed: 2 failed of 8 checks",
        "schema review has 1 fail rows",
        "audit samples contains 1 errors",
        "unit profiles contains 4 errors",
    ]


def test_build_data_review_gate_failures_can_treat_warnings_as_blocking():
    payload = {
        "audit_report": {"summary": {"error": 0, "warning": 2}},
        "suspicious_weapon_summary": {"by_severity": {"warning": 3}},
        "unit_profile_summary": {"by_severity": {"warning": 4}},
        "loadout_summary": {"by_severity": {"warning": 5}},
    }

    failures = build_data_review_gate_failures(payload, fail_on_warnings=True)

    assert failures == [
        "audit samples contains 2 warnings",
        "suspicious weapons contains 3 warnings",
        "unit profiles contains 4 warnings",
        "loadout review contains 5 warnings",
    ]


def test_build_data_review_gate_failures_supports_warning_and_coverage_thresholds():
    payload = {
        "audit_report": {"summary": {"warning": 2}},
        "suspicious_weapon_summary": {"by_severity": {"warning": 18}},
        "unit_profile_summary": {"by_severity": {"warning": 0}},
        "loadout_summary": {"by_severity": {"warning": 143}},
        "weapon_coverage_summary": {"no_weapon_total": 16},
    }

    failures = build_data_review_gate_failures(
        payload,
        thresholds={
            "audit_warnings": 1,
            "suspicious_weapon_warnings": 18,
            "unit_profile_warnings": 0,
            "loadout_warnings": 120,
            "no_weapon_units": 15,
        },
    )

    assert failures == [
        "audit samples contains 2 warnings, above threshold 1",
        "loadout review contains 143 warnings, above threshold 120",
        "weapon coverage has 16 no-weapon units, above threshold 15",
    ]


def test_build_current_review_thresholds_and_normalize_thresholds():
    payload = {
        "audit_report": {"summary": {"warning": 2}},
        "suspicious_weapon_summary": {"by_severity": {"warning": 18}},
        "unit_profile_summary": {"by_severity": {"warning": 0}},
        "loadout_summary": {"by_severity": {"warning": 143}},
        "weapon_coverage_summary": {"no_weapon_total": 16},
    }

    assert build_current_review_thresholds(payload) == {
        "audit_warnings": 2,
        "suspicious_weapon_warnings": 18,
        "unit_profile_warnings": 0,
        "loadout_warnings": 143,
        "no_weapon_units": 16,
    }
    assert normalize_review_thresholds(
        {
            "audit_warnings": "2",
            "loadout_warnings": 143,
            "unknown": 99,
            "no_weapon_units": -1,
        }
    ) == {"audit_warnings": 2, "loadout_warnings": 143}


def test_build_review_threshold_summary_lines_formats_thresholds():
    assert build_review_threshold_summary_lines({"loadout_warnings": 143, "no_weapon_units": 16}) == [
        "Review gate thresholds:",
        "- loadout warnings: 143",
        "- no-weapon units: 16",
    ]
    assert build_review_threshold_summary_lines({}) == []


def test_data_review_summary_cli_help():
    result = subprocess.run(
        [sys.executable, "data_review_summary.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--data-dir" in result.stdout
    assert "--json" in result.stdout
    assert "--fail-on-issues" in result.stdout
    assert "--max-loadout-warnings" in result.stdout
    assert "--thresholds" in result.stdout


def test_data_review_summary_cli_writes_threshold_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    output = tmp_path / "thresholds.json"

    result = subprocess.run(
        [sys.executable, "data_review_summary.py", "--data-dir", str(data_dir), "--write-thresholds", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Wrote review thresholds" in result.stdout
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "audit_warnings": 0,
        "loadout_warnings": 0,
        "no_weapon_units": 0,
        "suspicious_weapon_warnings": 0,
        "unit_profile_warnings": 0,
    }


def test_data_review_summary_cli_prints_thresholds_and_gate_pass(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text('{"loadout_warnings": 0, "no_weapon_units": 0}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "data_review_summary.py",
            "--data-dir",
            str(data_dir),
            "--fail-on-issues",
            "--thresholds",
            str(thresholds),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Review gate thresholds:" in result.stdout
    assert "- loadout warnings: 0" in result.stdout
    assert "Data review gate passed." in result.stdout
