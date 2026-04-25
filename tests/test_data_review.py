from warhammer.data_review import (
    data_review_payload,
    review_file_content_type,
    source_info_from_metadata,
)


def test_data_review_payload_loads_generated_reports(tmp_path):
    (tmp_path / "audit_report.json").write_text('{"summary": {"error": 1}}', encoding="utf-8")
    (tmp_path / "import_diff.json").write_text('{"tables": {"units": {"delta": 2}}}', encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"counts": {"units": 3}}', encoding="utf-8")
    (tmp_path / "edition_status.json").write_text('{"edition": "10e", "status": "ready"}', encoding="utf-8")
    (tmp_path / "update_report.md").write_text("# Update\n\nStatus: PASS\n", encoding="utf-8")
    (tmp_path / "profile_review.md").write_text("# Imported Profile Review\n\nWeapon profiles: 1\n", encoding="utf-8")
    (tmp_path / "weapon_profile_review.csv").write_text("unit_name,weapon_name\nBoyz,Choppa\n", encoding="utf-8")

    payload = data_review_payload(tmp_path)

    assert payload["audit_report"]["summary"]["error"] == 1
    assert payload["import_diff"]["tables"]["units"]["delta"] == 2
    assert payload["metadata"]["counts"]["units"] == 3
    assert payload["edition_status"]["status"] == "ready"
    assert "Status: PASS" in payload["update_report"]
    assert "Imported Profile Review" in payload["profile_review"]
    assert payload["model_audit"] is None
    assert payload["model_files"] == []
    assert payload["review_files"][0]["href"].startswith("/api/review-files/10e/")
    assert {file["filename"] for file in payload["review_files"]} == {
        "weapon_profile_review.csv",
        "edition_status.json",
        "profile_review.md",
        "update_report.md",
    }


def test_data_review_payload_tolerates_missing_data_dir():
    assert data_review_payload(None) == {
        "audit_report": None,
        "import_diff": None,
        "metadata": None,
        "edition_status": None,
        "update_report": None,
        "profile_review": None,
        "model_audit": None,
        "review_files": [],
        "model_files": [],
        "edition": "10e",
    }


def test_data_review_payload_includes_model_audit_files(tmp_path):
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models" / "10e"
    data_dir.mkdir()
    model_dir.mkdir(parents=True)
    (model_dir / "matchup_centroid_model.md").write_text("# ML Model Audit\n", encoding="utf-8")
    (model_dir / "matchup_centroid_model.json").write_text('{"model_type":"test"}', encoding="utf-8")

    payload = data_review_payload(data_dir, edition="10e", model_dir=model_dir)

    assert payload["model_audit"] == "# ML Model Audit\n"
    assert {file["filename"] for file in payload["model_files"]} == {
        "matchup_centroid_model.md",
        "matchup_centroid_model.json",
    }
    assert all(file["href"].startswith("/api/ml-model-files/10e/") for file in payload["model_files"])


def test_review_file_content_type():
    assert review_file_content_type("weapon_profile_review.csv").startswith("text/csv")
    assert review_file_content_type("edition_status.json").startswith("application/json")
    assert review_file_content_type("profile_review.md").startswith("text/markdown")


def test_source_info_from_metadata_summarizes_commit_and_generation():
    payload = source_info_from_metadata(
        {
            "generated_at": "2026-04-25T12:00:00Z",
            "github_ref": "main",
            "source_revisions": [
                {
                    "commit": "32b4525d9f69f062f3458d517c6cf82512ef6fef",
                    "branch": "main",
                    "remote_origin": "https://github.com/BSData/wh40k-10e.git",
                    "dirty": False,
                }
            ],
        }
    )

    assert payload == {
        "commit": "32b4525d9f69f062f3458d517c6cf82512ef6fef",
        "commit_short": "32b4525d9f69",
        "branch": "main",
        "remote_origin": "https://github.com/BSData/wh40k-10e.git",
        "dirty": False,
        "generated_at": "2026-04-25T12:00:00Z",
        "rules_edition": "10e",
        "supported_rules_editions": ["10e"],
    }
