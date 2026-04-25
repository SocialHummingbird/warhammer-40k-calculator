import pytest

from warhammer.calculator import evaluate_unit, evaluate_weapon
from warhammer.profiles import UnitProfile
from warhammer.rules import available_rulesets, get_ruleset


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


def test_rules_registry_exposes_tenth_edition():
    ruleset = get_ruleset("10e")

    assert ruleset.edition == "10e"
    assert "10e" in available_rulesets()
    assert ruleset.required_wound_roll(8, 4) == 2
    assert ruleset.cap_roll_modifier(2) == 1


def test_explicit_tenth_edition_matches_default_calculator_result():
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Heavy rifle",
            "type": "ranged",
            "attacks": "2",
            "skill": "3+",
            "strength": 5,
            "ap": -1,
            "damage": "2",
            "keywords": ["Heavy", "Sustained Hits 1"],
        },
    )
    defender = _unit("Target", toughness=4, save="3+", wounds=2)

    default_result = evaluate_unit(attacker, defender, "ranged")
    explicit_result = evaluate_unit(attacker, defender, "ranged", edition="10e")
    default_weapon = default_result.weapons[0]
    explicit_weapon = explicit_result.weapons[0]

    assert explicit_result.total_damage == pytest.approx(default_result.total_damage)
    assert explicit_result.expected_models_destroyed == pytest.approx(default_result.expected_models_destroyed)
    assert explicit_weapon.hit_probability == pytest.approx(default_weapon.hit_probability)
    assert explicit_weapon.wound_probability == pytest.approx(default_weapon.wound_probability)
    assert explicit_weapon.failed_save_probability == pytest.approx(default_weapon.failed_save_probability)


def test_evaluate_weapon_rejects_unknown_edition():
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Rifle",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
        },
    )
    defender = _unit("Target")

    with pytest.raises(ValueError, match="Unsupported rules edition"):
        evaluate_weapon(attacker, defender, attacker.weapons[0], edition="11e")
