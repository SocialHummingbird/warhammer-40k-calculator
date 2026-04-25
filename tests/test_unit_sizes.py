from pathlib import Path
import pytest

from warhammer.importers.bsdata import import_catalogues
from warhammer.importers.csv_loader import load_units_from_directory


CAT_ORKS = Path("wh40k-10e") / "Orks.cat"
CAT_SPACE_MARINES = Path("wh40k-10e") / "Imperium - Space Marines.cat"
CSV_DIR = Path("data") / "latest"


def _find_unit_in_catalogue(cat_path: Path, name: str):
    """Load just one catalogue file and return a UnitRow by exact name."""
    units, weapons, abilities, keywords, unit_keywords = import_catalogues([cat_path])
    for row in units:
        if row.name == name:
            return row
    return None


def _find_unit_in_csv(csv_dir: Path, name: str):
    """Load importer CSVs and return a UnitProfile by case-insensitive name."""
    profiles_by_id = load_units_from_directory(csv_dir)
    name_key = name.casefold()
    for profile in profiles_by_id.values():
        if profile.name.casefold() == name_key:
            return profile
    return None


def _get_unit(name: str):
    """Try CSV first (fastest and most stable), fall back to local catalogue files, else skip."""
    if (CSV_DIR / "units.csv").exists():
        unit = _find_unit_in_csv(CSV_DIR, name)
        if unit is not None:
            return unit
    # Fallback to catalogues if they exist
    if name == "Boyz" and CAT_ORKS.exists():
        unit = _find_unit_in_catalogue(CAT_ORKS, name)
        if unit is not None:
            return unit
    if name == "Intercessor Squad" and CAT_SPACE_MARINES.exists():
        unit = _find_unit_in_catalogue(CAT_SPACE_MARINES, name)
        if unit is not None:
            return unit
    pytest.skip(f"Required data not available for unit: {name}")


@pytest.mark.parametrize(
    "unit_name, min_expected",
    [
        ("Boyz", 10),
        ("Intercessor Squad", 5),
    ],
)
def test_unit_size_minimums(unit_name: str, min_expected: int):
    unit = _get_unit(unit_name)
    # Unit may be a UnitProfile (CSV) or UnitRow (catalogue import)
    models_min = getattr(unit, "models_min", None)
    assert models_min is not None, f"models_min not extracted for {unit_name}"
    assert int(models_min) >= min_expected, f"Expected {unit_name} min models >= {min_expected}, got {models_min}"
    models_max = getattr(unit, "models_max", None)
    if models_max is not None:
        assert int(models_max) >= int(models_min)
