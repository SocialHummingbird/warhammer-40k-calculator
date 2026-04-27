import pytest

from warhammer.calculator import EngagementContext, evaluate_weapon, scale_weapon_result
from warhammer.profiles import UnitProfile


def _weapon_dict(**overrides):
    data = {
        "name": "Test Weapon",
        "type": "ranged",
        "attacks": "1",
        "skill": "3+",
        "strength": 4,
        "ap": 0,
        "damage": "1",
    }
    data.update(overrides)
    return data


def _unit_dict(weapon_dict, *, ability=None, keywords=None):
    payload = {
        "name": "Test Unit",
        "toughness": 4,
        "save": "3+",
        "wounds": 2,
        "weapons": [weapon_dict],
        "abilities": [],
        "keywords": keywords or [],
    }
    if ability:
        payload["abilities"].append({"name": ability[0], "text": ability[1]})
    return payload


def _build_unit(weapon_dict, ability=None, keywords=None):
    return UnitProfile.from_dict(_unit_dict(weapon_dict, ability=ability, keywords=keywords))


def _simple_target(**overrides):
    data = {
        "name": "Target",
        "toughness": 4,
        "save": "3+",
        "wounds": 2,
        "weapons": [],
    }
    data.update(overrides)
    return UnitProfile.from_dict(data)


def test_ability_hit_modifier_applies_vs_keyword():
    weapon_dict = _weapon_dict()
    ability = (
        "Preferred Target",
        "Each time this unit makes a ranged attack that targets INFANTRY units, add 1 to the Hit roll.",
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target(keywords=["INFANTRY"], toughness=3, save="4+", wounds=1)

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon)

    assert pytest.approx(result.hit_probability, rel=1e-6) == pytest.approx(5 / 6)
    assert any("Preferred Target" in note for note in result.ability_notes)

    non_infantry = _simple_target(keywords=["VEHICLE"], toughness=7, save="3+", wounds=10)
    result_no_bonus = evaluate_weapon(attacker, non_infantry, weapon)
    assert pytest.approx(result_no_bonus.hit_probability, rel=1e-6) == pytest.approx(2 / 3)


def test_scale_weapon_result_scales_counts_but_not_probabilities():
    attacker = _build_unit(_weapon_dict(attacks="2", damage="2"))
    defender = _simple_target(wounds=1)
    result = evaluate_weapon(attacker, defender, attacker.weapons[0])

    scaled = scale_weapon_result(result, 3)

    assert scaled.attacks == pytest.approx(result.attacks * 3)
    assert scaled.expected_damage == pytest.approx(result.expected_damage * 3)
    assert scaled.expected_models_destroyed == pytest.approx(result.expected_models_destroyed * 3)
    assert scaled.hit_probability == result.hit_probability
    assert scaled.wound_probability == result.wound_probability


def test_ability_reroll_ones_melee_only():
    weapon_dict = _weapon_dict(type="melee")
    ability = (
        "Expert Duelists",
        "Each time this unit makes a melee attack, re-roll Hit rolls of 1.",
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target(keywords=["INFANTRY"])

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon)

    expected = (2 / 3) + (1 / 6) * (2 / 3)
    assert pytest.approx(result.hit_probability, rel=1e-6) == pytest.approx(expected)


def test_ability_wound_modifier_global():
    weapon_dict = _weapon_dict()
    ability = (
        "Blessed Blades",
        "Add 1 to wound rolls for attacks made by this unit.",
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target(keywords=["INFANTRY"])

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon)

    assert pytest.approx(result.wound_probability, rel=1e-6) == pytest.approx(2 / 3)


def test_ability_grants_twin_linked_increases_wound_probability():
    weapon_dict = _weapon_dict()
    ability = (
        "Target Lock",
        "Each time this unit makes a ranged attack, that attack has the TWIN-LINKED ability.",
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target()

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon)

    assert pytest.approx(result.wound_probability, rel=1e-6) == pytest.approx(0.75)
    assert any("Twin-linked" in note for note in result.ability_notes)


