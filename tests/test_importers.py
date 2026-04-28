from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.importers.bsdata import import_catalogues


def test_load_units_includes_leadership_and_objective_control(tmp_path):
    data_dir = tmp_path

    units_csv = (
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type,source_file\n"
        "u1,Test,Fictional Unit,4,3+,,2,6,2,100,1,1,,,,Test.cat\n"
    )
    (data_dir / 'units.csv').write_text(units_csv, encoding='utf-8')
    (data_dir / 'weapons.csv').write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds",
        encoding='utf-8'
    )
    (data_dir / 'abilities.csv').write_text('ability_id,source_type,source_id,name,text', encoding='utf-8')
    (data_dir / 'keywords.csv').write_text('keyword_id,keyword', encoding='utf-8')
    (data_dir / 'unit_keywords.csv').write_text('unit_id,keyword_id', encoding='utf-8')

    profiles = load_units_from_directory(data_dir)
    unit = profiles['u1']

    assert unit.leadership == 6
    assert unit.objective_control == 2
    assert unit.source_file == "Test.cat"


def test_load_units_preserves_optional_weapon_range(tmp_path):
    data_dir = tmp_path
    (data_dir / "units.csv").write_text(
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type,source_file\n"
        "u1,Test,Fictional Unit,4,3+,,2,6,2,100,1,1,,,,Test.cat\n",
        encoding="utf-8",
    )
    (data_dir / "weapons.csv").write_text(
        "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,range_inches,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds\n"
        "w1,u1,Bolt rifle,ranged,2,3+,4,-1,1,Assault,24,,,,,,,\n",
        encoding="utf-8",
    )
    (data_dir / "abilities.csv").write_text("ability_id,source_type,source_id,name,text\n", encoding="utf-8")
    (data_dir / "keywords.csv").write_text("keyword_id,keyword\n", encoding="utf-8")
    (data_dir / "unit_keywords.csv").write_text("unit_id,keyword_id\n", encoding="utf-8")

    profiles = load_units_from_directory(data_dir)

    assert profiles["u1"].weapons[0].range_inches == 24


