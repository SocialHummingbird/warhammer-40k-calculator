import hashlib
import json

from warhammer.data_review import (
    data_review_payload,
    download_file_request_parts,
    review_file_content_type,
    source_info_from_metadata,
)


def test_data_review_payload_loads_generated_reports(tmp_path):
    (tmp_path / "audit_report.json").write_text('{"summary": {"error": 1}}', encoding="utf-8")
    (tmp_path / "import_diff.json").write_text('{"tables": {"units": {"delta": 2}}}', encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"counts": {"units": 3}}', encoding="utf-8")
    (tmp_path / "edition_status.json").write_text('{"edition": "10e", "status": "ready"}', encoding="utf-8")
    (tmp_path / "edition_readiness.md").write_text("# Edition Readiness Report\n", encoding="utf-8")
    (tmp_path / "unit_footprint_review.md").write_text("# Unit Footprint Review\n", encoding="utf-8")
    (tmp_path / "update_report.md").write_text("# Update\n\nStatus: PASS\n", encoding="utf-8")
    (tmp_path / "profile_review.md").write_text("# Imported Profile Review\n\nWeapon profiles: 1\n", encoding="utf-8")
    (tmp_path / "weapon_profile_review.csv").write_text("unit_name,weapon_name\nBoyz,Choppa\n", encoding="utf-8")

    payload = data_review_payload(tmp_path)

    assert payload["audit_report"]["summary"]["error"] == 1
    assert payload["import_diff"]["tables"]["units"]["delta"] == 2
    assert payload["metadata"]["counts"]["units"] == 3
    assert payload["edition_status"]["status"] == "ready"
    assert payload["artifact_manifest"] is None
    assert payload["verification_report"] is None
    assert payload["suspicious_weapon_summary"] is None
    assert payload["unit_profile_summary"] is None
    assert payload["loadout_summary"] is None
    assert payload["source_catalogue_summary"] is None
    assert payload["unit_variant_summary"] is None
    assert payload["weapon_coverage_summary"] is None
    assert payload["unit_footprint_summary"] is None
    assert payload["unit_footprint_suggestion_summary"] is None
    assert payload["unit_footprint_template_summary"] is None
    assert payload["unit_footprint_queue_summary"] is None
    assert payload["unit_footprint_review"] == "# Unit Footprint Review\n"
    assert payload["ability_modifier_summary"] is None
    assert payload["schema_summary"] is None
    assert "Status: PASS" in payload["update_report"]
    assert "Imported Profile Review" in payload["profile_review"]
    assert payload["edition_readiness"] == "# Edition Readiness Report\n"
    assert payload["model_audit"] is None
    assert payload["model_comparison"] is None
    assert payload["model_files"] == []
    assert payload["review_files"][0]["href"].startswith("/api/review-files/10e/")
    assert {file["filename"] for file in payload["review_files"]} == {
        "weapon_profile_review.csv",
        "edition_status.json",
        "edition_readiness.md",
        "unit_footprint_review.md",
        "profile_review.md",
        "update_report.md",
    }


