import pytest

from warhammer import webapp
from warhammer import api_payloads
from warhammer import data_review
from warhammer import matchup_payloads
from warhammer import unit_search
from warhammer import web_state
from warhammer.context import EngagementContext
from warhammer.matchups import evaluate_unit_with_weapon_filter
from warhammer.profiles import UnitProfile


def _unit(name, weapon_type="ranged", faction="", keywords=None, weapons=None):
    return UnitProfile.from_dict(
        {
            "name": name,
            "faction": faction,
            "source_file": "Test.cat",
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "weapons": weapons or [
                {
                    "name": "Test Weapon",
                    "type": weapon_type,
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                    "source_file": "Test.cat",
                }
            ],
            "keywords": keywords or ["Infantry"],
        }
    )


def test_context_from_payload_normalises_values():
    context = api_payloads.context_from_payload(
        {
            "attacker_advanced": True,
            "target_model_count": "10",
            "target_in_cover": True,
        }
    )

    assert context.attacker_advanced is True
    assert context.attacker_moved is True
    assert context.target_model_count == 10
    assert context.target_in_cover is True


def test_context_from_payload_parses_string_booleans():
    context = api_payloads.context_from_payload(
        {
            "attacker_moved": "false",
            "attacker_advanced": "true",
            "target_within_half_range": "0",
            "target_in_cover": "1",
        }
    )

    assert context.attacker_moved is True
    assert context.attacker_advanced is True
    assert context.target_within_half_range is False
    assert context.target_in_cover is True


def test_context_from_payload_rejects_invalid_target_model_count():
    with pytest.raises(ValueError, match="target_model_count"):
        api_payloads.context_from_payload({"target_model_count": "0"})


def test_context_from_payload_rejects_invalid_booleans():
    with pytest.raises(ValueError, match="attacker_moved"):
        api_payloads.context_from_payload({"attacker_moved": "sometimes"})


def test_optional_weapon_name_normalises_blank_and_all_values():
    assert api_payloads.optional_weapon_name("") is None
    assert api_payloads.optional_weapon_name("__all__") is None
    assert api_payloads.optional_weapon_name("  Bolt rifle ") == "Bolt rifle"
    with pytest.raises(ValueError, match="weapon filters"):
        api_payloads.optional_weapon_name(12)


def test_optional_unit_id_normalises_blank_values():
    assert api_payloads.optional_unit_id("") is None
    assert api_payloads.optional_unit_id("  abc ") == "abc"
    with pytest.raises(ValueError, match="unit ids"):
        api_payloads.optional_unit_id(12)


def test_contexts_from_payload_keeps_return_strike_independent():
    outgoing, incoming = api_payloads.contexts_from_payload(
        {
            "context": {
                "attacker_advanced": True,
                "target_in_cover": True,
            }
        }
    )

    assert outgoing.attacker_advanced is True
    assert outgoing.target_in_cover is True
    assert incoming.attacker_advanced is False
    assert incoming.target_in_cover is False


def test_contexts_from_payload_accepts_explicit_return_context():
    outgoing, incoming = api_payloads.contexts_from_payload(
        {
            "outgoing_context": {"target_within_half_range": True},
            "incoming_context": {"attacker_moved": True, "target_model_count": 3},
        }
    )

    assert outgoing.target_within_half_range is True
    assert incoming.attacker_moved is True
    assert incoming.target_model_count == 3


def test_evaluate_unit_with_weapon_filter_limits_results_to_matching_weapon():
    attacker = _unit(
        "Shooter",
        weapons=[
            {"name": "Light gun", "type": "ranged", "attacks": "1", "skill": "3+", "strength": 4, "ap": 0, "damage": "1"},
            {"name": "Heavy gun", "type": "ranged", "attacks": "2", "skill": "3+", "strength": 8, "ap": -2, "damage": "3"},
        ],
    )
    defender = _unit("Target")

    result = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name="Heavy gun",
        multiplier=1,
    )

    assert [weapon_result.weapon.name for weapon_result in result.weapons] == ["Heavy gun"]


def test_evaluate_unit_with_weapon_filter_rejects_missing_weapon():
    attacker = _unit("Shooter")
    defender = _unit("Target")

    with pytest.raises(ValueError, match="no ranged weapon"):
        evaluate_unit_with_weapon_filter(
            attacker,
            defender,
            "ranged",
            context=EngagementContext(),
            weapon_name="Missing",
            multiplier=1,
        )


def test_evaluate_unit_with_weapon_filter_applies_multiplier():
    attacker = _unit("Shooter")
    defender = _unit("Target")

    base = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name=None,
        multiplier=1,
    )
    scaled = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name=None,
        multiplier=4,
    )

    assert scaled.total_damage == pytest.approx(base.total_damage * 4)
    assert scaled.weapons[0].attacks == pytest.approx(base.weapons[0].attacks * 4)


