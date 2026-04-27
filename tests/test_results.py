import pytest

from warhammer.profiles import UnitProfile
from warhammer.results import UnitResult, WeaponResult, scale_unit_result, scale_weapon_result


def _unit():
    return UnitProfile.from_dict(
        {
            "name": "Target",
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "weapons": [
                {
                    "name": "Test Weapon",
                    "type": "ranged",
                    "attacks": "1",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                }
            ],
        }
    )


def _weapon_result(*, models_destroyed=None):
    unit = _unit()
    return WeaponResult(
        weapon=unit.weapons[0],
        attacks=2.0,
        hits=1.0,
        critical_hits=0.2,
        extra_hits=0.1,
        auto_wounds=0.2,
        devastating_wounds=0.3,
        wounds=0.8,
        unsaved_wounds_before_fnp=0.7,
        unsaved_wounds=0.5,
        expected_damage=1.5,
        hit_probability=0.5,
        wound_probability=0.5,
        critical_wound_probability=1 / 6,
        failed_save_probability=1 / 3,
        wound_roll_label="4+",
        save_used_label="3+",
        fnp_success_probability=0.0,
        target_fnp_label=None,
        ability_notes=[],
        damage_cap_applied=None,
        target_wounds=2,
        models_destroyed=models_destroyed,
    )


def test_weapon_result_models_destroyed_prefers_explicit_model_math():
    explicit = _weapon_result(models_destroyed=0.25)
    fallback = _weapon_result(models_destroyed=None)

    assert explicit.expected_models_destroyed == pytest.approx(0.25)
    assert fallback.expected_models_destroyed == pytest.approx(0.75)


def test_scale_weapon_result_scales_counts_but_not_probabilities():
    result = _weapon_result(models_destroyed=0.25)

    scaled = scale_weapon_result(result, 3)

    assert scaled.attacks == pytest.approx(6.0)
    assert scaled.expected_damage == pytest.approx(4.5)
    assert scaled.models_destroyed == pytest.approx(0.75)
    assert scaled.hit_probability == pytest.approx(result.hit_probability)
    assert scaled.wound_probability == pytest.approx(result.wound_probability)


def test_unit_result_totals_and_scaling():
    unit = _unit()
    first = _weapon_result(models_destroyed=0.25)
    second = _weapon_result(models_destroyed=0.5)
    result = UnitResult(unit=unit, weapons=[first, second], target_wounds=2)

    scaled = scale_unit_result(result, 2)

    assert result.total_damage == pytest.approx(3.0)
    assert result.total_unsaved_wounds == pytest.approx(1.0)
    assert result.total_unsaved_wounds_before_fnp == pytest.approx(1.4)
    assert result.expected_models_destroyed == pytest.approx(0.75)
    assert scaled.total_damage == pytest.approx(6.0)
    assert scaled.expected_models_destroyed == pytest.approx(1.5)
