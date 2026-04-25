from audit_import import (
    audit_abilities,
    audit_schema,
    audit_unit_keywords,
    audit_units,
    audit_weapons,
    build_audit_report,
    build_schema_review_rows,
    write_audit_report,
    write_schema_review,
)


def test_audit_weapons_flags_placeholder_profile_stats():
    issues = audit_weapons(
        [
            {
                "weapon_id": "w1",
                "unit_id": "u1",
                "name": "Vertebrax of Vodun",
                "weapon_type": "ranged",
                "attacks": "1",
                "skill": "2+",
                "strength": "*",
                "ap": "*",
                "damage": "D*",
                "keywords": "Assault",
                "source_file": "Test.cat",
            }
        ],
        unit_ids={"u1"},
    )

    assert "placeholder_strength" in issues
    assert "placeholder_ap" in issues
    assert "placeholder_damage" in issues


def test_audit_weapons_accepts_valid_dice_profiles():
    issues = audit_weapons(
        [
            {
                "weapon_id": "w1",
                "unit_id": "u1",
                "name": "Twin magna lascannon",
                "weapon_type": "ranged",
                "attacks": "2",
                "skill": "2+",
                "strength": "18",
                "ap": "-4",
                "damage": "D6+6",
                "keywords": "Blast",
                "source_file": "Test.cat",
            }
        ],
        unit_ids={"u1"},
    )

    assert issues == {}


def test_audit_weapons_accepts_variable_strength_profiles():
    issues = audit_weapons(
        [
            {
                "weapon_id": "w1",
                "unit_id": "u1",
                "name": "Zzap gun",
                "weapon_type": "ranged",
                "attacks": "1",
                "skill": "5+",
                "strength": "2D6",
                "ap": "-3",
                "damage": "5",
                "keywords": "Anti-Vehicle 4+",
                "source_file": "Test.cat",
            },
            {
                "weapon_id": "w2",
                "unit_id": "u1",
                "name": "Chainfist",
                "weapon_type": "melee",
                "attacks": "3",
                "skill": "4+",
                "strength": "8+",
                "ap": "-2",
                "damage": "2",
                "keywords": "Anti-Vehicle 3+",
                "source_file": "Test.cat",
            },
        ],
        unit_ids={"u1"},
    )

    assert "invalid_strength" not in issues


def test_audit_cross_references_flag_orphans():
    weapon_issues = audit_weapons(
        [
            {
                "weapon_id": "w1",
                "unit_id": "missing",
                "name": "Bolt rifle",
                "weapon_type": "ranged",
                "attacks": "2",
                "skill": "3+",
                "strength": "4",
                "ap": "0",
                "damage": "1",
                "keywords": "-",
                "source_file": "Test.cat",
            }
        ],
        unit_ids={"u1"},
    )
    ability_issues = audit_abilities(
        [{"ability_id": "a1", "source_type": "unit", "source_id": "missing", "name": "Rule", "text": "", "source_file": "Test.cat"}],
        unit_ids={"u1"},
    )
    keyword_issues = audit_unit_keywords(
        [{"unit_id": "missing", "keyword_id": "k-missing"}],
        unit_ids={"u1"},
        keyword_ids={"k1"},
    )

    assert "orphaned_weapons" in weapon_issues
    assert "orphaned_unit_abilities" in ability_issues
    assert "orphaned_unit_keywords" in keyword_issues
    assert "orphaned_keyword_ids" in keyword_issues


def test_audit_flags_missing_source_files():
    unit_issues = audit_units(
        [
            {
                "unit_id": "u1",
                "name": "Unit",
                "toughness": "4",
                "save": "3+",
                "wounds": "2",
                "points": "100",
                "models_min": "1",
                "models_max": "1",
                "selection_type": "unit",
                "source_file": "",
            }
        ]
    )
    weapon_issues = audit_weapons(
        [
            {
                "weapon_id": "w1",
                "unit_id": "u1",
                "name": "Gun",
                "weapon_type": "ranged",
                "attacks": "1",
                "skill": "3+",
                "strength": "4",
                "ap": "0",
                "damage": "1",
                "keywords": "-",
                "source_file": "",
            }
        ],
        unit_ids={"u1"},
    )
    ability_issues = audit_abilities(
        [{"ability_id": "a1", "source_type": "unit", "source_id": "u1", "name": "Rule", "text": "", "source_file": ""}],
        unit_ids={"u1"},
    )

    assert "missing_unit_source_file" in unit_issues
    assert "missing_weapon_source_file" in weapon_issues
    assert "missing_ability_source_file" in ability_issues


