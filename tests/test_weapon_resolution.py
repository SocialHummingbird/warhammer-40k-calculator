import pytest

from warhammer.context import EngagementContext
from warhammer.profiles import UnitProfile
from warhammer.rules import get_ruleset
from warhammer.weapon_resolution import resolve_weapon, wound_roll_label_for_weapon


def _unit(name, *, weapon=None, toughness=4, save="3+", wounds=2):
    payload = {
        "name": name,
        "toughness": toughness,
        "save": save,
        "wounds": wounds,
        "weapons": [],
    }
    if weapon:
        payload["weapons"].append(weapon)
    return UnitProfile.from_dict(payload)


def test_resolve_weapon_handles_normal_attack_pipeline():
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Rifle",
            "type": "ranged",
            "attacks": "2",
            "skill": "3+",
            "strength": 4,
            "ap": -1,
            "damage": "2",
        },
    )
    defender = _unit("Target", toughness=4, save="3+", wounds=2)
    weapon = attacker.weapons[0]

    result = resolve_weapon(
        attacker=attacker,
        defender=defender,
        weapon=weapon,
        context=EngagementContext(),
        ruleset=get_ruleset("10e"),
    )

    assert result.attacks == pytest.approx(2.0)
    assert result.hit_probability == pytest.approx(2 / 3)
    assert result.wound_probability == pytest.approx(0.5)
    assert result.failed_save_probability == pytest.approx(0.5)
    assert result.expected_damage == pytest.approx((2 * (2 / 3) * 0.5 * 0.5) * 2)
    assert result.expected_models_destroyed == pytest.approx(result.unsaved_wounds)


def test_resolve_weapon_blocks_non_assault_advanced_ranged_attack():
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Rifle",
            "type": "ranged",
            "attacks": "2",
            "skill": "3+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
        },
    )
    defender = _unit("Target")
    weapon = attacker.weapons[0]

    result = resolve_weapon(
        attacker=attacker,
        defender=defender,
        weapon=weapon,
        context=EngagementContext(attacker_advanced=True),
        ruleset=get_ruleset("10e"),
    )

    assert result.expected_damage == pytest.approx(0.0)
    assert any("Cannot fire after advancing" in note for note in result.ability_notes)
    assert result.wound_roll_label == "4+"


def test_wound_roll_label_for_weapon_uses_ruleset_strength_table():
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Heavy rifle",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 8,
            "ap": 0,
            "damage": "1",
        },
    )

    assert wound_roll_label_for_weapon(attacker.weapons[0], 4, ruleset=get_ruleset("10e")) == "2+"