def test_weapon_keywords_enable_twin_linked_and_anti():
    weapon_dict = _weapon_dict(
        strength=4,
        keywords="Assault, Twin-linked, Anti-INFANTRY 4+, Rapid Fire 1",
    )
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(keywords=["INFANTRY"], toughness=5)

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_within_half_range=True))

    assert pytest.approx(result.wound_probability, rel=1e-6) == pytest.approx(0.75)
    notes = result.ability_notes
    assert any("Twin-linked" in note for note in notes)
    assert any("Anti-INFANTRY 4+" in note for note in notes)
    assert any("Rapid Fire active" in note for note in notes)
    assert any("Assault" in note for note in notes)


def test_weapon_keyword_text_populates_hit_special_rules():
    weapon_dict = _weapon_dict(
        attacks="6",
        skill="4+",
        keywords="Lethal Hits, Sustained Hits 2, Devastating Wounds",
    )
    attacker = _build_unit(weapon_dict)

    weapon = attacker.weapons[0]

    assert weapon.lethal_hits is True
    assert weapon.sustained_hits == 2
    assert weapon.devastating_wounds is True


def test_ability_grants_anti_keyword_increases_wound_probability():
    weapon_dict = _weapon_dict()
    ability = (
        "Tank Hunters",
        "Each time this unit makes an attack that targets VEHICLE units, that attack has the [ANTI-VEHICLE 4+] ability.",
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target(keywords=["VEHICLE"], toughness=8, wounds=10)

    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon)

    assert pytest.approx(result.wound_probability, rel=1e-6) == pytest.approx(0.5)
    assert any("Anti-VEHICLE 4+" in note for note in result.ability_notes)


def test_heavy_bonus_when_stationary():
    weapon_dict = _weapon_dict(skill="3+", keywords=["Heavy"])
    attacker = _build_unit(weapon_dict)
    defender = _simple_target()

    weapon = attacker.weapons[0]
    stationary = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(attacker_moved=False))
    moved = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(attacker_moved=True))

    assert stationary.hit_probability > moved.hit_probability
    assert any("Heavy" in note for note in stationary.ability_notes)


def test_rapid_fire_adds_attacks_within_half_range():
    weapon_dict = _weapon_dict(attacks="2", keywords=["Rapid Fire 1"])
    attacker = _build_unit(weapon_dict)
    defender = _simple_target()

    weapon = attacker.weapons[0]
    near = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_within_half_range=True))
    far = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_within_half_range=False))

    assert near.attacks == pytest.approx(weapon.attacks.average + 1)
    assert far.attacks == pytest.approx(weapon.attacks.average)
    assert any("Rapid Fire active" in note for note in near.ability_notes)


def test_assault_weapon_handles_advance_penalty():
    weapon_dict = _weapon_dict(keywords=["Assault"])
    attacker = _build_unit(weapon_dict)
    defender = _simple_target()

    weapon = attacker.weapons[0]
    baseline = evaluate_weapon(attacker, defender, weapon)
    advanced = evaluate_weapon(
        attacker,
        defender,
        weapon,
        context=EngagementContext(attacker_moved=True, attacker_advanced=True),
    )

    assert advanced.hit_probability < baseline.hit_probability
    assert any("Assault: advanced" in note for note in advanced.ability_notes)


def test_advance_without_assault_prevents_firing():
    weapon_dict = _weapon_dict()
    attacker = _build_unit(weapon_dict)
    defender = _simple_target()

    weapon = attacker.weapons[0]
    advanced = evaluate_weapon(
        attacker,
        defender,
        weapon,
        context=EngagementContext(attacker_moved=True, attacker_advanced=True),
    )

    assert advanced.expected_damage == 0.0
    assert any("Cannot fire after advancing" in note for note in advanced.ability_notes)


def test_cover_bonus_applies_without_ignore_cover():
    weapon_dict = _weapon_dict(ap=0)
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(save="4+")

    weapon = attacker.weapons[0]
    baseline = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_in_cover=False))
    cover = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_in_cover=True))

    assert cover.failed_save_probability < baseline.failed_save_probability
    assert any("Target in Cover" in note for note in cover.ability_notes)


def test_ignore_cover_keyword_bypasses_cover():
    weapon_dict = _weapon_dict(ap=0, keywords=["Ignores Cover"])
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(save="4+")

    weapon = attacker.weapons[0]
    cover = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_in_cover=True))
    baseline = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_in_cover=False))

    assert pytest.approx(cover.failed_save_probability, rel=1e-6) == pytest.approx(baseline.failed_save_probability)
    assert any("Ignores Cover" in note for note in cover.ability_notes)