def test_unit_and_weapon_serializers_are_json_ready():
    unit = _unit("Serializer")

    payload = matchup_payloads.unit_detail(unit)

    assert payload["name"] == "Serializer"
    assert payload["source_file"] == "Test.cat"
    assert payload["weapons"][0]["name"] == "Test Weapon"
    assert payload["weapons"][0]["source_file"] == "Test.cat"
    assert payload["keywords"] == ["Infantry"]


def test_result_serializers_include_estimated_points_removed():
    attacker = _unit("Shooter")
    defender = UnitProfile.from_dict(
        {
            "name": "Target",
            "toughness": 4,
            "save": "7+",
            "wounds": 1,
            "points": 100,
            "models_min": 10,
            "models_max": 10,
            "weapons": [],
        }
    )

    result = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name=None,
        multiplier=1,
    )
    payload = matchup_payloads.unit_result(result, target=defender)

    assert payload["points_per_model"] == pytest.approx(10)
    assert payload["estimated_points_removed"] == pytest.approx(payload["expected_models_destroyed"] * 10)
    assert payload["weapons"][0]["estimated_points_removed"] == pytest.approx(
        payload["weapons"][0]["expected_models_destroyed"] * 10
    )


def test_matchup_judgement_prefers_points_removed_when_available():
    attacker = UnitProfile.from_dict(
        {
            "name": "Cheap attacker",
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": 50,
            "models_min": 1,
            "models_max": 1,
            "weapons": [],
        }
    )
    defender = UnitProfile.from_dict(
        {
            "name": "Expensive defender",
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": 300,
            "models_min": 1,
            "models_max": 1,
            "weapons": [],
        }
    )

    judgement = matchup_payloads.matchup_judgement(
        attacker,
        defender,
        outgoing={"total_damage": 2.0, "estimated_points_removed": 120.0},
        incoming={"total_damage": 6.0, "estimated_points_removed": 40.0},
    )

    assert judgement["basis"] == "points_removed"
    assert judgement["winner"] == "Cheap attacker"
    assert "estimated points removed" in judgement["body"]
    assert "Damage context" in judgement["body"]


def test_matchup_judgement_falls_back_to_damage_without_points():
    attacker = _unit("Attacker")
    defender = _unit("Defender")

    judgement = matchup_payloads.matchup_judgement(
        attacker,
        defender,
        outgoing={"total_damage": 1.0, "estimated_points_removed": None},
        incoming={"total_damage": 3.0, "estimated_points_removed": None},
    )

    assert judgement["basis"] == "damage"
    assert judgement["winner"] == "Defender"


def test_app_state_requires_exact_unit_name(tmp_path, monkeypatch):
    units = {"alpha": _unit("Alpha")}

    monkeypatch.setattr(web_state, "load_units_from_json", lambda path: units)

    state = web_state.AppState(csv_dir=None, json_path=tmp_path / "units.json")

    assert state.require_unit("Alpha").name == "Alpha"
    with pytest.raises(KeyError):
        state.require_unit("Missing")


def test_app_state_preserves_duplicate_csv_unit_names(tmp_path):
    (tmp_path / "units.csv").write_text(
        "\n".join(
            [
                "unit_id,faction,name,toughness,save,invulnerable_save,wounds,move,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type",
                "u1,Faction A,Shared Name,4,3+,,2,,6+,1,100,1,1,,,unit",
                "u2,Faction B,Shared Name,5,2+,,3,,6+,1,200,1,1,,,unit",
            ]
        ),
        encoding="utf-8",
    )
    for filename, header in {
        "weapons.csv": "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords",
        "abilities.csv": "ability_id,source_type,source_id,name,text",
        "keywords.csv": "keyword_id,keyword",
        "unit_keywords.csv": "unit_id,keyword_id",
    }.items():
        (tmp_path / filename).write_text(header + "\n", encoding="utf-8")

    state = web_state.AppState(csv_dir=tmp_path, json_path=None)

    assert len(state.units) == 2
    assert state.require_unit("Shared Name", unit_id="u2").faction == "Faction B"
    assert matchup_payloads.unit_summary(state.require_unit("Shared Name", unit_id="u1"))["id"] == "u1"


def test_app_state_loads_explicit_model_path_for_active_edition(tmp_path, monkeypatch):
    units = {"alpha": _unit("Alpha")}
    selected_model = tmp_path / "selected_model.json"
    selected_model.write_text('{"model_type": "custom"}', encoding="utf-8")
    loaded_paths = []

    monkeypatch.setattr(web_state, "load_units_from_json", lambda path: units)
    monkeypatch.setattr(web_state, "load_advisory_model", lambda path: loaded_paths.append(path) or {"model_type": "custom"})

    state = web_state.AppState(csv_dir=None, json_path=tmp_path / "units.json", model_path=selected_model)

    assert state.ml_model_path_for_edition("10e") == selected_model
    assert state.ml_model_dir_for_edition("10e") == tmp_path
    assert state.ml_model_for_edition("10e") == {"model_type": "custom"}
    assert loaded_paths[0] == selected_model


