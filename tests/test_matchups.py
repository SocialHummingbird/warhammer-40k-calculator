import pytest

from warhammer.calculator import EngagementContext
from warhammer.matchups import calculate_matchup, evaluate_unit_with_weapon_filter
from warhammer.profiles import UnitProfile


def _unit(name, *, points=100, weapons=None):
    return UnitProfile.from_dict(
        {
            "name": name,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": points,
            "models_min": 1,
            "models_max": 1,
            "weapons": weapons
            or [
                {
                    "name": "Test Weapon",
                    "type": "ranged",
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                }
            ],
        }
    )


def test_calculate_matchup_returns_json_ready_two_way_payload():
    attacker = _unit("Attacker", points=80)
    defender = _unit("Defender", points=120)

    payload = calculate_matchup(
        attacker,
        defender,
        "ranged",
        outgoing_context=EngagementContext(),
        incoming_context=EngagementContext(attacker_moved=True),
        edition="10e",
    )

    assert payload["attacker"]["name"] == "Attacker"
    assert payload["defender"]["name"] == "Defender"
    assert payload["edition"] == "10e"
    assert payload["contexts"]["incoming"]["attacker_moved"] is True
    assert payload["outgoing"]["total_damage"] >= 0
    assert payload["incoming"]["total_damage"] >= 0
    assert payload["judgement"]["basis"] in {"damage", "points_removed"}


def test_evaluate_unit_with_weapon_filter_applies_named_weapon_and_multiplier():
    attacker = _unit(
        "Shooter",
        weapons=[
            {"name": "Light gun", "type": "ranged", "attacks": "1", "skill": "3+", "strength": 4, "ap": 0, "damage": "1"},
            {"name": "Heavy gun", "type": "ranged", "attacks": "2", "skill": "3+", "strength": 8, "ap": -2, "damage": "3"},
        ],
    )
    defender = _unit("Target")

    base = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name="Heavy gun",
    )
    scaled = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        "ranged",
        context=EngagementContext(),
        weapon_name="Heavy gun",
        multiplier=3,
    )

    assert [weapon_result.weapon.name for weapon_result in base.weapons] == ["Heavy gun"]
    assert scaled.total_damage == pytest.approx(base.total_damage * 3)
