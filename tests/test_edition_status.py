from warhammer.edition_status import build_edition_status, edition_dir_name, read_metadata


def test_edition_dir_name_normalizes_empty_and_mixed_case_values():
    assert edition_dir_name(" 10E ") == "10e"
    assert edition_dir_name("") == "10e"


def test_build_edition_status_reports_ready_supported_edition(tmp_path):
    metadata = {"rules_edition": "10e", "counts": {"units": 1, "weapons": 2}}
    audit_report = {"summary": {"error": 0, "warning": 1, "info": 0, "total": 1}}

    status = build_edition_status(
        tmp_path,
        "10e",
        {"commit": "abc", "dirty": False},
        audit_report,
        metadata=metadata,
    )

    assert status["edition"] == "10e"
    assert status["rules_available"] is True
    assert status["calculations_enabled"] is True
    assert status["status"] == "ready"
    assert status["blockers"] == []
    assert status["counts"]["weapons"] == 2
    assert {item["key"] for item in status["rule_capabilities"]} >= {
        "hit_rolls",
        "wound_rolls",
        "save_resolution",
        "model_removal",
    }


def test_build_edition_status_blocks_unsupported_edition(tmp_path):
    status = build_edition_status(
        tmp_path,
        "11e",
        {"commit": "abc"},
        {"summary": {"error": 0}},
        metadata={"rules_edition": "11e", "counts": {"units": 1}},
    )

    assert status["edition"] == "11e"
    assert status["rules_available"] is False
    assert status["calculations_enabled"] is False
    assert status["status"] == "blocked"
    assert "Ruleset not implemented" in status["blockers"]
    assert status["rule_capabilities"] == []


def test_read_metadata_ignores_missing_invalid_or_non_object_files(tmp_path):
    assert read_metadata(tmp_path) == {}

    (tmp_path / "metadata.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert read_metadata(tmp_path) == {}

    (tmp_path / "metadata.json").write_text('{"rules_edition":"10e"}', encoding="utf-8")
    assert read_metadata(tmp_path) == {"rules_edition": "10e"}
