import pytest

from warhammer import webapp
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
    context = webapp._context_from_payload(
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
    context = webapp._context_from_payload(
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
        webapp._context_from_payload({"target_model_count": "0"})


def test_context_from_payload_rejects_invalid_booleans():
    with pytest.raises(ValueError, match="attacker_moved"):
        webapp._context_from_payload({"attacker_moved": "sometimes"})


def test_optional_weapon_name_normalises_blank_and_all_values():
    assert webapp._optional_weapon_name("") is None
    assert webapp._optional_weapon_name("__all__") is None
    assert webapp._optional_weapon_name("  Bolt rifle ") == "Bolt rifle"
    with pytest.raises(ValueError, match="weapon filters"):
        webapp._optional_weapon_name(12)


def test_optional_unit_id_normalises_blank_values():
    assert webapp._optional_unit_id("") is None
    assert webapp._optional_unit_id("  abc ") == "abc"
    with pytest.raises(ValueError, match="unit ids"):
        webapp._optional_unit_id(12)


def test_contexts_from_payload_keeps_return_strike_independent():
    outgoing, incoming = webapp._contexts_from_payload(
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
    outgoing, incoming = webapp._contexts_from_payload(
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

    result = webapp._evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=webapp.EngagementContext(),
        weapon_name="Heavy gun",
        multiplier=1,
    )

    assert [weapon_result.weapon.name for weapon_result in result.weapons] == ["Heavy gun"]


def test_evaluate_unit_with_weapon_filter_rejects_missing_weapon():
    attacker = _unit("Shooter")
    defender = _unit("Target")

    with pytest.raises(ValueError, match="no ranged weapon"):
        webapp._evaluate_unit_with_weapon_filter(
            attacker,
            defender,
            "ranged",
            context=webapp.EngagementContext(),
            weapon_name="Missing",
            multiplier=1,
        )


def test_evaluate_unit_with_weapon_filter_applies_multiplier():
    attacker = _unit("Shooter")
    defender = _unit("Target")

    base = webapp._evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=webapp.EngagementContext(),
        weapon_name=None,
        multiplier=1,
    )
    scaled = webapp._evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=webapp.EngagementContext(),
        weapon_name=None,
        multiplier=4,
    )

    assert scaled.total_damage == pytest.approx(base.total_damage * 4)
    assert scaled.weapons[0].attacks == pytest.approx(base.weapons[0].attacks * 4)


def test_unit_and_weapon_serializers_are_json_ready():
    unit = _unit("Serializer")

    payload = webapp._unit_detail(unit)

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

    result = webapp._evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=webapp.EngagementContext(),
        weapon_name=None,
        multiplier=1,
    )
    payload = webapp._unit_result(result, target=defender)

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

    judgement = webapp._matchup_judgement(
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

    judgement = webapp._matchup_judgement(
        attacker,
        defender,
        outgoing={"total_damage": 1.0, "estimated_points_removed": None},
        incoming={"total_damage": 3.0, "estimated_points_removed": None},
    )

    assert judgement["basis"] == "damage"
    assert judgement["winner"] == "Defender"


def test_app_state_requires_exact_unit_name(tmp_path, monkeypatch):
    units = {"alpha": _unit("Alpha")}

    monkeypatch.setattr(webapp, "load_units_from_json", lambda path: units)

    state = webapp.AppState(csv_dir=None, json_path=tmp_path / "units.json")

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

    state = webapp.AppState(csv_dir=tmp_path, json_path=None)

    assert len(state.units) == 2
    assert state.require_unit("Shared Name", unit_id="u2").faction == "Faction B"
    assert webapp._unit_summary(state.require_unit("Shared Name", unit_id="u1"))["id"] == "u1"


def test_unit_search_filters_by_faction_keywords_and_limit():
    units = [
        _unit("Ork Boy", faction="Xenos - Orks", keywords=["Infantry"]),
        _unit("Intercessor", faction="Imperium - Space Marines", keywords=["Infantry"]),
        _unit("Rhino", faction="Imperium - Space Marines", keywords=["Vehicle"]),
    ]

    assert [unit.name for unit in webapp._search_units(units, text="vehicle")] == ["Rhino"]
    assert [unit.name for unit in webapp._search_units(units, faction="Imperium - Space Marines", limit=1)] == ["Intercessor"]
    assert webapp._unit_factions(units) == ["Imperium - Space Marines", "Xenos - Orks"]


def test_data_review_payload_loads_generated_reports(tmp_path):
    (tmp_path / "audit_report.json").write_text('{"summary": {"error": 1}}', encoding="utf-8")
    (tmp_path / "import_diff.json").write_text('{"tables": {"units": {"delta": 2}}}', encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"counts": {"units": 3}}', encoding="utf-8")
    (tmp_path / "update_report.md").write_text("# Update\n\nStatus: PASS\n", encoding="utf-8")
    (tmp_path / "profile_review.md").write_text("# Imported Profile Review\n\nWeapon profiles: 1\n", encoding="utf-8")
    (tmp_path / "weapon_profile_review.csv").write_text("unit_name,weapon_name\nBoyz,Choppa\n", encoding="utf-8")

    payload = webapp._data_review_payload(tmp_path)

    assert payload["audit_report"]["summary"]["error"] == 1
    assert payload["import_diff"]["tables"]["units"]["delta"] == 2
    assert payload["metadata"]["counts"]["units"] == 3
    assert "Status: PASS" in payload["update_report"]
    assert "Imported Profile Review" in payload["profile_review"]
    assert payload["review_files"][0]["href"].startswith("/api/review-files/")
    assert {file["filename"] for file in payload["review_files"]} == {
        "weapon_profile_review.csv",
        "profile_review.md",
        "update_report.md",
    }


def test_data_review_payload_tolerates_missing_data_dir():
    payload = webapp._data_review_payload(None)

    assert payload == {
        "audit_report": None,
        "import_diff": None,
        "metadata": None,
        "update_report": None,
        "profile_review": None,
        "review_files": [],
    }


def test_review_file_content_type():
    assert webapp._review_file_content_type("weapon_profile_review.csv").startswith("text/csv")
    assert webapp._review_file_content_type("profile_review.md").startswith("text/markdown")


def test_source_info_from_metadata_summarizes_commit_and_generation():
    payload = webapp._source_info_from_metadata(
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