def test_bsdata_importer_extracts_weapon_range_inches(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-1">
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
        <profile name="Bolt Rifle" typeName="Ranged Weapons">
          <characteristics>
            <characteristic name="Range">24&quot;</characteristic>
            <characteristic name="A">2</characteristic>
            <characteristic name="BS">3+</characteristic>
            <characteristic name="S">4</characteristic>
            <characteristic name="AP">-1</characteristic>
            <characteristic name="D">1</characteristic>
            <characteristic name="Keywords">Assault</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    _units, weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert weapons[0].range_inches == "24"


def test_bsdata_importer_keeps_same_name_ranged_and_melee_profiles(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Guard Unit" id="unit-1">
      <profiles>
        <profile name="Guard Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
        <profile name="Guardian Spear" typeName="Ranged Weapons">
          <characteristics>
            <characteristic name="Range">24&quot;</characteristic>
            <characteristic name="A">2</characteristic>
            <characteristic name="BS">2+</characteristic>
            <characteristic name="S">4</characteristic>
            <characteristic name="AP">-1</characteristic>
            <characteristic name="D">2</characteristic>
            <characteristic name="Keywords">Assault</characteristic>
          </characteristics>
        </profile>
        <profile name="Guardian Spear" typeName="Melee Weapons">
          <characteristics>
            <characteristic name="Range">Melee</characteristic>
            <characteristic name="A">5</characteristic>
            <characteristic name="WS">2+</characteristic>
            <characteristic name="S">7</characteristic>
            <characteristic name="AP">-2</characteristic>
            <characteristic name="D">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    _units, weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert {(weapon.name, weapon.weapon_type) for weapon in weapons} == {
        ("Guardian Spear", "ranged"),
        ("Guardian Spear", "melee"),
    }
    assert {weapon.weapon_id for weapon in weapons} == {
        "unit-1:ranged:guardian-spear",
        "unit-1:melee:guardian-spear",
    }


def test_importer_does_not_attach_child_upgrade_abilities_to_unit(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-1">
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
        <profile name="Unit Rule" typeName="Abilities">
          <characteristics>
            <characteristic name="Description">This belongs to the unit.</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="Optional Enhancements" id="group-1">
          <selectionEntries>
            <selectionEntry type="upgrade" import="true" name="Relic Armour" id="upgrade-1">
              <profiles>
                <profile name="Relic Armour" typeName="Abilities">
                  <characteristics>
                    <characteristic name="Description">Subtract 1 from the Damage characteristic of that attack.</characteristic>
                  </characteristics>
                </profile>
              </profiles>
            </selectionEntry>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert [unit.name for unit in units] == ["Line Unit"]
    assert [ability.name for ability in abilities] == ["Unit Rule"]
    assert units[0].source_file == "test.cat"
    assert abilities[0].source_file == "test.cat"


def test_importer_normalises_bare_numeric_roll_stats(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-1">
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3</characteristic>
            <characteristic name="Invulnerable Save">5</characteristic>
            <characteristic name="FNP">6</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, _weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert units[0].save == "3+"
    assert units[0].invulnerable_save == "5+"
    assert units[0].feel_no_pain == "6+"


def test_importer_uses_model_points_when_unit_parent_is_zero(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Walker Unit" id="unit-1">
      <costs>
        <cost name="pts" value="0"/>
      </costs>
      <profiles>
        <profile name="Walker Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">7</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">6</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntries>
        <selectionEntry type="model" import="true" name="Walker" id="model-1">
          <costs>
            <cost name="pts" value="85"/>
          </costs>
        </selectionEntry>
      </selectionEntries>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, _weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert units[0].points == 85


def test_importer_keeps_primary_model_points_over_child_model_costs(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="model" import="true" name="Knight Unit" id="unit-1">
      <costs>
        <cost name="pts" value="410"/>
      </costs>
      <profiles>
        <profile name="Knight Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">12</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">24</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntries>
        <selectionEntry type="model" import="true" name="Optional Servitor" id="model-1">
          <costs>
            <cost name="pts" value="30"/>
          </costs>
        </selectionEntry>
      </selectionEntries>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, _weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert units[0].points == 410


def test_importer_skips_nested_model_profiles_without_direct_points(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Veteran Squad" id="unit-1">
      <costs>
        <cost name="pts" value="100"/>
      </costs>
      <profiles>
        <profile name="Veteran Squad" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntries>
        <selectionEntry type="model" import="true" name="Veteran Sergeant" id="model-1">
          <profiles>
            <profile name="Veteran Sergeant" typeName="Unit">
              <characteristics>
                <characteristic name="T">4</characteristic>
                <characteristic name="SV">3+</characteristic>
                <characteristic name="W">2</characteristic>
              </characteristics>
            </profile>
            <profile name="Power sword" typeName="Melee Weapons">
              <characteristics>
                <characteristic name="A">4</characteristic>
                <characteristic name="WS">3+</characteristic>
                <characteristic name="S">5</characteristic>
                <characteristic name="AP">-2</characteristic>
                <characteristic name="D">1</characteristic>
                <characteristic name="Keywords">-</characteristic>
              </characteristics>
            </profile>
          </profiles>
        </selectionEntry>
      </selectionEntries>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert [unit.name for unit in units] == ["Veteran Squad"]
    assert [weapon.name for weapon in weapons] == ["Power sword"]
    assert weapons[0].unit_id == units[0].unit_id


def test_importer_skips_shared_child_model_refs_without_direct_points(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <sharedSelectionEntries>
    <selectionEntry type="model" import="true" name="Shared Specialist" id="model-1">
      <profiles>
        <profile name="Shared Specialist" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
        <profile name="Special rifle" typeName="Ranged Weapons">
          <characteristics>
            <characteristic name="A">2</characteristic>
            <characteristic name="BS">3+</characteristic>
            <characteristic name="S">4</characteristic>
            <characteristic name="AP">-1</characteristic>
            <characteristic name="D">1</characteristic>
            <characteristic name="Keywords">-</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </sharedSelectionEntries>
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Kill Team" id="unit-1">
      <costs>
        <cost name="pts" value="100"/>
      </costs>
      <profiles>
        <profile name="Kill Team" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntries>
        <selectionEntry type="upgrade" import="true" name="5 models" id="option-1">
          <entryLinks>
            <entryLink type="selectionEntry" name="Shared Specialist" targetId="model-1"/>
          </entryLinks>
        </selectionEntry>
      </selectionEntries>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, _abilities, _keywords, _unit_keywords = import_catalogues([catalogue])

    assert [unit.name for unit in units] == ["Kill Team"]
    assert [weapon.name for weapon in weapons] == ["Special rifle"]
    assert weapons[0].unit_id == units[0].unit_id


def test_importer_does_not_attach_crusade_weapon_modifications_to_units(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <sharedSelectionEntryGroups>
    <selectionEntryGroup name="Weapon Modifications" id="mod-group">
      <comment>Crusade content</comment>
      <selectionEntries>
        <selectionEntry type="upgrade" import="true" name="Vortex Grenade" id="vortex">
          <profiles>
            <profile name="Vertebrax of Vodun" typeName="Ranged Weapons">
              <characteristics>
                <characteristic name="A">1</characteristic>
                <characteristic name="BS">2+</characteristic>
                <characteristic name="S">*</characteristic>
                <characteristic name="AP">*</characteristic>
                <characteristic name="D">*</characteristic>
                <characteristic name="Keywords">Assault</characteristic>
              </characteristics>
            </profile>
          </profiles>
        </selectionEntry>
      </selectionEntries>
    </selectionEntryGroup>
  </sharedSelectionEntryGroups>
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-1">
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="Wargear" id="wargear">
          <selectionEntries>
            <selectionEntry type="upgrade" import="true" name="Bolt Rifle" id="bolt-rifle">
              <profiles>
                <profile name="Bolt Rifle" typeName="Ranged Weapons">
                  <characteristics>
                    <characteristic name="A">2</characteristic>
                    <characteristic name="BS">3+</characteristic>
                    <characteristic name="S">4</characteristic>
                    <characteristic name="AP">0</characteristic>
                    <characteristic name="D">1</characteristic>
                    <characteristic name="Keywords">-</characteristic>
                  </characteristics>
                </profile>
              </profiles>
              <entryLinks>
                <entryLink name="Weapon Modifications" targetId="mod-group" type="selectionEntryGroup"/>
              </entryLinks>
            </selectionEntry>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert [unit.name for unit in units] == ["Line Unit"]
    assert [weapon.name for weapon in weapons] == ["Bolt Rifle"]


def test_importer_distinguishes_same_named_abilities_with_different_profiles(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Shield Unit" id="unit-1">
      <profiles>
        <profile name="Shield Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
        <profile name="Invulnerable Save" typeName="Abilities" id="profile-5-plus">
          <characteristics>
            <characteristic name="Description">This model has a 5+ invulnerable save.</characteristic>
          </characteristics>
        </profile>
        <profile name="Invulnerable Save" typeName="Abilities" id="profile-4-plus">
          <characteristics>
            <characteristic name="Description">This model has a 4+ invulnerable save.</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert [unit.name for unit in units] == ["Shield Unit"]
    assert [ability.name for ability in abilities] == ["Invulnerable Save", "Invulnerable Save"]
    assert len({ability.ability_id for ability in abilities}) == 2


def test_importer_skips_crusade_variant_unit_carriers(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-1">
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
    <selectionEntry type="unit" import="true" name="Line Unit" id="unit-crusade">
      <comment>Crusade variant</comment>
      <profiles>
        <profile name="Line Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert [unit.unit_id for unit in units] == ["unit-1"]


def test_importer_uses_model_cost_when_unit_has_no_direct_points(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Heavy Destroyers" id="unit-1">
      <profiles>
        <profile name="Heavy Destroyers" typeName="Unit">
          <characteristics>
            <characteristic name="T">6</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">4</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="1-3 Heavy Destroyers" id="group-1">
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Destroyer w/ gun" id="model-1">
              <constraints>
                <constraint type="max" value="3" field="selections" scope="parent"/>
              </constraints>
              <costs>
                <cost name="pts" value="55"/>
                <cost name="Crusade Points" value="0"/>
              </costs>
            </selectionEntry>
          </selectionEntries>
          <constraints>
            <constraint type="min" value="1" field="selections" scope="parent"/>
            <constraint type="max" value="3" field="selections" scope="parent"/>
          </constraints>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].points == 55


def test_importer_uses_group_size_for_nested_alternative_models(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Heavy Destroyers" id="unit-1">
      <profiles>
        <profile name="Heavy Destroyers" typeName="Unit">
          <characteristics>
            <characteristic name="T">6</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">4</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="1-3 Heavy Destroyers" id="group-1">
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Destroyer w/ enmitic exterminator" id="model-1">
              <constraints>
                <constraint type="max" value="3" field="selections" scope="parent"/>
              </constraints>
            </selectionEntry>
            <selectionEntry type="model" import="true" name="Destroyer w/ gauss destructor" id="model-2">
              <constraints>
                <constraint type="max" value="3" field="selections" scope="parent"/>
              </constraints>
            </selectionEntry>
          </selectionEntries>
          <constraints>
            <constraint type="min" value="1" field="selections" scope="parent"/>
            <constraint type="max" value="3" field="selections" scope="parent"/>
          </constraints>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].models_min == 1
    assert units[0].models_max == 3


def test_importer_falls_back_to_nested_model_size_when_group_has_no_bounds(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Swarm Unit" id="unit-1">
      <profiles>
        <profile name="Swarm Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">3</characteristic>
            <characteristic name="SV">6+</characteristic>
            <characteristic name="W">1</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="Models" id="group-1">
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Swarm Model" id="model-1">
              <constraints>
                <constraint type="min" value="10" field="selections" scope="parent"/>
                <constraint type="max" value="20" field="selections" scope="parent"/>
              </constraints>
            </selectionEntry>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].models_min == 10
    assert units[0].models_max == 20


def test_importer_adds_required_nested_leader_model_without_optional_group_max(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Mob Unit" id="unit-1">
      <profiles>
        <profile name="Mob Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">5</characteristic>
            <characteristic name="SV">5+</characteristic>
            <characteristic name="W">1</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntryGroups>
        <selectionEntryGroup name="9-19 Troopers" id="group-1">
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Trooper" id="model-1"/>
          </selectionEntries>
          <constraints>
            <constraint type="min" value="9" field="selections" scope="parent"/>
            <constraint type="max" value="19" field="selections" scope="parent"/>
          </constraints>
          <selectionEntryGroups>
            <selectionEntryGroup name="Special Weapons" id="specials">
              <selectionEntries>
                <selectionEntry type="model" import="true" name="Trooper w/ special weapon" id="special-1"/>
              </selectionEntries>
              <constraints>
                <constraint type="max" value="1" field="selections" scope="parent"/>
              </constraints>
            </selectionEntryGroup>
          </selectionEntryGroups>
        </selectionEntryGroup>
        <selectionEntryGroup name="Boss Nob" id="leader-group">
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Boss Nob" id="leader-1">
              <constraints>
                <constraint type="min" value="1" field="selections" scope="parent"/>
                <constraint type="max" value="1" field="selections" scope="parent"/>
              </constraints>
            </selectionEntry>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].models_min == 10
    assert units[0].models_max == 20


def test_importer_normalises_model_carriers_to_single_model_and_blank_keywords_to_dash(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="model" import="true" name="Named Tank" id="tank-1">
      <costs>
        <cost name="pts" value="100"/>
      </costs>
      <profiles>
        <profile name="Named Tank" typeName="Unit">
          <characteristics>
            <characteristic name="T">10</characteristic>
            <characteristic name="SV">2+</characteristic>
            <characteristic name="W">12</characteristic>
          </characteristics>
        </profile>
        <profile name="Empty blade" typeName="Melee Weapons">
          <characteristics>
            <characteristic name="A">3</characteristic>
            <characteristic name="WS">3+</characteristic>
            <characteristic name="S">6</characteristic>
            <characteristic name="AP">-1</characteristic>
            <characteristic name="D">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].selection_type == "model"
    assert units[0].models_min == 1
    assert units[0].models_max == 1
    assert units[0].source_file == "test.cat"
    assert weapons[0].keywords == "-"
    assert weapons[0].source_file == "test.cat"


def test_importer_sums_required_leader_model_with_model_group_size(tmp_path):
    catalogue = tmp_path / "test.cat"
    catalogue.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<catalogue name="Test Faction">
  <selectionEntries>
    <selectionEntry type="unit" import="true" name="Squad Unit" id="unit-1">
      <profiles>
        <profile name="Squad Unit" typeName="Unit">
          <characteristics>
            <characteristic name="T">4</characteristic>
            <characteristic name="SV">3+</characteristic>
            <characteristic name="W">2</characteristic>
          </characteristics>
        </profile>
      </profiles>
      <selectionEntries>
        <selectionEntry type="model" import="true" name="Squad Champion" id="leader-1">
          <constraints>
            <constraint type="min" value="1" field="selections" scope="parent"/>
            <constraint type="max" value="1" field="selections" scope="parent"/>
          </constraints>
        </selectionEntry>
      </selectionEntries>
      <selectionEntryGroups>
        <selectionEntryGroup name="9 - 19 Squad Models" id="group-1">
          <constraints>
            <constraint type="min" value="9" field="selections" scope="parent"/>
            <constraint type="max" value="19" field="selections" scope="parent"/>
          </constraints>
          <selectionEntries>
            <selectionEntry type="model" import="true" name="Squad Model" id="model-1"/>
          </selectionEntries>
        </selectionEntryGroup>
      </selectionEntryGroups>
    </selectionEntry>
  </selectionEntries>
</catalogue>
""",
        encoding="utf-8",
    )

    units, weapons, abilities, keywords, unit_keywords = import_catalogues([catalogue])

    assert units[0].models_min == 10
    assert units[0].models_max == 20
