# Imported Profile Review

Generated: 2026-04-25T18:17:03.234759Z

## Files

- `weapon_profile_review.csv`: one row per imported weapon profile, joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.
- `suspicious_weapon_review.csv`: filtered weapon profiles with zero or extreme parsed damage characteristics for manual inspection.
- `ability_profile_review.csv`: one row per imported ability profile, joined to unit name, faction, and source file where applicable.
- `ability_modifier_review.csv`: one row per imported ability effect that the calculator turns into a modifier.
- `unit_variant_review.csv`: one row per unit whose name appears more than once, preserving IDs, faction context, and source file.
- `unit_weapon_coverage_review.csv`: one row per unit showing ranged/melee weapon counts and coverage category.
- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need manual loadout selection.
- `source_catalogue_review.csv`: one row per BSData source catalogue with imported row counts, review-risk counts, and exact upstream GitHub file URLs when metadata is available.

## Counts

| Item | Count |
| --- | ---: |
| Units | 2093 |
| Weapon profiles | 10808 |
| Suspicious weapon profiles | 58 |
| Ability profiles | 3173 |
| Ability modifier rows | 370 |
| Duplicate-name unit rows | 365 |
| Weapon coverage rows | 2093 |
| Loadout review rows | 344 |
| Source catalogue rows | 37 |

## Largest Factions

| Faction | Units |
| --- | ---: |
| Imperium - Adeptus Astartes - Space Marines | 240 |
| Aeldari - Aeldari Library | 175 |
| Imperium - Astra Militarum - Library | 163 |
| Chaos - Chaos Space Marines | 142 |
| Xenos - Orks | 134 |
| Imperium - Agents of the Imperium | 104 |
| Xenos - T'au Empire | 99 |
| Imperium - Adeptus Astartes - Space Wolves | 76 |
| Chaos - Daemons Library | 74 |
| Xenos - Necrons | 70 |
| Xenos - Tyranids | 57 |
| Chaos - Death Guard | 54 |

## Source Catalogue Coverage

| Source File | Factions | Units | Weapons | Suspicious Weapons | Loadout Rows |
| --- | --- | ---: | ---: | ---: | ---: |
| [Imperium - Space Marines.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Imperium%20-%20Space%20Marines.cat) | Imperium - Adeptus Astartes - Space Marines | 240 | 2125 | 0 | 55 |
| [Aeldari - Aeldari Library.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Aeldari%20-%20Aeldari%20Library.cat) | Aeldari - Aeldari Library | 175 | 828 | 1 | 23 |
| [Imperium - Astra Militarum - Library.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Imperium%20-%20Astra%20Militarum%20-%20Library.cat) | Imperium - Astra Militarum - Library | 163 | 906 | 4 | 40 |
| [Chaos - Chaos Space Marines.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Chaos%20-%20Chaos%20Space%20Marines.cat) | Chaos - Chaos Space Marines | 142 | 630 | 0 | 24 |
| [Orks.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Orks.cat) | Xenos - Orks | 134 | 595 | 7 | 10 |
| [Imperium - Agents of the Imperium.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Imperium%20-%20Agents%20of%20the%20Imperium.cat) | Imperium - Agents of the Imperium | 104 | 615 | 0 | 22 |
| [T'au Empire.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/T%27au%20Empire.cat) | Xenos - T'au Empire | 99 | 577 | 10 | 22 |
| [Imperium - Space Wolves.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Imperium%20-%20Space%20Wolves.cat) | Imperium - Adeptus Astartes - Space Wolves | 76 | 205 | 0 | 15 |
| [Chaos - Chaos Daemons Library.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Chaos%20-%20Chaos%20Daemons%20Library.cat) | Chaos - Daemons Library | 74 | 242 | 0 | 3 |
| [Necrons.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Necrons.cat) | Xenos - Necrons | 70 | 250 | 5 | 3 |
| [Tyranids.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Tyranids.cat) | Xenos - Tyranids | 57 | 137 | 1 | 2 |
| [Chaos - Death Guard.cat](https://github.com/BSData/wh40k-10e/blob/32b4525d9f69f062f3458d517c6cf82512ef6fef/Chaos%20-%20Death%20Guard.cat) | Chaos - Death Guard | 54 | 341 | 0 | 12 |

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

## Derived Ability Modifiers

| Modifier Type | Rows |
| --- | ---: |
| attack_modifier | 356 |
| damage_reduction | 14 |

## Duplicate Unit Names

| Unit Name | Variants |
| --- | ---: |
| Chaos Spawn | 6 |
| Chaos Land Raider | 5 |
| Chaos Rhino | 5 |
| Defiler | 5 |
| Boss Nob | 4 |
| Chaos Predator Annihilator | 4 |
| Chaos Predator Destructor | 4 |
| Fiends | 4 |
| Helbrute | 4 |
| Heldrake | 4 |
| Hell Talon [Legends] | 4 |
| Hellblade [Legends] | 4 |

## Unit Weapon Coverage

| Coverage | Units |
| --- | ---: |
| both | 1767 |
| melee_only | 248 |
| no_weapons | 19 |
| ranged_only | 59 |

## Loadout Review Reasons

| Reason | Rows |
| --- | ---: |
| mixed loadout profiles | 343 |
| many imported weapon profiles | 151 |
| many ranged profiles | 109 |
| many melee profiles | 50 |