def test_damage_reduction_from_abilities_applies():
    weapon_dict = _weapon_dict(damage="3")
    attacker = _build_unit(weapon_dict)
    defender_plain = _simple_target(wounds=10)
    defender_reduced = UnitProfile.from_dict(
        {
            "name": "Armoured Target",
            "toughness": 4,
            "save": "3+",
            "wounds": 10,
            "weapons": [],
            "abilities": [
                {
                    "name": "Adamantine Mantle",
                    "text": "Each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack.",
                }
            ],
        }
    )

    weapon = attacker.weapons[0]
    baseline = evaluate_weapon(attacker, defender_plain, weapon)
    reduced = evaluate_weapon(attacker, defender_reduced, weapon)

    assert reduced.expected_damage < baseline.expected_damage
    assert any("Damage Reduction" in note for note in reduced.ability_notes)

def test_ability_grants_torrent_auto_hits_against_keyword():
    weapon_dict = _weapon_dict(attacks='3', skill='4+')
    ability = (
        'Purging Flame',
        'Each time this unit makes a ranged attack that targets INFANTRY units, that attack has the [TORRENT] ability.',
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    vs_infantry = _simple_target(keywords=['INFANTRY'], wounds=3)
    vs_vehicle = _simple_target(keywords=['VEHICLE'], wounds=3)

    weapon = attacker.weapons[0]
    torrent_result = evaluate_weapon(attacker, vs_infantry, weapon)
    normal_result = evaluate_weapon(attacker, vs_vehicle, weapon)

    assert pytest.approx(torrent_result.hit_probability, rel=1e-6) == pytest.approx(1.0)
    assert pytest.approx(torrent_result.hits, rel=1e-6) == pytest.approx(torrent_result.attacks)
    assert any('Torrent' in note for note in torrent_result.ability_notes)

    assert pytest.approx(normal_result.hit_probability, rel=1e-6) == pytest.approx(0.5)
    assert not any('Torrent' in note for note in normal_result.ability_notes)


def test_conditional_twin_linked_only_applies_vs_monsters():
    weapon_dict = _weapon_dict(strength=5)
    ability = (
        'Monster Lock',
        'Each time this unit makes a ranged attack that targets MONSTER units, that attack has the Twin-linked ability.',
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    monster_target = _simple_target(keywords=['MONSTER'], toughness=5, wounds=8)
    vehicle_target = _simple_target(keywords=['VEHICLE'], toughness=5, wounds=8)

    weapon = attacker.weapons[0]
    monster_result = evaluate_weapon(attacker, monster_target, weapon)
    vehicle_result = evaluate_weapon(attacker, vehicle_target, weapon)

    assert pytest.approx(monster_result.wound_probability, rel=1e-6) == pytest.approx(0.75)
    assert pytest.approx(vehicle_result.wound_probability, rel=1e-6) == pytest.approx(0.5)
    assert any('Twin-linked' in note for note in monster_result.ability_notes)
    assert not any('Twin-linked' in note for note in vehicle_result.ability_notes)


def test_blast_bonus_uses_target_model_context():
    weapon_dict = _weapon_dict(keywords="Blast")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(models_min=5, models_max=5)
    context = EngagementContext(target_model_count=10)
    weapon = attacker.weapons[0]
    result = evaluate_weapon(attacker, defender, weapon, context=context)

    assert pytest.approx(result.attacks, rel=1e-6) == pytest.approx(2.0)
    assert any("Blast: +1" in note for note in result.ability_notes)


def test_melta_damage_bonus_within_half_range():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength=12, damage="3", keywords="Melta 2")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=1, save="7+")
    weapon = attacker.weapons[0]

    far = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_within_half_range=False))
    close = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(target_within_half_range=True))

    assert close.unsaved_wounds > 0
    far_damage = far.expected_damage / far.unsaved_wounds
    close_damage = close.expected_damage / close.unsaved_wounds
    assert pytest.approx(close_damage, rel=1e-6) == pytest.approx(far_damage + 2)
    assert any("Melta active" in note for note in close.ability_notes)


