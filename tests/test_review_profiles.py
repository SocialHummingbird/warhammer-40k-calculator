import csv
import json

from review_profiles import (
    build_ability_review_rows,
    build_ability_modifier_review_rows,
    build_loadout_review_rows,
    build_source_catalogue_review_rows,
    build_suspicious_weapon_review_rows,
    build_unit_variant_review_rows,
    build_unit_weapon_coverage_rows,
    build_weapon_review_rows,
    write_profile_review,
)


def test_build_weapon_review_rows_joins_unit_context():
    units = {
        "u1": {
            "unit_id": "u1",
            "name": "Intercessor Squad",
            "faction": "Imperium",
            "selection_type": "unit",
            "source_file": "Space Marines.cat",
            "points": "80",
            "models_min": "5",
            "models_max": "10",
        }
    }
    weapons = [
        {
            "weapon_id": "w1",
            "unit_id": "u1",
            "name": "Bolt rifle",
            "weapon_type": "ranged",
            "attacks": "2",
            "skill": "3+",
            "strength": "4",
            "ap": "-1",
            "damage": "1",
            "keywords": "Assault",
            "source_file": "Space Marines.cat",
        }
    ]

    rows = build_weapon_review_rows(weapons, units)

    assert rows[0]["unit_name"] == "Intercessor Squad"
    assert rows[0]["faction"] == "Imperium"
    assert rows[0]["source_file"] == "Space Marines.cat"
    assert rows[0]["weapon_name"] == "Bolt rifle"
    assert rows[0]["models_max"] == "10"
    assert rows[0]["attacks_average"] == "2.00"
    assert rows[0]["strength_average"] == "4.00"
    assert rows[0]["damage_average"] == "1.00"
    assert rows[0]["attacks_parse_status"] == "ok"
    assert rows[0]["strength_parse_status"] == "ok"
    assert rows[0]["damage_parse_status"] == "ok"
    assert rows[0]["raw_damage_throughput"] == "2.00"


def test_build_weapon_review_rows_derives_dice_averages_and_plus_strength():
    units = {"u1": {"unit_id": "u1", "name": "Tank", "faction": "Imperium"}}
    weapons = [
        {
            "weapon_id": "w1",
            "unit_id": "u1",
            "name": "Swingy cannon",
            "weapon_type": "ranged",
            "attacks": "D6+3",
            "skill": "3+",
            "strength": "8+",
            "ap": "-2",
            "damage": "D6+1",
            "keywords": "Blast",
        }
    ]

    rows = build_weapon_review_rows(weapons, units)

    assert rows[0]["attacks_average"] == "6.50"
    assert rows[0]["strength_average"] == "8.00"
    assert rows[0]["damage_average"] == "4.50"
    assert rows[0]["raw_damage_throughput"] == "29.25"


def test_build_weapon_review_rows_marks_unsupported_damage_expressions():
    units = {"u1": {"unit_id": "u1", "name": "Special Weapon", "faction": "Test"}}
    weapons = [
        {
            "weapon_id": "w1",
            "unit_id": "u1",
            "name": "Narrative damage",
            "weapon_type": "ranged",
            "attacks": "1",
            "skill": "2+",
            "strength": "10",
            "ap": "-4",
            "damage": "D*",
            "keywords": "",
        }
    ]

    rows = build_weapon_review_rows(weapons, units)
    suspicious_rows = build_suspicious_weapon_review_rows(rows)

    assert rows[0]["damage_average"] == "0.00"
    assert rows[0]["damage_parse_status"] == "unsupported"
    assert "unsupported damage expression" in suspicious_rows[0]["review_reason"]


