import pytest

from warhammer import webapp
from warhammer.profiles import UnitProfile


def _unit(name, weapon_type="ranged", faction="", keywords=None):
    return UnitProfile.from_dict(
        {
            "name": name,
            "faction": faction,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "weapons": [
                {
                    "name": "Test Weapon",
                    "type": weapon_type,
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
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


def test_unit_and_weapon_serializers_are_json_ready():
    unit = _unit("Serializer")

    payload = webapp._unit_detail(unit)

    assert payload["name"] == "Serializer"
    assert payload["weapons"][0]["name"] == "Test Weapon"
    assert payload["keywords"] == ["Infantry"]


def test_app_state_requires_exact_unit_name(tmp_path, monkeypatch):
    units = {"alpha": _unit("Alpha")}

    monkeypatch.setattr(webapp, "load_units_from_json", lambda path: units)

    state = webapp.AppState(csv_dir=None, json_path=tmp_path / "units.json")

    assert state.require_unit("Alpha").name == "Alpha"
    with pytest.raises(KeyError):
        state.require_unit("Missing")


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

    payload = webapp._data_review_payload(tmp_path)

    assert payload["audit_report"]["summary"]["error"] == 1
    assert payload["import_diff"]["tables"]["units"]["delta"] == 2
    assert payload["metadata"]["counts"]["units"] == 3


def test_data_review_payload_tolerates_missing_data_dir():
    payload = webapp._data_review_payload(None)

    assert payload == {"audit_report": None, "import_diff": None, "metadata": None}
