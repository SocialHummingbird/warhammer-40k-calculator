import pytest

from warhammer import cli_core
from warhammer.profiles import UnitProfile


def _unit(name, *, weapons=None, invulnerable_save=None, points=100, models_min=5, models_max=10):
    return UnitProfile.from_dict(
        {
            "name": name,
            "toughness": 4,
            "save": "3+",
            "invulnerable_save": invulnerable_save,
            "wounds": 2,
            "points": points,
            "models_min": models_min,
            "models_max": models_max,
            "weapons": weapons or [],
        }
    )


def test_require_unit_supports_exact_and_unique_partial_match():
    units = {
        "alpha squad": _unit("Alpha Squad"),
        "beta squad": _unit("Beta Squad"),
    }

    assert cli_core._require_unit(units, "Alpha Squad").name == "Alpha Squad"
    assert cli_core._require_unit(units, "beta").name == "Beta Squad"


def test_require_unit_rejects_ambiguous_partial_match():
    units = {
        "alpha squad": _unit("Alpha Squad"),
        "alpha veterans": _unit("Alpha Veterans"),
    }

    with pytest.raises(SystemExit, match="Ambiguous unit name"):
        cli_core._require_unit(units, "alpha")


def test_defense_label_does_not_double_append_invulnerable_plus():
    unit = _unit("Shield Unit", invulnerable_save="4+")

    label = cli_core._format_unit_defense_label(unit, "average")

    assert "4++" not in label
    assert "4+" in label


def test_weapon_table_uses_overkill_safe_model_count_for_points_removed():
    attacker = _unit(
        "Shooter",
        weapons=[
            {
                "name": "Big Gun",
                "type": "ranged",
                "attacks": "1",
                "skill": "Auto",
                "strength": 12,
                "ap": -6,
                "damage": "D6",
            }
        ],
    )
    defender = _unit("Target", points=10, models_min=10, models_max=10, weapons=[])

    table = cli_core._build_weapon_table(attacker, [defender], "ranged", "average")

    assert table is not None
    damage, models, points = table["rows"][0][2].split(" / ")
    assert float(damage) > 1.0
    assert float(models) < float(damage)
    assert points.endswith("pts")