def test_build_suspicious_weapon_review_rows_flags_zero_and_extreme_profiles():
    rows = build_suspicious_weapon_review_rows(
        [
            {
                "faction": "Test",
                "unit_name": "Broken",
                "weapon_name": "Missing damage",
                "ap": "0",
                "attacks_average": "1.00",
                "strength_average": "4.00",
                "damage_average": "0.00",
                "raw_damage_throughput": "0.00",
            },
            {
                "faction": "Test",
                "unit_name": "Titan",
                "weapon_name": "Large gun",
                "ap": "-5",
                "attacks_average": "30.00",
                "strength_average": "20.00",
                "damage_average": "3.00",
                "raw_damage_throughput": "90.00",
            },
            {
                "faction": "Test",
                "unit_name": "Normal",
                "weapon_name": "Bolt rifle",
                "ap": "-1",
                "attacks_average": "2.00",
                "strength_average": "4.00",
                "damage_average": "1.00",
                "raw_damage_throughput": "2.00",
            },
        ]
    )

    assert len(rows) == 2
    assert "zero raw damage throughput" in rows[0]["review_reason"]
    assert "very high raw damage throughput" in rows[1]["review_reason"]
    assert "extreme AP" in rows[1]["review_reason"]


def test_build_ability_review_rows_joins_unit_context_only_for_unit_sources():
    units = {"u1": {"unit_id": "u1", "name": "Boyz", "faction": "Xenos", "selection_type": "unit"}}
    abilities = [
        {"ability_id": "a1", "source_type": "unit", "source_id": "u1", "name": "Mob Rule", "text": "Text"},
        {"ability_id": "a2", "source_type": "rule", "source_id": "r1", "name": "Core Rule", "text": "Text"},
    ]

    rows = build_ability_review_rows(abilities, units)

    unit_row = next(row for row in rows if row["ability_id"] == "a1")
    rule_row = next(row for row in rows if row["ability_id"] == "a2")
    assert unit_row["unit_name"] == "Boyz"
    assert rule_row["unit_name"] == ""


def test_build_ability_modifier_review_rows_lists_calculated_effects():
    units = [
        {
            "unit_id": "u1",
            "name": "Rule Carrier",
            "faction": "Test",
            "selection_type": "unit",
            "toughness": "4",
            "save": "3+",
            "wounds": "2",
        }
    ]
    abilities = [
        {
            "ability_id": "a1",
            "source_type": "unit",
            "source_id": "u1",
            "name": "Targeted Accuracy",
            "text": "Each time this unit makes a ranged attack against a Vehicle, add 1 to the Hit roll.",
        },
        {
            "ability_id": "a2",
            "source_type": "unit",
            "source_id": "u1",
            "name": "Armoured Shell",
            "text": "Subtract 1 from the Damage characteristic of attacks allocated to this model.",
        },
    ]

    rows = build_ability_modifier_review_rows(units, abilities)

    attack_row = next(row for row in rows if row["modifier_type"] == "attack_modifier")
    damage_row = next(row for row in rows if row["modifier_type"] == "damage_reduction")
    assert attack_row["unit_name"] == "Rule Carrier"
    assert attack_row["hit_modifier"] == "1"
    assert attack_row["applies_to_ranged"] == "true"
    assert attack_row["target_keywords"] == "vehicle"
    assert damage_row["source"] == "Armoured Shell"
    assert damage_row["damage_reduction"] == "1.00"


def test_build_unit_variant_review_rows_lists_duplicate_names_with_ids():
    rows = build_unit_variant_review_rows(
        [
            {
                "unit_id": "u1",
                "name": "Daemon Prince",
                "faction": "Chaos - Daemons",
                "selection_type": "unit",
                "points": "180",
            },
            {
                "unit_id": "u2",
                "name": "Daemon Prince",
                "faction": "Chaos - Thousand Sons",
                "selection_type": "unit",
                "points": "190",
            },
            {
                "unit_id": "u3",
                "name": "Unique Unit",
                "faction": "Test",
                "selection_type": "unit",
                "points": "100",
            },
        ]
    )

    assert [row["unit_id"] for row in rows] == ["u1", "u2"]
    assert {row["variant_count"] for row in rows} == {"2"}


