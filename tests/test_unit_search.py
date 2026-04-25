from warhammer.profiles import UnitProfile
from warhammer.unit_search import search_units, unit_factions


def _unit(name, *, faction="", keywords=None):
    return UnitProfile.from_dict(
        {
            "name": name,
            "faction": faction,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "weapons": [],
            "keywords": keywords or ["Infantry"],
        }
    )


def test_unit_search_filters_by_faction_keywords_and_limit():
    units = [
        _unit("Ork Boy", faction="Xenos - Orks", keywords=["Infantry"]),
        _unit("Intercessor", faction="Imperium - Space Marines", keywords=["Infantry"]),
        _unit("Rhino", faction="Imperium - Space Marines", keywords=["Vehicle"]),
    ]

    assert [unit.name for unit in search_units(units, text="vehicle")] == ["Rhino"]
    assert [unit.name for unit in search_units(units, faction="Imperium - Space Marines", limit=1)] == ["Intercessor"]
    assert unit_factions(units) == ["Imperium - Space Marines", "Xenos - Orks"]
