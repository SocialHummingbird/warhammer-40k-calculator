import csv

import pytest

from warhammer.ml.features import build_matchup_feature_rows, sample_matchup_feature_rows, write_matchup_feature_csv
from warhammer.profiles import UnitProfile


def _unit(name, *, unit_id, points=100, toughness=4, save="3+", wounds=2, weapons=None):
    return UnitProfile.from_dict(
        {
            "unit_id": unit_id,
            "name": name,
            "faction": "Test Faction",
            "toughness": toughness,
            "save": save,
            "wounds": wounds,
            "points": points,
            "models_min": 1,
            "models_max": 1,
            "weapons": weapons
            or [
                {
                    "name": "Test Gun",
                    "type": "ranged",
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                }
            ],
            "keywords": ["Infantry"],
        }
    )


def test_build_matchup_feature_rows_uses_deterministic_calculator_outputs():
    attacker = _unit(
        "Shooter",
        unit_id="u1",
        points=80,
        weapons=[
            {
                "name": "Big gun",
                "type": "ranged",
                "attacks": "4",
                "skill": "3+",
                "strength": 8,
                "ap": -2,
                "damage": "3",
                "keywords": ["Heavy", "Sustained Hits 1"],
                "sustained_hits": 1,
            }
        ],
    )
    defender = _unit("Target", unit_id="u2", points=120, toughness=4, save="4+", wounds=2)

    rows = build_matchup_feature_rows([attacker, defender], modes=("ranged",), max_rows=1)

    assert len(rows) == 1
    row = rows[0]
    assert row["edition"] == "10e"
    assert row["mode"] == "ranged"
    assert row["label_source"] == "deterministic_calculator"
    assert row["attacker_name"] == "Shooter"
    assert row["defender_name"] == "Target"
    assert row["attacker_mode_weapon_count"] == 1
    assert row["attacker_mode_avg_attacks"] == pytest.approx(4)
    assert row["attacker_mode_avg_skill"] == pytest.approx(3)
    assert row["attacker_mode_avg_strength"] == pytest.approx(8)
    assert row["attacker_mode_best_ap"] == pytest.approx(-2)
    assert row["attacker_mode_avg_damage"] == pytest.approx(3)
    assert row["attacker_mode_keyword_count"] == 2
    assert row["attacker_mode_special_rule_count"] == 2
    assert row["outgoing_damage"] >= 0
    assert row["damage_delta"] == pytest.approx(row["outgoing_damage"] - row["incoming_damage"])
    assert row["winner_label"] in {"attacker", "defender", "close"}


def test_build_matchup_feature_rows_skips_modes_without_attacker_weapons():
    shooter = _unit("Shooter", unit_id="u1")
    target = _unit("Target", unit_id="u2")

    rows = build_matchup_feature_rows([shooter, target], modes=("melee",))

    assert rows == []


def test_write_matchup_feature_csv_writes_header_and_rows(tmp_path):
    attacker = _unit("Shooter", unit_id="u1")
    defender = _unit("Target", unit_id="u2")
    rows = build_matchup_feature_rows([attacker, defender], modes=("ranged",), max_rows=1)
    output = tmp_path / "features.csv"

    count = write_matchup_feature_csv(rows, output)

    assert count == 1
    with output.open(encoding="utf-8", newline="") as handle:
        loaded = list(csv.DictReader(handle))
    assert loaded[0]["attacker_id"] == "u1"
    assert loaded[0]["label_source"] == "deterministic_calculator"


def test_sample_matchup_feature_rows_uses_seeded_unique_pairs_across_modes():
    attacker = _unit(
        "Mixed",
        unit_id="u1",
        weapons=[
            {"name": "Gun", "type": "ranged", "attacks": "2", "skill": "3+", "strength": 4, "ap": 0, "damage": "1"},
            {"name": "Blade", "type": "melee", "attacks": "2", "skill": "3+", "strength": 4, "ap": 0, "damage": "1"},
        ],
    )
    defender = _unit(
        "Target",
        unit_id="u2",
        weapons=[
            {"name": "Claw", "type": "melee", "attacks": "2", "skill": "3+", "strength": 4, "ap": 0, "damage": "1"},
        ],
    )

    rows = sample_matchup_feature_rows([attacker, defender], row_count=4, seed=1)

    keys = {(row["mode"], row["attacker_id"], row["defender_id"]) for row in rows}
    assert len(keys) == len(rows)
    assert {row["mode"] for row in rows} == {"ranged", "melee"}
