from audit_import import audit_abilities, audit_unit_keywords, audit_units, audit_weapons, build_audit_report, write_audit_report


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
            }
        ],
        unit_ids={"u1"},
    )
    ability_issues = audit_abilities(
        [{"ability_id": "a1", "source_type": "unit", "source_id": "missing", "name": "Rule", "text": ""}],
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


def test_build_audit_report_includes_severity_summary(tmp_path):
    (tmp_path / "units.csv").write_text(
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,move,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type\n"
        "u1,Test,Target,4,3+,,2,,,,100,1,1,,,\n",
        encoding="utf-8",
    )
    (tmp_path / "weapons.csv").write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds\n"
        "w1,u1,Bad Gun,ranged,1,3+,*,0,D*,Assault,,,,,,,\n",
        encoding="utf-8",
    )
    (tmp_path / "abilities.csv").write_text("ability_id,source_type,source_id,name,text\n", encoding="utf-8")
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
            },
        ]
    )

    assert issues["missing_points"] == ["Playable Unit (x1)"]
    assert issues["missing_models_min"] == ["Playable Unit (x1)"]
    assert issues["missing_models_max"] == ["Playable Unit (x1)"]
