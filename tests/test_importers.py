from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.importers.bsdata import import_catalogues


def test_load_units_includes_leadership_and_objective_control(tmp_path):
    data_dir = tmp_path

    units_csv = (
        "unit_id,faction,name,toughness,save,invulnerable_save,wounds,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type\n"
        "u1,Test,Fictional Unit,4,3+,,2,6,2,100,1,1,,,\n"
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
    assert weapons[0].keywords == "-"


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
