# Imported Profile Review

Generated: 2026-04-28T11:54:35.533568Z

## Files

- `weapon_profile_review.csv`: one row per imported weapon profile, joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.
- `suspicious_weapon_review.csv`: filtered weapon profiles with zero or extreme parsed damage characteristics for manual inspection.
- `unit_profile_review.csv`: one row per imported unit with core stat, points, and model-count validation for manual inspection.
- `ability_profile_review.csv`: one row per imported ability profile, joined to unit name, faction, and source file where applicable.
- `ability_modifier_review.csv`: one row per imported ability effect that the calculator turns into a modifier.
- `unit_variant_review.csv`: one row per unit whose name appears more than once, preserving IDs, faction context, and source file.
- `unit_weapon_coverage_review.csv`: one row per unit showing ranged/melee weapon counts and coverage category.
- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need manual loadout selection.
- `source_catalogue_review.csv`: one row per BSData source catalogue with imported row counts, review-risk counts, and exact upstream GitHub file URLs when metadata is available.

## Counts

| Item | Count |
| --- | ---: |
| Units | 1471 |
| Weapon profiles | 8655 |
| Ranged weapon profiles with range | 5577 |
| Ranged weapon profiles missing range | 2 |
| Suspicious weapon profiles | 58 |
| Unit profile review rows | 1471 |
| Unit profile issue rows | 5 |
| Ability profiles | 3143 |
| Ability modifier rows | 368 |
| Duplicate-name unit rows | 186 |
| Weapon coverage rows | 1471 |
| Loadout review rows | 302 |
| Source catalogue rows | 37 |

## Largest Factions

| Faction | Units |
| --- | ---: |
| Imperium - Adeptus Astartes - Space Marines | 132 |
| Aeldari - Aeldari Library | 127 |
| Imperium - Astra Militarum - Library | 119 |
| Xenos - Orks | 98 |
| Chaos - Chaos Space Marines | 84 |
| Chaos - Daemons Library | 68 |
| Xenos - T'au Empire | 68 |
| Xenos - Necrons | 67 |
| Chaos - Death Guard | 51 |
| Imperium - Agents of the Imperium | 50 |
| Imperium - Adeptus Mechanicus | 44 |
| Chaos - Thousand Sons | 42 |

## Source Catalogue Coverage