def test_unit_search_filters_by_faction_keywords_and_limit():
    units = [
        _unit("Ork Boy", faction="Xenos - Orks", keywords=["Infantry"]),
        _unit("Intercessor", faction="Imperium - Space Marines", keywords=["Infantry"]),
        _unit("Rhino", faction="Imperium - Space Marines", keywords=["Vehicle"]),
    ]

    assert [unit.name for unit in unit_search.search_units(units, text="vehicle")] == ["Rhino"]
    assert [unit.name for unit in unit_search.search_units(units, faction="Imperium - Space Marines", limit=1)] == ["Intercessor"]
    assert unit_search.unit_factions(units) == ["Imperium - Space Marines", "Xenos - Orks"]


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

    payload = data_review.data_review_payload(tmp_path)

    assert payload["audit_report"]["summary"]["error"] == 1
    assert payload["import_diff"]["tables"]["units"]["delta"] == 2
    assert payload["metadata"]["counts"]["units"] == 3
    assert payload["edition_status"]["status"] == "ready"
    assert payload["artifact_manifest"] is None
    assert payload["verification_report"] is None
    assert payload["suspicious_weapon_summary"] is None
    assert "Status: PASS" in payload["update_report"]
    assert "Imported Profile Review" in payload["profile_review"]
    assert payload["edition_readiness"] == "# Edition Readiness Report\n"
    assert payload["unit_footprint_review"] == "# Unit Footprint Review\n"
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
    payload = data_review.data_review_payload(None)

    assert payload == {
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


def test_review_file_content_type():
    assert data_review.review_file_content_type("weapon_profile_review.csv").startswith("text/csv")
    assert data_review.review_file_content_type("profile_review.md").startswith("text/markdown")


def test_source_info_from_metadata_summarizes_commit_and_generation():
    payload = data_review.source_info_from_metadata(
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


def test_discover_edition_data_dirs_lists_available_latest_folders(tmp_path):
    latest = tmp_path / "10e" / "latest"
    latest.mkdir(parents=True)
    (latest / "metadata.json").write_text(
        """
{
  "generated_at": "2026-04-25T12:00:00Z",
  "rules_edition": "10e",
  "counts": {"units": 12},
  "source_revisions": [{"commit": "abcdef123456"}]
}
""".strip(),
        encoding="utf-8",
    )

    rows = web_state.discover_edition_data_dirs(tmp_path, active_data_dir=latest)

    assert rows == [
        {
            "edition": "10e",
            "label": "10th Edition",
            "path": str(latest),
            "active": True,
            "loaded": False,
            "units": 12,
            "commit": "abcdef123456",
            "commit_short": "abcdef123456",
            "generated_at": "2026-04-25T12:00:00Z",
            "rules_available": True,
            "status": "available",
            "unavailable_reason": "",
        }
    ]


def test_discover_edition_data_dirs_reports_blocked_unimplemented_ruleset(tmp_path):
    latest = tmp_path / "11e" / "latest"
    latest.mkdir(parents=True)
    (latest / "metadata.json").write_text(
        """
{
  "generated_at": "2026-04-25T12:00:00Z",
  "rules_edition": "11e",
  "counts": {"units": 3}
}
""".strip(),
        encoding="utf-8",
    )

    rows = web_state.discover_edition_data_dirs(tmp_path)

    assert rows[0]["edition"] == "11e"
    assert rows[0]["label"] == "11th Edition"
    assert rows[0]["rules_available"] is False
    assert rows[0]["status"] == "blocked"
    assert rows[0]["unavailable_reason"] == "Ruleset not implemented"


def test_available_edition_rows_preserve_blocked_discovered_editions(tmp_path):
    unit = _unit("Loaded")
    dataset = web_state.EditionDataset(
        edition="10e",
        data_dir=tmp_path / "10e" / "latest",
        source="test",
        units={"u1": unit},
        metadata={"rules_edition": "10e", "counts": {"units": 1}},
    )
    blocked = {
        "edition": "11e",
        "label": "11th Edition",
        "path": str(tmp_path / "11e" / "latest"),
        "active": False,
        "loaded": False,
        "units": 3,
        "commit": "",
        "commit_short": "",
        "generated_at": "",
        "rules_available": False,
        "status": "blocked",
        "unavailable_reason": "Ruleset not implemented",
    }

    rows = web_state.available_edition_rows({"10e": dataset}, active_edition="10e", discovered_rows=[blocked])

    assert [row["edition"] for row in rows] == ["10e", "11e"]
    loaded = next(row for row in rows if row["edition"] == "10e")
    assert loaded["loaded"] is True
    assert loaded["status"] == "loaded"
    assert next(row for row in rows if row["edition"] == "11e")["status"] == "blocked"


def test_requested_rules_edition_validates_dataset_support():
    class State:
        rules_edition = "10e"

        def dataset_for_edition(self, edition=None):
            if edition not in {None, "10e"}:
                raise ValueError("not loaded")

            class Dataset:
                supported_rules_editions = ["10e"]

            return Dataset()

    assert web_state.requested_rules_edition(None, state=State()) == "10e"
    assert web_state.requested_rules_edition("10e", state=State()) == "10e"
    with pytest.raises(ValueError, match="not loaded"):
        web_state.requested_rules_edition("11e", state=State())
