import pytest

from warhammer.calculator import evaluate_unit, evaluate_weapon
from warhammer.profiles import UnitProfile
from warhammer.rules import available_rulesets, capability_key_drift, get_ruleset, ruleset_capabilities, ruleset_registry_payload


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


def test_ruleset_capability_payload_is_shared_and_machine_readable():
    capabilities = ruleset_capabilities("10e")
    payload = ruleset_registry_payload()

    keys = {capability["key"] for capability in capabilities}
    assert {"hit_rolls", "wound_rolls", "save_resolution", "model_removal"} <= keys
    assert payload["10e"]["capability_count"] == len(capabilities)
    assert payload["10e"]["capabilities"] == capabilities


def test_capability_key_drift_reports_missing_and_extra_keys():
    drift = capability_key_drift("10e", [{"key": "hit_rolls"}, {"key": "future_rule"}])

    assert drift is not None
    assert drift["ok"] is False
    assert "wound_rolls" in drift["missing_keys"]
    assert drift["extra_keys"] == ["future_rule"]
    assert capability_key_drift("11e", []) is None


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


def test_tenth_ruleset_owns_contextual_attack_adjustments():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Frag rifle",
            "type": "ranged",
            "attacks": "2",
            "skill": "3+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
            "keywords": ["Rapid Fire 1", "Blast"],
        },
    )
    defender = _unit("Target", wounds=1)

    adjustment = ruleset.adjusted_attack_count(
        attacker.weapons[0],
        base_attacks=attacker.weapons[0].attacks.average,
        target_model_count=10,
        defender=defender,
        target_within_half_range=True,
        weapon_blast=True,
    )

    assert adjustment.attacks == pytest.approx(4.0)
    assert adjustment.target_model_count == 10
    assert any("Rapid Fire active" in note for note in adjustment.notes)
    assert any("Blast: +1" in note for note in adjustment.notes)


def test_tenth_ruleset_owns_advance_and_hit_modifier_adjustments():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Heavy assault rifle",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
            "keywords": ["Heavy", "Assault"],
        },
    )
    weapon = attacker.weapons[0]

    decision = ruleset.advance_attack_decision(
        weapon,
        attacker_advanced=True,
        weapon_assault=False,
        attacker_can_advance_and_shoot=False,
    )
    penalty = ruleset.ranged_hit_modifier(
        weapon,
        attacker_moved=True,
        attacker_advanced=True,
        weapon_assault=True,
        attacker_can_advance_and_shoot=False,
    )

    assert decision.can_attack is False
    assert any("Cannot fire after advancing" in note for note in decision.notes)
    assert penalty.modifier_delta == -1
    assert any("Assault: advanced" in note for note in penalty.notes)


def test_tenth_ruleset_owns_hit_pool_resolution():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Exploding rifle",
            "type": "ranged",
            "attacks": "6",
            "skill": "4+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
            "lethal_hits": True,
            "sustained_hits": 1,
        },
    )
    weapon = attacker.weapons[0]

    hit_roll = ruleset.hit_roll_resolution(
        weapon,
        attacks=6.0,
        hit_modifier=1,
        hit_reroll="none",
        weapon_auto_hits=False,
    )
    torrent_roll = ruleset.hit_roll_resolution(
        weapon,
        attacks=6.0,
        hit_modifier=1,
        hit_reroll="all",
        weapon_auto_hits=True,
    )

    assert hit_roll.hit_probability == pytest.approx(4 / 6)
    assert hit_roll.critical_hit_probability == pytest.approx(1 / 6)
    assert hit_roll.hits == pytest.approx(4.0)
    assert hit_roll.critical_hits == pytest.approx(1.0)
    assert hit_roll.extra_hits == pytest.approx(1.0)
    assert hit_roll.total_hits == pytest.approx(5.0)
    assert hit_roll.auto_wounds == pytest.approx(1.0)
    assert hit_roll.hits_requiring_wound == pytest.approx(4.0)
    assert torrent_roll.hit_probability == pytest.approx(1.0)
    assert torrent_roll.critical_hits == pytest.approx(0.0)
    assert torrent_roll.auto_wounds == pytest.approx(0.0)