| Source File | Factions | Units | Weapons | Suspicious Weapons | Unit Issues | Loadout Rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [Imperium - Space Marines.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Imperium%20-%20Space%20Marines.cat) | Imperium - Adeptus Astartes - Space Marines | 132 | 1342 | 0 | 1 | 39 |
| [Aeldari - Aeldari Library.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Aeldari%20-%20Aeldari%20Library.cat) | Aeldari - Aeldari Library | 127 | 667 | 1 | 0 | 22 |
| [Imperium - Astra Militarum - Library.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Imperium%20-%20Astra%20Militarum%20-%20Library.cat) | Imperium - Astra Militarum - Library | 119 | 760 | 4 | 0 | 36 |
| [Orks.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Orks.cat) | Xenos - Orks | 98 | 505 | 7 | 0 | 10 |
| [Chaos - Chaos Space Marines.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Chaos%20-%20Chaos%20Space%20Marines.cat) | Chaos - Chaos Space Marines | 84 | 532 | 0 | 1 | 24 |
| [T'au Empire.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/T%27au%20Empire.cat) | Xenos - T'au Empire | 68 | 440 | 10 | 0 | 17 |
| [Chaos - Chaos Daemons Library.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Chaos%20-%20Chaos%20Daemons%20Library.cat) | Chaos - Daemons Library | 68 | 232 | 0 | 0 | 3 |
| [Necrons.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Necrons.cat) | Xenos - Necrons | 67 | 241 | 5 | 0 | 3 |
| [Chaos - Death Guard.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Chaos%20-%20Death%20Guard.cat) | Chaos - Death Guard | 51 | 308 | 0 | 0 | 11 |
| [Imperium - Agents of the Imperium.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Imperium%20-%20Agents%20of%20the%20Imperium.cat) | Imperium - Agents of the Imperium | 50 | 420 | 0 | 0 | 18 |
| [Imperium - Adeptus Mechanicus.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Imperium%20-%20Adeptus%20Mechanicus.cat) | Imperium - Adeptus Mechanicus | 44 | 267 | 0 | 0 | 7 |
| [Chaos - Thousand Sons.cat](https://github.com/BSData/wh40k-10e/blob/1228d35e79bcf02a5e70ec94e422b7ffce4f980e/Chaos%20-%20Thousand%20Sons.cat) | Chaos - Thousand Sons | 42 | 255 | 0 | 0 | 8 |

## Units With Most Weapon Profiles

| Unit | Weapon Profiles |
| --- | ---: |
| Defiler | 60 |
| Helbrute | 49 |
| Champion of the Chapter [Crucible] | 49 |
| Librarius Adept [Crucible] | 49 |
| Deathwatch Agent [Crucible] | 38 |
| Enthroned Agent [Crucible] | 38 |
| Martial Agent [Crucible] | 38 |
| Exalted Champion [Crucible] | 36 |
| Sorcerous Champion [Crucible] | 36 |
| Soul Forge Tyrant [Crucible] | 36 |
| Hordeboss [Crucible] | 36 |
| Upstart Gretchin [Crucible] | 36 |

## Highest Raw Damage Throughput

| Unit | Weapon | Raw Throughput |
| --- | --- | ---: |
| Warlord Titan | ➤ Arioch power claw - strike | 144.00 |
| Warlord Titan | ➤ Sunfury plasma annihilator - supercharge | 104.00 |
| Warlord Titan | ➤ Arioch power claw - sweep | 96.00 |
| Warlord Titan | Belicosa volcano cannon | 90.00 |
| Warlord Titan | Macro gatling blaster | 90.00 |
| Reaver Titan | ➤ Reaver power fist - strike | 84.00 |
| Phantom Titan | ➤ Wraith glaive - strike | 72.00 |
| Reaver Titan | ➤ Reaver power fist - sweep | 72.00 |
| Gargantuan Squiggoth | ➤ Huge tusks - strike | 72.00 |
| Warbringer Nemesis Titan | Nemesis volcano cannon | 70.00 |
| Warlord Titan | ➤ Sunfury plasma annihilator - standard | 65.00 |
| Warlord Titan | Mori quake cannon | 63.00 |

## Suspicious Weapon Review Reasons

| Reason | Rows |
| --- | ---: |
| extreme AP | 28 |
| very high damage average | 19 |
| very high raw damage throughput | 18 |
| very high attacks average | 16 |

## Suspicious Weapon Severity

| Severity | Rows |
| --- | ---: |
| info | 40 |
| warning | 18 |

## Suspicious Weapon Categories

| Category | Rows |
| --- | ---: |
| extreme_profile | 18 |
| large_platform_profile | 40 |

## Unit Profile Validation

| Severity | Rows |
| --- | ---: |
| info | 5 |
| ok | 1466 |

## Unit Profile Review Reasons

| Reason | Rows |
| --- | ---: |
| missing points | 4 |
| invalid points | 1 |

## Unit Profile Review Categories

| Category | Rows |
| --- | ---: |
| model_points_unset | 5 |
| ok | 1466 |

## Derived Ability Modifiers

| Modifier Type | Rows |
| --- | ---: |
| attack_modifier | 354 |
| damage_reduction | 14 |

## Duplicate Unit Names

| Unit Name | Variants |
| --- | ---: |
| Chaos Land Raider | 5 |
| Chaos Rhino | 5 |
| Chaos Spawn | 5 |
| Defiler | 5 |
| Chaos Predator Annihilator | 4 |
| Chaos Predator Destructor | 4 |
| Helbrute | 4 |
| Heldrake | 4 |
| Hell Talon [Legends] | 4 |
| Hellblade [Legends] | 4 |
| Maulerfiend | 4 |
| Forgefiend | 3 |

## Unit Weapon Coverage

| Coverage | Units |
| --- | ---: |
| both | 1267 |
| melee_only | 145 |
| no_weapons | 16 |
| ranged_only | 43 |

## Ranged Weapon Range Coverage

| Status | Weapon Profiles |
| --- | ---: |
| Explicit range | 5577 |
| Missing range | 2 |

## Loadout Review Reasons

| Reason | Rows |
| --- | ---: |
| mixed loadout profiles | 301 |
| many imported weapon profiles | 133 |
| many ranged profiles | 101 |
| many melee profiles | 49 |

## Loadout Review Severity

| Severity | Rows |
| --- | ---: |
| info | 159 |
| warning | 143 |

## Loadout Review Categories

| Category | Rows |
| --- | ---: |
| crucible_profile | 62 |
| legends_profile | 97 |
| many_profiles | 33 |
| mixed_profiles | 110 |