def test_data_review_payload_tolerates_missing_data_dir():
    assert data_review_payload(None) == {
        "audit_report": None,
        "import_diff": None,
        "metadata": None,
        "edition_status": None,
        "artifact_manifest": None,
        "verification_report": None,
        "suspicious_weapon_summary": None,
        "unit_profile_summary": None,
        "loadout_summary": None,
        "source_catalogue_summary": None,
        "unit_variant_summary": None,
        "weapon_coverage_summary": None,
        "unit_footprint_summary": None,
        "unit_footprint_suggestion_summary": None,
        "unit_footprint_template_summary": None,
        "unit_footprint_queue_summary": None,
        "unit_footprint_review": None,
        "ability_modifier_summary": None,
        "schema_summary": None,
        "update_report": None,
        "profile_review": None,
        "edition_readiness": None,
        "model_audit": None,
        "model_comparison": None,
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
    (model_dir / "model_comparison.md").write_text("# ML Model Comparison\n", encoding="utf-8")

    payload = data_review_payload(data_dir, edition="10e", model_dir=model_dir)

    assert payload["model_audit"] == "# ML Model Audit\n"
    assert payload["model_comparison"] == "# ML Model Comparison\n"
    assert {file["filename"] for file in payload["model_files"]} == {
        "matchup_centroid_model.md",
        "matchup_centroid_model.json",
        "model_comparison.md",
    }
    assert all(file["href"].startswith("/api/ml-model-files/10e/") for file in payload["model_files"])


def test_data_review_payload_includes_artifact_verification(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    manifest = {
        "source": {"commit": "abc"},
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "edition": "10e",
            "feature_set": "pre_match",
            "feature_rows": 10,
            "artifacts": {},
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = data_review_payload(tmp_path)

    assert payload["artifact_manifest"]["source"]["commit"] == "abc"
    assert payload["artifact_manifest"]["linked_ml_artifacts"]["feature_rows"] == 10
    assert payload["verification_report"]["ok"] is True
    assert payload["verification_report"]["ok_count"] == 1


def test_data_review_payload_summarizes_suspicious_weapons(tmp_path):
    (tmp_path / "suspicious_weapon_review.csv").write_text(
        "\n".join(
            [
                "review_severity,review_category,faction,unit_name,weapon_name,weapon_type,attacks,strength,ap,damage,damage_parse_status,raw_damage_throughput,review_reason,source_file",
                "error,missing_damage,Test,Broken,Blank Gun,ranged,1,4,0,,empty,0.00,empty damage expression; zero damage average,Test.cat",
                "warning,extreme_profile,Test,Titan,Large Gun,ranged,30,20,-5,3,ok,90.00,very high raw damage throughput,Test.cat",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["suspicious_weapon_summary"]

    assert summary["total"] == 2
    assert summary["by_severity"] == {"error": 1, "warning": 1}
    assert summary["by_category"] == {"extreme_profile": 1, "missing_damage": 1}
    assert summary["by_reason"]["empty damage expression"] == 1
    assert summary["rows"][0]["weapon_name"] == "Blank Gun"


def test_data_review_payload_summarizes_unit_profiles(tmp_path):
    (tmp_path / "unit_profile_review.csv").write_text(
        "\n".join(
            [
                "review_severity,review_category,faction,unit_name,selection_type,unit_id,source_file,toughness,save,wounds,points,models_min,models_max,review_reason",
                "warning,unit_points_unset,Test,Missing Points,unit,u1,Test.cat,4,3+,2,,1,1,missing points",
                "error,core_stats,Test,Bad Save,unit,u2,Test.cat,4,5,2,25,1,1,missing or invalid save",
                ",ok,Test,OK,unit,u3,Test.cat,4,3+,2,80,5,10,",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_profile_summary"]

    assert summary["total"] == 3
    assert summary["issue_total"] == 2
    assert summary["by_severity"] == {"error": 1, "ok": 1, "warning": 1}
    assert summary["by_category"] == {"core_stats": 1, "ok": 1, "unit_points_unset": 1}
    assert summary["by_reason"]["missing points"] == 1
    assert summary["rows"][0]["unit_name"] == "Missing Points"
    assert summary["rows"][0]["category"] == "unit_points_unset"
    assert summary["rows"][1]["save"] == "5"


def test_data_review_payload_summarizes_loadouts(tmp_path):
    (tmp_path / "loadout_review.csv").write_text(
        "\n".join(
            [
                "review_severity,review_category,faction,unit_name,selection_type,source_file,points,models_min,models_max,total_weapons,ranged_weapons,ranged_weapons_with_range,ranged_weapons_missing_range,melee_weapons,coverage,review_reason",
                "warning,many_profiles,Test,Tactical Squad,unit,Test.cat,140,10,10,26,20,17,3,6,both,many imported weapon profiles; many ranged profiles",
                "info,legends_profile,Test,Command Squad [Legends],unit,Test.cat,165,7,7,18,10,10,0,8,both,mixed loadout profiles",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["loadout_summary"]

    assert summary["total"] == 2
    assert summary["by_severity"] == {"info": 1, "warning": 1}
    assert summary["by_category"] == {"legends_profile": 1, "many_profiles": 1}
    assert summary["by_reason"]["many imported weapon profiles"] == 1
    assert summary["rows"][0]["unit_name"] == "Tactical Squad"
    assert summary["rows"][0]["total_weapons"] == "26"
    assert summary["rows"][0]["ranged_weapons_missing_range"] == "3"


def test_data_review_payload_summarizes_source_catalogues(tmp_path):
    (tmp_path / "source_catalogue_review.csv").write_text(
        "\n".join(
            [
                "source_file,source_url,factions,units,weapon_profiles,ability_profiles,suspicious_weapon_profiles,unit_profile_issue_rows,loadout_review_rows,duplicate_name_unit_rows,no_weapon_units,ranged_weapons_missing_range",
                "Space Marines.cat,https://example.test/Space%20Marines.cat,Imperium,132,1342,200,0,1,39,10,2,12",
                "Orks.cat,https://example.test/Orks.cat,Xenos,97,501,100,7,0,10,4,1,5",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["source_catalogue_summary"]

    assert summary["total"] == 2
    assert summary["totals"]["units"] == 229
    assert summary["totals"]["suspicious_weapon_profiles"] == 7
    assert summary["totals"]["ranged_weapons_missing_range"] == 17
    assert summary["rows"][0]["source_file"] == "Space Marines.cat"
    assert summary["rows"][0]["unit_profile_issue_rows"] == "1"
    assert summary["rows"][1]["source_url"] == "https://example.test/Orks.cat"


def test_data_review_payload_summarizes_unit_variants(tmp_path):
    (tmp_path / "unit_variant_review.csv").write_text(
        "\n".join(
            [
                "unit_name,variant_count,unit_id,source_file,faction,selection_type,points,models_min,models_max,toughness,save,wounds",
                "Rhino,2,u1,Chaos.cat,Chaos,model,75,1,1,9,3+,10",
                "Rhino,2,u2,Space Marines.cat,Imperium,model,75,1,1,9,3+,10",
                "Land Raider,3,u3,Chaos.cat,Chaos,model,240,1,1,12,2+,16",
                "Land Raider,3,u4,Space Marines.cat,Imperium,model,265,1,1,12,2+,16",
                "Land Raider,3,u5,Grey Knights.cat,Imperium,model,240,1,1,12,2+,16",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_variant_summary"]

    assert summary["total_rows"] == 5
    assert summary["duplicate_names"] == 2
    assert summary["max_variant_count"] == 3
    assert summary["rows"][0]["unit_name"] == "Land Raider"
    assert summary["rows"][0]["variant_count"] == "3"
    assert summary["rows"][0]["points"] == "240; 265"


def test_data_review_payload_summarizes_weapon_coverage(tmp_path):
    (tmp_path / "unit_weapon_coverage_review.csv").write_text(
        "\n".join(
            [
                "faction,unit_name,selection_type,unit_id,source_file,points,models_min,models_max,total_weapons,ranged_weapons,ranged_weapons_with_range,ranged_weapons_missing_range,melee_weapons,coverage",
                "Test,Tactical Squad,unit,u1,Test.cat,140,10,10,2,1,1,0,1,both",
                "Test,Drop Pod,model,u2,Test.cat,70,1,1,0,0,0,0,0,no_weapons",
                "Test,Sword Unit,unit,u3,Test.cat,90,5,5,1,0,0,0,1,melee_only",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["weapon_coverage_summary"]

    assert summary["total"] == 3
    assert summary["by_coverage"] == {"both": 1, "melee_only": 1, "no_weapons": 1}
    assert summary["no_weapon_total"] == 1
    assert summary["ranged_weapons_with_range"] == 1
    assert summary["ranged_weapons_missing_range"] == 0
    assert summary["rows"][0]["unit_name"] == "Drop Pod"
    assert summary["rows"][0]["coverage"] == "no_weapons"


def test_data_review_payload_summarizes_unit_footprints(tmp_path):
    (tmp_path / "unit_footprint_review.csv").write_text(
        "\n".join(
            [
                "review_severity,review_category,unit_id,faction,unit_name,selection_type,models_min,models_max,footprint_status,base_type,base_shape,base_width_mm,base_depth_mm,guide_faction,guide_unit_name,guide_model_name,source,source_url,source_updated,match_method,match_confidence,review_reason",
                "warning,unmatched_unit,u1,Test,Missing Base,unit,5,10,unmatched,,,,,,,,guide,url,January 2026,none,0.00,no guide match",
                "info,mixed_or_multi_base_unit,u2,Test,Mixed Base,unit,11,11,review,round,round,40,40,TEST,Mixed Base,Platform,guide,url,January 2026,exact_name_faction,0.70,multiple official rows",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_footprint_summary"]

    assert summary["total"] == 2
    assert summary["by_severity"] == {"info": 1, "warning": 1}
    assert summary["by_category"] == {"mixed_or_multi_base_unit": 1, "unmatched_unit": 1}
    assert summary["by_status"] == {"review": 1, "unmatched": 1}
    assert summary["rows"][0]["unit_name"] == "Missing Base"
    assert summary["rows"][1]["base_width_mm"] == "40"


def test_data_review_payload_summarizes_unit_footprint_suggestions(tmp_path):
    (tmp_path / "unit_footprint_suggestions.csv").write_text(
        "\n".join(
            [
                "unit_id,faction,unit_name,selection_type,models_min,models_max,suggestion_rank,suggestion_score,suggestion_reason,guide_faction,guide_unit_name,guide_model_name,base_size_text,base_type,base_shape,base_width_mm,base_depth_mm,source_page,source,source_url,source_updated",
                "u1,Test,Autarch Skyrunner,model,1,1,1,0.72,similar name,AELDARI,Farseer Skyrunner,,Small Flying Base,small_flying_base,flying,,,22,guide,https://example.test/base-guide.pdf,January 2026",
                "u2,Test,Odd Unit,model,1,1,1,0.58,weak name,AELDARI,Other Unit,,32mm,round,round,32,32,23,guide,https://example.test/base-guide.pdf,January 2026",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_footprint_suggestion_summary"]

    assert summary["total"] == 2
    assert summary["unit_total"] == 2
    assert summary["by_score_band"] == {"low": 1, "medium": 1}
    assert summary["by_faction"] == {"Test": 2}
    assert summary["rows"][0]["unit_name"] == "Autarch Skyrunner"
    assert summary["rows"][0]["guide_unit_name"] == "Farseer Skyrunner"
    assert summary["rows"][0]["source_page"] == "22"
    assert summary["rows"][0]["source_url"] == "https://example.test/base-guide.pdf"


def test_data_review_payload_summarizes_unit_footprint_override_template(tmp_path):
    (tmp_path / "unit_footprint_override_template.csv").write_text(
        "\n".join(
            [
                "unit_id,unit_name,faction_contains,suggested_guide_unit_name,suggested_base_size_text,override_base_size_text,review_decision",
                "ready,Ready Unit,Test,Official Unit,40mm,,accept_suggestion",
                "manual,Manual Unit,Test,,,90x52.5mm Oval Base,override",
                "invalid,Invalid Unit,Test,,,,accept_suggestion",
                "blank,Blank Unit,Test,,,,",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_overrides.csv").write_text(
        "unit_id,unit_name\n",
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_footprint_template_summary"]

    assert summary["total"] == 4
    assert summary["ready_total"] == 2
    assert summary["invalid_total"] == 1
    assert summary["blank_total"] == 1
    assert summary["by_status"]["accept_suggestion_ready"] == 1
    assert summary["by_status"]["override_ready"] == 1
    assert summary["rows"][0]["unit_id"] == "invalid"
    assert "missing" in summary["rows"][0]["reason"]


def test_data_review_payload_summarizes_unit_footprint_review_queue(tmp_path):
    (tmp_path / "unit_footprint_review_queue.csv").write_text(
        "\n".join(
            [
                "review_rank,review_priority,review_hint,unit_id,unit_name,faction_contains,models_min,models_max,suggestion_score,suggested_guide_faction,suggested_guide_unit_name,suggested_guide_model_name,suggested_base_size_text,suggested_source_page,suggested_source_url,suggested_source_updated",
                "1,review_suggestion_high,Check same datasheet,u1,Commander in Crisis Battlesuit [Legends],Xenos - T'au Empire,1,1,0.86,T'AU EMPIRE,Commander in Enforcer Battlesuit,,60mm,48,https://example.test/base-guide.pdf,January 2026",
                "2,no_suggestion,Research official base,u2,Unknown Unit,Test,1,1,,,,,,,,",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["unit_footprint_queue_summary"]

    assert summary["total"] == 2
    assert summary["by_priority"] == {"no_suggestion": 1, "review_suggestion_high": 1}
    assert summary["by_faction"]["Xenos - T'au Empire"] == 1
    assert summary["rows"][0]["review_rank"] == "1"
    assert summary["rows"][0]["suggested_guide_unit_name"] == "Commander in Enforcer Battlesuit"
    assert summary["rows"][0]["suggested_source_page"] == "48"
    assert summary["rows"][0]["suggested_source_url"] == "https://example.test/base-guide.pdf"
    assert summary["rows"][1]["review_priority"] == "no_suggestion"


def test_data_review_payload_summarizes_ability_modifiers(tmp_path):
    (tmp_path / "ability_modifier_review.csv").write_text(
        "\n".join(
            [
                "faction,unit_name,selection_type,unit_id,source_file,modifier_type,source,description,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,grants,anti_rules,ignores_cover,applies_to_ranged,applies_to_melee,target_keywords,damage_reduction",
                "Test,Farseer,model,u1,Test.cat,attack_modifier,Guide,Text,1,0,,,,,,true,false,,",
                "Test,Tank,model,u2,Test.cat,damage_reduction,Armour,Text,,,,,,,,,,,1.00",
                "Test,Flamer,model,u3,Test.cat,attack_modifier,Torrent Gift,Text,0,0,,,Torrent,,false,true,false,,",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["ability_modifier_summary"]

    assert summary["total"] == 3
    assert summary["by_type"] == {"attack_modifier": 2, "damage_reduction": 1}
    assert summary["by_grant"] == {"Torrent": 1}
    assert summary["rows"][0]["unit_name"] == "Farseer"
    assert summary["rows"][0]["hit_modifier"] == "1"
    assert summary["rows"][2]["damage_reduction"] == "1.00"


def test_data_review_payload_summarizes_schema_review(tmp_path):
    (tmp_path / "schema_review.csv").write_text(
        "\n".join(
            [
                "table,file,status,required_count,actual_count,missing_columns,extra_columns,required_columns,actual_columns",
                "units,units.csv,pass,3,3,,,unit_id; name; wounds,unit_id; name; wounds",
                "weapons,weapons.csv,fail,4,3,damage,,weapon_id; unit_id; name; damage,weapon_id; unit_id; name",
            ]
        ),
        encoding="utf-8",
    )

    payload = data_review_payload(tmp_path)
    summary = payload["schema_summary"]

    assert summary["total"] == 2
    assert summary["by_status"] == {"fail": 1, "pass": 1}
    assert summary["rows"][0]["table"] == "weapons"
    assert summary["rows"][0]["missing_columns"] == "damage"
    assert summary["rows"][1]["status"] == "pass"


def test_review_file_content_type():
    assert review_file_content_type("weapon_profile_review.csv").startswith("text/csv")
    assert review_file_content_type("edition_status.json").startswith("application/json")
    assert review_file_content_type("profile_review.md").startswith("text/markdown")


def test_download_file_request_parts_extracts_edition_and_filename():
    assert download_file_request_parts(
        "/api/review-files/10e/weapon_profile_review.csv",
        prefix="/api/review-files/",
        default_edition="10e",
    ) == ("10e", "weapon_profile_review.csv")
    assert download_file_request_parts(
        "/api/ml-model-files/11e/../matchup_centroid_model.json",
        prefix="/api/ml-model-files/",
        default_edition="10e",
    ) == ("11e", "matchup_centroid_model.json")
    assert download_file_request_parts(
        "profile_review.md",
        prefix="/api/review-files/",
        default_edition="10e",
    ) == ("10e", "profile_review.md")


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