def test_build_unit_weapon_coverage_rows_counts_ranged_and_melee():
    units = [
        {"unit_id": "u1", "name": "Hybrid", "faction": "Test", "selection_type": "unit"},
        {"unit_id": "u2", "name": "Shooter", "faction": "Test", "selection_type": "unit"},
        {"unit_id": "u3", "name": "Support", "faction": "Test", "selection_type": "unit"},
    ]
    weapons = [
        {"weapon_id": "w1", "unit_id": "u1", "name": "Gun", "weapon_type": "ranged"},
        {"weapon_id": "w2", "unit_id": "u1", "name": "Blade", "weapon_type": "melee"},
        {"weapon_id": "w3", "unit_id": "u2", "name": "Gun", "weapon_type": "ranged"},
    ]

    rows = {row["unit_id"]: row for row in build_unit_weapon_coverage_rows(units, weapons)}

    assert rows["u1"]["coverage"] == "both"
    assert rows["u1"]["ranged_weapons"] == "1"
    assert rows["u1"]["melee_weapons"] == "1"
    assert rows["u2"]["coverage"] == "ranged_only"
    assert rows["u3"]["coverage"] == "no_weapons"


def test_build_loadout_review_rows_flags_many_imported_profiles():
    rows = build_loadout_review_rows(
        [
            {
                "unit_id": "u1",
                "unit_name": "Champion",
                "faction": "Test",
                "total_weapons": "18",
                "ranged_weapons": "12",
                "melee_weapons": "6",
            },
            {
                "unit_id": "u2",
                "unit_name": "Normal",
                "faction": "Test",
                "total_weapons": "3",
                "ranged_weapons": "2",
                "melee_weapons": "1",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0]["unit_id"] == "u1"
    assert "many imported weapon profiles" in rows[0]["review_reason"]
    assert "many ranged profiles" in rows[0]["review_reason"]


def test_build_source_catalogue_review_rows_summarizes_review_counts():
    rows = build_source_catalogue_review_rows(
        units=[
            {"unit_id": "u1", "faction": "Imperium", "source_file": "Space Marines.cat"},
            {"unit_id": "u2", "faction": "Imperium", "source_file": "Space Marines.cat"},
            {"unit_id": "u3", "faction": "Xenos", "source_file": "Orks.cat"},
        ],
        weapon_rows=[
            {"weapon_id": "w1", "source_file": "Space Marines.cat"},
            {"weapon_id": "w2", "source_file": "Orks.cat"},
            {"weapon_id": "w3", "source_file": "Orks.cat"},
        ],
        ability_rows=[
            {"ability_id": "a1", "source_file": "Space Marines.cat"},
        ],
        suspicious_weapon_rows=[
            {"weapon_id": "w3", "source_file": "Orks.cat"},
        ],
        loadout_rows=[
            {"unit_id": "u1", "source_file": "Space Marines.cat"},
        ],
        unit_variant_rows=[
            {"unit_id": "u2", "source_file": "Space Marines.cat"},
        ],
        weapon_coverage_rows=[
            {"unit_id": "u1", "source_file": "Space Marines.cat", "coverage": "both"},
            {"unit_id": "u3", "source_file": "Orks.cat", "coverage": "no_weapons"},
        ],
    )

    by_source = {row["source_file"]: row for row in rows}
    assert by_source["Space Marines.cat"]["units"] == "2"
    assert by_source["Space Marines.cat"]["source_url"] == ""
    assert by_source["Space Marines.cat"]["weapon_profiles"] == "1"
    assert by_source["Space Marines.cat"]["loadout_review_rows"] == "1"
    assert by_source["Space Marines.cat"]["duplicate_name_unit_rows"] == "1"
    assert by_source["Orks.cat"]["suspicious_weapon_profiles"] == "1"
    assert by_source["Orks.cat"]["no_weapon_units"] == "1"


def test_write_profile_review_outputs_joined_csvs_and_markdown(tmp_path):
    (tmp_path / "units.csv").write_text(
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,move,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type,source_file\n"
        "u1,Imperium,Intercessor Squad,4,3+,,2,6,6+,2,80,5,10,,,unit,Space Marines.cat\n"
        "u2,Other,Intercessor Squad,4,3+,,2,6,6+,2,90,5,10,,,unit,Other.cat\n",
        encoding="utf-8",
    )
    (tmp_path / "weapons.csv").write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds,source_file\n"
        "w1,u1,Bolt rifle,ranged,2,3+,4,-1,1,Assault,,,,,,,,Space Marines.cat\n",
        encoding="utf-8",
    )
    (tmp_path / "abilities.csv").write_text(
        "ability_id,source_type,source_id,name,text,source_file\n"
        "a1,unit,u1,Oath,Ability text,Space Marines.cat\n",
        encoding="utf-8",
    )
    (tmp_path / "metadata.json").write_text(
        json.dumps(
            {
                "github_subdir": None,
                "source_revisions": [
                    {
                        "remote_origin": "https://github.com/BSData/wh40k-10e.git",
                        "commit": "abc123",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    counts = write_profile_review(tmp_path)

    assert counts == {
        "units": 2,
        "weapon_profiles": 1,
        "suspicious_weapon_profiles": 0,
        "ability_profiles": 1,
        "ability_modifiers": 0,
        "unit_name_variants": 2,
        "unit_weapon_coverage_rows": 2,
        "loadout_review_rows": 0,
        "source_catalogue_review_rows": 2,
    }
    with (tmp_path / "weapon_profile_review.csv").open(newline="", encoding="utf-8") as handle:
        weapon_rows = list(csv.DictReader(handle))
    with (tmp_path / "suspicious_weapon_review.csv").open(newline="", encoding="utf-8") as handle:
        suspicious_weapon_rows = list(csv.DictReader(handle))
    with (tmp_path / "unit_variant_review.csv").open(newline="", encoding="utf-8") as handle:
        variant_rows = list(csv.DictReader(handle))
    with (tmp_path / "unit_weapon_coverage_review.csv").open(newline="", encoding="utf-8") as handle:
        coverage_rows = list(csv.DictReader(handle))
    with (tmp_path / "ability_modifier_review.csv").open(newline="", encoding="utf-8") as handle:
        modifier_rows = list(csv.DictReader(handle))
    with (tmp_path / "loadout_review.csv").open(newline="", encoding="utf-8") as handle:
        loadout_rows = list(csv.DictReader(handle))
    with (tmp_path / "source_catalogue_review.csv").open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    assert weapon_rows[0]["unit_name"] == "Intercessor Squad"
    assert weapon_rows[0]["source_file"] == "Space Marines.cat"
    assert suspicious_weapon_rows == []
    assert {row["unit_id"] for row in variant_rows} == {"u1", "u2"}
    assert {row["coverage"] for row in coverage_rows} == {"ranged_only", "no_weapons"}
    assert modifier_rows == []
    assert loadout_rows == []
    assert {row["source_file"] for row in source_rows} == {"Space Marines.cat", "Other.cat"}
    assert {
        row["source_url"]
        for row in source_rows
    } == {
        "https://github.com/BSData/wh40k-10e/blob/abc123/Space%20Marines.cat",
        "https://github.com/BSData/wh40k-10e/blob/abc123/Other.cat",
    }
    profile_review = (tmp_path / "profile_review.md").read_text(encoding="utf-8")
    assert "Imported Profile Review" in profile_review
    assert "Duplicate Unit Names" in profile_review
    assert "Unit Weapon Coverage" in profile_review
    assert "Highest Raw Damage Throughput" in profile_review
    assert "Suspicious Weapon Review Reasons" in profile_review
    assert "Derived Ability Modifiers" in profile_review
    assert "Loadout Review Reasons" in profile_review
    assert "Source Catalogue Coverage" in profile_review
    assert "https://github.com/BSData/wh40k-10e/blob/abc123/Space%20Marines.cat" in profile_review
