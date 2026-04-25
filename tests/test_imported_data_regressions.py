import csv
from pathlib import Path

import pytest


CSV_DIR = Path("data") / "latest"


def _load_csv(filename):
    path = CSV_DIR / filename
    if not path.exists():
        pytest.skip(f"{path} not generated")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _units_by_name():
    return {row["name"]: row for row in _load_csv("units.csv")}


def _weapons_for_unit(unit_id):
    return [row for row in _load_csv("weapons.csv") if row["unit_id"] == unit_id]


def _abilities_for_unit(unit_id):
    return [row for row in _load_csv("abilities.csv") if row["source_type"] == "unit" and row["source_id"] == unit_id]


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Boyz", {"models_min": "10", "models_max": "20", "points": "80", "toughness": "5", "wounds": "1", "save": "5+"}),
        (
            "Lokhust Heavy Destroyers",
            {"models_min": "1", "models_max": "3", "points": "55", "toughness": "6", "wounds": "4", "save": "3+"},
        ),
        (
            "Acastus Knight Porphyrion",
            {"selection_type": "model", "models_min": "1", "models_max": "1", "points": "700", "toughness": "13", "wounds": "30"},
        ),
        (
            "Astartes Servitors [Legends]",
            {"models_min": "4", "models_max": "4", "points": "55", "toughness": "4", "wounds": "1"},
        ),
        (
            "Tyrannic War Veterans [Legends]",
            {"models_min": "6", "models_max": "6", "points": "85", "toughness": "4", "wounds": "2"},
        ),
    ],
)
def test_known_tricky_units_keep_expected_imported_values(name, expected):
    unit = _units_by_name()[name]

    for field, value in expected.items():
        assert unit[field] == value


def test_crusade_variant_wolf_guard_headtakers_is_not_exported_as_duplicate_unit():
    rows = [row for row in _load_csv("units.csv") if row["name"] == "Wolf Guard Headtakers"]

    assert len(rows) == 1
    assert rows[0]["unit_id"] == "d4ef-1ddc-1ed5-5156"
    assert rows[0]["models_min"] == "1"
    assert rows[0]["models_max"] == "3"


def test_boyz_do_not_inherit_crusade_relic_abilities():
    boyz = _units_by_name()["Boyz"]
    ability_names = {row["name"] for row in _abilities_for_unit(boyz["unit_id"])}

    assert ability_names == {"Get Da Good Bitz", "Bodyguard"}
    assert "Tartarine Cuirass" not in ability_names


def test_lokhust_heavy_destroyers_keep_model_level_points_and_weapons():
    unit = _units_by_name()["Lokhust Heavy Destroyers"]
    weapons = {row["name"]: row for row in _weapons_for_unit(unit["unit_id"])}

    assert unit["points"] == "55"
    assert weapons["Gauss destructor"]["damage"] == "6"
    assert weapons["Gauss destructor"]["keywords"] == "Heavy, Lethal Hits"
    assert weapons["Enmitic exterminator"]["attacks"] == "6"
    assert weapons["Enmitic exterminator"]["keywords"] == "Heavy, Rapid Fire 6, Sustained Hits 1"


def test_acastus_knight_porphyrion_keeps_variable_damage_profiles():
    unit = _units_by_name()["Acastus Knight Porphyrion"]
    weapons = {row["name"]: row for row in _weapons_for_unit(unit["unit_id"])}

    assert weapons["Twin magna lascannon"]["attacks"] == "D6"
    assert weapons["Twin magna lascannon"]["strength"] == "18"
    assert weapons["Twin magna lascannon"]["damage"] == "D6+6"
    assert weapons["Acastus ironstorm missile pod"]["attacks"] == "D6+6"
    assert weapons["Helios defence missiles"]["damage"] == "D6"