def test_audit_schema_flags_missing_required_columns():
    issues = audit_schema(
        {
            "units": ["unit_id", "name"],
            "weapons": ["weapon_id", "unit_id", "name"],
            "abilities": ["ability_id", "source_type", "source_id", "name", "text"],
            "keywords": ["keyword_id", "keyword", "description"],
            "unit_keywords": ["unit_id", "keyword_id"],
        }
    )

    assert "missing_required_columns" in issues
    assert any("units.csv missing:" in sample and "source_file" in sample for sample in issues["missing_required_columns"])
    assert any("weapons.csv missing:" in sample and "damage" in sample for sample in issues["missing_required_columns"])


def test_schema_review_rows_record_required_and_missing_columns(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name,source_file\nu1,Test,Test.cat\n", encoding="utf-8")
    (tmp_path / "weapons.csv").write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds,source_file\n",
        encoding="utf-8",
    )
    (tmp_path / "abilities.csv").write_text("ability_id,source_type,source_id,name,text,source_file\n", encoding="utf-8")
    (tmp_path / "keywords.csv").write_text("keyword_id,keyword,description\n", encoding="utf-8")
    (tmp_path / "unit_keywords.csv").write_text("unit_id,keyword_id\n", encoding="utf-8")

    rows = {row["table"]: row for row in build_schema_review_rows(tmp_path)}
    written = write_schema_review(tmp_path)

    assert written == 5
    assert rows["units"]["status"] == "fail"
    assert "toughness" in rows["units"]["missing_columns"]
    assert rows["weapons"]["status"] == "pass"
    assert (tmp_path / "schema_review.csv").exists()


def test_build_audit_report_includes_severity_summary(tmp_path):
    (tmp_path / "units.csv").write_text(
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,move,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type,source_file\n"
        "u1,Test,Target,4,3+,,2,,,,100,1,1,,,unit,Test.cat\n",
        encoding="utf-8",
    )
    (tmp_path / "weapons.csv").write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds,source_file\n"
        "w1,u1,Bad Gun,ranged,1,3+,*,0,D*,Assault,,,,,,,,Test.cat\n",
        encoding="utf-8",
    )
    (tmp_path / "abilities.csv").write_text("ability_id,source_type,source_id,name,text,source_file\n", encoding="utf-8")
    (tmp_path / "keywords.csv").write_text("keyword_id,keyword,description\n", encoding="utf-8")
    (tmp_path / "unit_keywords.csv").write_text("unit_id,keyword_id\n", encoding="utf-8")

    report = build_audit_report(tmp_path)
    output = tmp_path / "audit_report.json"
    write_audit_report(report, output)

    assert report["summary"]["error"] >= 2
    assert report["row_counts"]["weapons"] == 1
    assert output.exists()


def test_audit_units_only_requires_points_and_sizes_for_unit_rows():
    issues = audit_units(
        [
            {
                "unit_id": "m1",
                "name": "Embedded Model",
                "toughness": "4",
                "save": "3+",
                "wounds": "2",
                "points": "",
                "models_min": "",
                "models_max": "",
                "selection_type": "model",
                "source_file": "Test.cat",
            },
            {
                "unit_id": "u1",
                "name": "Playable Unit",
                "toughness": "4",
                "save": "3+",
                "wounds": "2",
                "points": "",
                "models_min": "",
                "models_max": "",
                "selection_type": "unit",
                "source_file": "Test.cat",
            },
        ]
    )

    assert issues["missing_points"] == ["Playable Unit (x1)"]
    assert issues["missing_models_min"] == ["Playable Unit (x1)"]
    assert issues["missing_models_max"] == ["Playable Unit (x1)"]


def test_audit_units_only_checks_duplicate_names_for_unit_rows():
    issues = audit_units(
        [
            {
                "unit_id": "u1",
                "faction": "Test",
                "name": "Cronos",
                "toughness": "7",
                "save": "3+",
                "wounds": "7",
                "points": "55",
                "models_min": "1",
                "models_max": "2",
                "selection_type": "unit",
                "source_file": "Test.cat",
            },
            {
                "unit_id": "m1",
                "faction": "Test",
                "name": "Cronos",
                "toughness": "7",
                "save": "3+",
                "wounds": "7",
                "points": "",
                "models_min": "1",
                "models_max": "1",
                "selection_type": "model",
                "source_file": "Test.cat",
            },
        ]
    )

    assert "duplicate_names" not in issues
