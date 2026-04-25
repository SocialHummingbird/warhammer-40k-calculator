from warhammer.datasheet import format_unit_datasheet
from warhammer.profiles import UnitProfile


def _weapon(name: str, weapon_type: str = "ranged") -> dict:
    return {
        "name": name,
        "type": weapon_type,
        "attacks": "3",
        "skill": "3+",
        "strength": 4,
        "ap": 1,
        "damage": "1",
    }


def _unit_with_ability() -> UnitProfile:
    data = {
        "name": "Test Squad",
        "toughness": 4,
        "save": "3+",
        "wounds": 2,
        "weapons": [
            _weapon("Boltgun"),
            _weapon("Chainsword", weapon_type="melee"),
        ],
        "abilities": [
            {
                "name": "Favoured Enemy",
                "text": "Add 1 to Hit rolls for attacks made by this unit against INFANTRY units.",
            }
        ],
        "keywords": ["INFANTRY", "CORE"],
    }
    return UnitProfile.from_dict(data)


def test_format_unit_datasheet_includes_modifiers():
    unit = _unit_with_ability()
    sheet = format_unit_datasheet(unit)
    assert "Unit: Test Squad" in sheet
    assert "Weapons:" in sheet
    assert "Boltgun (Ranged)" in sheet
    assert "Derived Modifiers:" in sheet
    assert "INFANTRY" in sheet
    assert "Favoured Enemy" in sheet


def test_format_unit_datasheet_wraps_ability_text():
    unit = UnitProfile.from_dict(
        {
            "name": "Example Leader",
            "toughness": 3,
            "save": "4+",
            "wounds": 3,
            "weapons": [_weapon("Pistol")],
            "abilities": [
                {
                    "name": "Long Rule",
                    "text": "This unit may perform a Normal move after shooting as long as it did not advance this turn and continues to target INFANTRY units when it shoots.",
                }
            ],
            "keywords": ["INFANTRY"],
        }
    )
    sheet = format_unit_datasheet(unit)
    assert "Long Rule" in sheet
    assert "      This unit may perform a Normal move after shooting" in sheet


def test_datasheet_default_hides_extra_abilities():
    abilities = [
        {"name": f"Ability {idx}", "text": "Brief rule."}
        for idx in range(12)
    ]
    unit = UnitProfile.from_dict(
        {
            "name": "Ability Test",
            "toughness": 4,
            "save": "3+",
            "wounds": 3,
            "weapons": [_weapon("Test Weapon")],
            "abilities": abilities,
            "keywords": ["INFANTRY"],
        }
    )
    trimmed = format_unit_datasheet(unit, core_ability_limit=5)
    assert "Ability 0" in trimmed
    assert "Ability 10" not in trimmed
    assert "hidden" in trimmed

    full = format_unit_datasheet(unit, include_crusade=True, core_ability_limit=5)
    assert "Ability 10" in full
