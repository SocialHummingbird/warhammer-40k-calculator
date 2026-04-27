from pathlib import Path

from warhammer.update_summary import build_update_summary_lines


def test_build_update_summary_lines_includes_core_update_counts():
    lines = build_update_summary_lines(
        {"commit": "old"},
        {
            "remote_origin": "https://github.com/BSData/wh40k-10e.git",
            "commit": "new",
            "commit_subject": "Update data",
        },
        {
            "tables": {
                "units": {
                    "before_count": 10,
                    "after_count": 12,
                    "delta": 2,
                    "changed_count": 1,
                }
            }
        },
        {"summary": {"error": 0, "warning": 2, "info": 3}},
        Path("data/10e/snapshots/new"),
        {
            "weapon_profiles": 100,
            "suspicious_weapon_profiles": 4,
            "unit_profile_issue_rows": 1,
            "ability_profiles": 50,
            "ability_modifiers": 9,
            "unit_name_variants": 2,
            "unit_weapon_coverage_rows": 80,
            "loadout_review_rows": 7,
            "source_catalogue_review_rows": 20,
        },
        5,
        {
            "feature_rows": 1000,
            "feature_set": "pre_match",
            "model_type": "centroid",
            "model_path": Path("models/10e/matchup_centroid_model.json"),
        },
    )

    assert lines[0] == "Database update complete."
    assert "Commit: old -> new" in lines
    assert "  units: 10 -> 12 (+2), changed 1" in lines
    assert "Audit samples: 0 errors, 2 warnings, 3 info" in lines
    assert "Schema review: 5 table rows" in lines
    assert "Snapshot: data\\10e\\snapshots\\new" in lines
    assert "ML artifacts: 1000 feature rows, feature set pre_match, model type centroid, model models\\10e\\matchup_centroid_model.json" in lines


def test_build_update_summary_lines_omits_optional_snapshot_and_ml():
    lines = build_update_summary_lines(
        {"commit": "old"},
        {"remote_origin": "origin", "commit": "new", "commit_subject": "subject"},
        {"tables": {}},
        {"summary": {"error": 0, "warning": 0, "info": 0}},
        None,
        {"weapon_profiles": 1, "ability_profiles": 2},
        3,
        None,
    )

    assert not any(line.startswith("Snapshot:") for line in lines)
    assert not any(line.startswith("ML artifacts:") for line in lines)
    assert any("1 weapons" in line for line in lines)
