from warhammer.ability_resolver import (
    build_ability_notes,
    collect_ability_modifiers,
    merge_reroll,
    normalise_keywords,
    resolve_anti_threshold,
)
from warhammer.profiles import UnitProfile


def _unit(weapon, *, ability=None, keywords=None):
    payload = {
        "name": "Test Unit",
        "toughness": 4,
        "save": "3+",
        "wounds": 2,
        "weapons": [weapon],
        "abilities": [],
        "keywords": keywords or [],
    }
    if ability:
        payload["abilities"].append({"name": ability[0], "text": ability[1]})
    return UnitProfile.from_dict(payload)


def _weapon(**overrides):
    payload = {
        "name": "Test Weapon",
        "type": "ranged",
        "attacks": "1",
        "skill": "3+",
        "strength": 4,
        "ap": 0,
        "damage": "1",
    }
    payload.update(overrides)
    return payload


def test_merge_reroll_keeps_strongest_valid_option():
    assert merge_reroll("none", "ones") == "ones"
    assert merge_reroll("all", "ones") == "all"
    assert merge_reroll("bad", "all") == "all"
    assert merge_reroll("ones", "bad") == "ones"


def test_collect_ability_modifiers_filters_by_weapon_type_and_target_keywords():
    ability = (
        "Targeting Array",
        (
            "Each time this unit makes ranged attacks that target INFANTRY units, "
            "add 1 to the Hit roll and re-roll Hit rolls of 1."
        ),
    )
    attacker = _unit(_weapon(type="ranged"), ability=ability)
    ranged_weapon = attacker.weapons[0]
    melee_attacker = _unit(_weapon(type="melee"), ability=ability)
    melee_weapon = melee_attacker.weapons[0]

    applied = collect_ability_modifiers(attacker, {"infantry"}, ranged_weapon)
    wrong_target = collect_ability_modifiers(attacker, {"vehicle"}, ranged_weapon)
    wrong_type = collect_ability_modifiers(melee_attacker, {"infantry"}, melee_weapon)

    assert applied.hit_modifier == 1
    assert applied.reroll_hits == "ones"
    assert any("Targeting Array" in note for note in applied.notes)
    assert wrong_target.hit_modifier == 0
    assert wrong_type.hit_modifier == 0


def test_resolve_anti_threshold_uses_best_weapon_or_ability_match():
    ability = (
        "Tank Hunters",
        "Each time this unit makes an attack that targets VEHICLE units, that attack has the [ANTI-VEHICLE 3+] ability.",
    )
    attacker = _unit(_weapon(keywords="Anti-VEHICLE 4+"), ability=ability)
    weapon = attacker.weapons[0]
    defender_keywords = normalise_keywords(["VEHICLE"])
    applied = collect_ability_modifiers(attacker, defender_keywords, weapon)

    assert resolve_anti_threshold(weapon, applied, defender_keywords) == 3
    assert resolve_anti_threshold(weapon, applied, normalise_keywords(["INFANTRY"])) is None


def test_build_ability_notes_summarises_weapon_rules():
    attacker = _unit(
        _weapon(
            reroll_hits="ones",
            keywords="Assault, Blast, Devastating Wounds, Lethal Hits, Sustained Hits 2",
        )
    )
    notes = build_ability_notes(attacker.weapons[0])

    assert "Hit rerolls (ones)" in notes
    assert "Assault" in notes
    assert "Blast" in notes
    assert "Devastating Wounds" in notes
    assert "Lethal Hits" in notes
    assert "Sustained Hits 2" in notes
