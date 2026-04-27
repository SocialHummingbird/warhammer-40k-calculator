import pytest

from warhammer.context import EngagementContext
from warhammer.matchup_payloads import (
    context_detail,
    matchup_judgement,
    points_per_model,
    points_removed,
    unit_detail,
    unit_summary,
)
from warhammer.profiles import UnitProfile


def _unit(name, *, points=100, models_min=2, models_max=4):
    return UnitProfile.from_dict(
        {
            "unit_id": name.lower(),
            "name": name,
            "faction": "Test Faction",
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": points,
            "models_min": models_min,
            "models_max": models_max,
            "keywords": ["INFANTRY"],
            "weapons": [
                {
                    "name": "Test Weapon",
                    "type": "ranged",
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                    "source_file": "Test.cat",
                }
            ],
            "abilities": [{"name": "Test Ability", "text": "Ability text", "source_file": "Test.cat"}],
            "source_file": "Test.cat",
        }
    )


def test_context_and_unit_payloads_are_json_ready():
    unit = _unit("Attacker")
    context = EngagementContext(attacker_advanced=True, target_model_count=0)

    context_payload = context_detail(context)
    summary = unit_summary(unit)
    detail = unit_detail(unit)

    assert context_payload["attacker_moved"] is True
    assert context_payload["target_model_count"] is None
    assert summary["id"] == "attacker"
    assert summary["keywords"] == ["INFANTRY"]
    assert detail["weapons"][0]["source_file"] == "Test.cat"
    assert detail["abilities"][0]["name"] == "Test Ability"


def test_points_helpers_use_average_model_count():
    unit = _unit("Target", points=90, models_min=2, models_max=4)

    assert points_per_model(unit) == pytest.approx(30.0)
    assert points_removed(unit, 1.5) == pytest.approx(45.0)
    assert points_removed(unit, None) is None


def test_matchup_judgement_prefers_points_removed_when_available():
    attacker = _unit("Attacker", points=80)
    defender = _unit("Defender", points=120)

    judgement = matchup_judgement(
        attacker,
        defender,
        outgoing={"total_damage": 1.0, "estimated_points_removed": 75.0},
        incoming={"total_damage": 10.0, "estimated_points_removed": 15.0},
    )

    assert judgement["basis"] == "points_removed"
    assert judgement["winner"] == "Attacker"
    assert "estimated points removed" in judgement["body"]


def test_matchup_judgement_falls_back_to_damage_without_points():
    attacker = _unit("Attacker", points=None)
    defender = _unit("Defender", points=None)

    judgement = matchup_judgement(
        attacker,
        defender,
        outgoing={"total_damage": 1.0, "estimated_points_removed": None},
        incoming={"total_damage": 3.0, "estimated_points_removed": None},
    )

    assert judgement["basis"] == "damage"
    assert judgement["winner"] == "Defender"