def test_advance_and_shoot_abilities_allow_firing_after_advance():
    weapon_dict = _weapon_dict(keywords="Assault")
    ability = ("Mobile Firepower", "This unit can shoot even if it advanced.")
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target()
    weapon = attacker.weapons[0]

    baseline = evaluate_weapon(attacker, defender, weapon, context=EngagementContext())

    advanced_context = EngagementContext(attacker_moved=True, attacker_advanced=True)
    result = evaluate_weapon(attacker, defender, weapon, context=advanced_context)

    attacker_without_ability = _build_unit(weapon_dict)
    penalty_result = evaluate_weapon(attacker_without_ability, defender, attacker_without_ability.weapons[0], context=advanced_context)

    assert getattr(attacker, "can_advance_and_shoot", False)
    assert pytest.approx(result.hit_probability, rel=1e-6) == pytest.approx(baseline.hit_probability)
    assert not any("Assault: advanced" in note for note in result.ability_notes)
    assert any("Advance & shoot ability" in note for note in result.ability_notes)

    assert penalty_result.hit_probability < baseline.hit_probability
    assert any("Assault: advanced" in note for note in penalty_result.ability_notes)


def test_ability_granting_assault_allows_advance_fire():
    weapon_dict = _weapon_dict()
    ability = (
        "Loping Predator",
        "The bearer's ranged weapons have the [Assault] ability."
    )
    attacker = _build_unit(weapon_dict, ability=ability)
    defender = _simple_target()
    context = EngagementContext(attacker_moved=True, attacker_advanced=True)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon, context=context)

    assert pytest.approx(result.attacks, rel=1e-6) == pytest.approx(1.0)
    assert any("Assault: advanced" in note for note in result.ability_notes)
    assert not any("Cannot fire after advancing" in note for note in result.ability_notes)

    baseline_unit = _build_unit(weapon_dict)
    baseline_result = evaluate_weapon(baseline_unit, defender, baseline_unit.weapons[0], context=context)
    assert baseline_result.attacks == 0.0


def test_roll_modifiers_are_capped_at_plus_or_minus_one():
    weapon_dict = _weapon_dict(skill="4+", hit_modifier=1, keywords=["Heavy"])
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(save="7+")
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon, context=EngagementContext(attacker_moved=False))

    assert pytest.approx(result.hit_probability, rel=1e-6) == pytest.approx(2 / 3)
    assert any("Hit modifier capped at +1" in note for note in result.ability_notes)


def test_models_destroyed_does_not_count_overkill_damage():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength=12, ap=-6, damage="D6")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=1, save="7+", wounds=1)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon)

    assert result.expected_damage > 1.0
    assert result.expected_models_destroyed == pytest.approx(result.unsaved_wounds)


def test_models_destroyed_uses_variable_damage_distribution_for_overkill():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength=12, ap=-6, damage="D6")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=1, save="7+", wounds=2)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon)

    assert result.unsaved_wounds == pytest.approx(5 / 6)
    assert result.expected_damage == pytest.approx((5 / 6) * 3.5)
    assert result.expected_models_destroyed == pytest.approx((5 / 6) * (11 / 12))


def test_damage_cap_uses_variable_damage_distribution():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength=12, ap=-6, damage="D6")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=1, save="7+", wounds=10, damage_cap=3)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon)

    assert result.unsaved_wounds == pytest.approx(5 / 6)
    assert result.expected_damage == pytest.approx((5 / 6) * 2.5)


def test_variable_strength_averages_wound_probability_by_distribution():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength="D6+6", ap=-6, damage="1")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=12, save="7+", wounds=10)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon)

    assert weapon.strength_label == "D6+6"
    assert result.wound_probability == pytest.approx(13 / 36)
    assert result.wound_roll_label == "4+/5+"


def test_strength_with_trailing_plus_is_treated_as_numeric_strength():
    weapon_dict = _weapon_dict(attacks="1", skill="Auto", strength="8+", ap=-6, damage="1")
    attacker = _build_unit(weapon_dict)
    defender = _simple_target(toughness=4, save="7+", wounds=10)
    weapon = attacker.weapons[0]

    result = evaluate_weapon(attacker, defender, weapon)

    assert weapon.strength == 8
    assert weapon.strength_label == "8"
    assert result.wound_probability == pytest.approx(5 / 6)
    assert result.wound_roll_label == "2+"