def test_tenth_ruleset_owns_save_and_damage_resolution_notes():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Melta rifle",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 9,
            "ap": -4,
            "damage": "D6",
            "keywords": ["Melta 2", "Ignores Cover"],
        },
    )
    defender = _unit("Target", save="3+", wounds=2)
    defender.damage_reduction = 1.0
    weapon = attacker.weapons[0]

    save = ruleset.save_resolution(
        defender,
        weapon,
        target_in_cover=True,
        weapon_ignores_cover=True,
    )
    damage = ruleset.damage_resolution(
        weapon,
        defender,
        target_within_half_range=True,
    )

    assert save.label == "7+"
    assert any("Ignores Cover" in note for note in save.notes)
    assert damage.damage_per_wound == pytest.approx(4.5)
    assert any("Melta active" in note for note in damage.notes)
    assert any("Target Damage Reduction" in note for note in damage.notes)


def test_tenth_ruleset_owns_anti_and_devastating_wound_pools():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Bio-plasma",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 4,
            "ap": 0,
            "damage": "1",
            "keywords": ["Anti-Infantry 4+", "Devastating Wounds"],
        },
    )
    weapon = attacker.weapons[0]

    wound_roll = ruleset.wound_roll_resolution(
        weapon,
        defender_toughness=5,
        wound_modifier=0,
        wound_reroll="none",
        anti_threshold=4,
    )
    wound_pool = ruleset.wound_pool_resolution(
        weapon,
        auto_wounds=1.0,
        hits_requiring_wound=6.0,
        wound_probability=wound_roll.wound_probability,
        critical_wound_probability=wound_roll.critical_wound_probability,
    )

    assert wound_roll.label == "5+"
    assert wound_roll.wound_probability == pytest.approx(0.5)
    assert wound_roll.critical_wound_probability == pytest.approx(0.5)
    assert wound_pool.devastating_wounds == pytest.approx(3.0)
    assert wound_pool.normal_wounds_from_roll == pytest.approx(0.0)
    assert wound_pool.wounds == pytest.approx(4.0)


def test_tenth_ruleset_owns_damage_pipeline_resolution():
    ruleset = get_ruleset("10e")
    attacker = _unit(
        "Shooter",
        weapon={
            "name": "Plasma gun",
            "type": "ranged",
            "attacks": "1",
            "skill": "3+",
            "strength": 8,
            "ap": -2,
            "damage": "3",
        },
    )
    defender = _unit("Target", save="4+", wounds=2)
    defender.feel_no_pain = 5
    weapon = attacker.weapons[0]

    save = ruleset.save_resolution(
        defender,
        weapon,
        target_in_cover=False,
        weapon_ignores_cover=False,
    )
    wound_pool = ruleset.wound_pool_resolution(
        weapon,
        auto_wounds=1.0,
        hits_requiring_wound=3.0,
        wound_probability=0.5,
        critical_wound_probability=0.0,
    )
    damage = ruleset.damage_resolution(
        weapon,
        defender,
        target_within_half_range=False,
    )
    pipeline = ruleset.damage_pipeline_resolution(
        defender,
        save_resolution=save,
        wound_pool=wound_pool,
        auto_wounds=1.0,
        damage_resolution=damage,
    )

    assert save.label == "6+"
    assert pipeline.failed_save_probability == pytest.approx(5 / 6)
    assert pipeline.fnp_success_probability == pytest.approx(2 / 6)
    assert pipeline.unsaved_wounds_before_fnp == pytest.approx((1.0 + 1.5) * 5 / 6)
    assert pipeline.unsaved_wounds == pytest.approx(((1.0 + 1.5) * 5 / 6) * (4 / 6))
    assert pipeline.expected_damage == pytest.approx(pipeline.unsaved_wounds * 3)
    assert pipeline.models_destroyed == pytest.approx(pipeline.unsaved_wounds)


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
