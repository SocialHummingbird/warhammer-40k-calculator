# Warhammer Data Update Report

Generated: 2026-04-26T15:56:14.857608Z
Source: https://github.com/BSData/wh40k-10e.git
Branch: main
Commit: 32b4525d9f69f062f3458d517c6cf82512ef6fef -> 32b4525d9f69f062f3458d517c6cf82512ef6fef
Commit date: 2026-04-21 17:44:59 +0100
Commit subject: Fixes #7066
Commit URL: https://github.com/BSData/wh40k-10e/commit/32b4525d9f69f062f3458d517c6cf82512ef6fef

## Audit

Status: PASS

| Severity | Samples |
| --- | ---: |
| Errors | 0 |
| Warnings | 0 |
| Info | 0 |
| Total | 0 |

No audit issues were reported.

## Current Row Counts

| Table | Rows |
| --- | ---: |
| units | 1464 |
| weapons | 8628 |
| abilities | 3124 |
| keywords | 1407 |
| unit_keywords | 9523 |

## Manual Review Files

- `profile_review.md`: summary of imported profile counts and largest factions.
- `weapon_profile_review.csv`: every imported weapon profile joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.
- `suspicious_weapon_review.csv`: missing, unparsable, zero, or extreme weapon characteristics with severity/category labels for manual review.
- `unit_profile_review.csv`: every imported unit with core stat, points, and model-count validation for manual review.
- `ability_profile_review.csv`: every imported ability profile joined to unit name, faction, and source file where applicable.
- `ability_modifier_review.csv`: derived ability effects that the calculator applies during matchup math.
- `unit_variant_review.csv`: duplicate-name unit rows joined to IDs, faction context, and source file.
- `unit_weapon_coverage_review.csv`: each unit's ranged/melee weapon counts and coverage category.
- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need loadout selection.
- `source_catalogue_review.csv`: per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.
- `edition_status.json`: edition readiness, ruleset availability, source commit, and calculation status.
- `artifact_manifest.json`: file sizes and SHA-256 hashes for generated data artifacts.
- `schema_review.csv`: required versus actual importer CSV columns for schema auditing.

## Import Diff

| Table | Before | After | Delta | Added | Removed | Changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| units | 1479 | 1464 | -15 | 0 | 15 | 0 |
| weapons | 8687 | 8628 | -59 | 0 | 59 | 0 |
| abilities | 3124 | 3124 | +0 | 0 | 0 | 0 |
| keywords | 1407 | 1407 | +0 | 0 | 0 | 0 |
| unit_keywords | 9537 | 9523 | -14 | 0 | 14 | 0 |

### Diff Samples

- units removed: 050d-797a-bb9a-2e8b, 2537-956c-98c0-bffb, 3435-d900-05e9-19e6, 550a-f5c4-d6a9-a09e, 552d-6c0d-80e8-ac32, 77a2-7703-4d4f-f30d, 8778-e3cb-2c6f-b23d, 9516-5ea3-ec42-dcfe, 954d-5938-64d8-597c, 99c8-e37d-ae6d-a8ba, 9ae9-4f7e-a148-cbfa, ab41-fdc1-8d0f-bb74, df47-6883-78e7-d725, e05a-fe00-3df3-d551, f019-5df1-88d5-ddc7
- weapons removed: 050d-797a-bb9a-2e8b:close-combat-weapon, 050d-797a-bb9a-2e8b:combat-knife, 050d-797a-bb9a-2e8b:deathwatch-marksman-bolt-carbine, 050d-797a-bb9a-2e8b:special-issue-bolt-pistol, 2537-956c-98c0-bffb:bolt-pistol, 2537-956c-98c0-bffb:heavy-thunder-hammer, 2537-956c-98c0-bffb:power-weapon, 3435-d900-05e9-19e6:bolt-pistol, 3435-d900-05e9-19e6:close-combat-weapon, 3435-d900-05e9-19e6:stalker-bolt-rifle, 3435-d900-05e9-19e6:➤-plasma-incinerator---standard, 3435-d900-05e9-19e6:➤-plasma-incinerator---supercharge, 550a-f5c4-d6a9-a09e:bolt-pistol, 550a-f5c4-d6a9-a09e:close-combat-weapon, 550a-f5c4-d6a9-a09e:frag-cannon, 550a-f5c4-d6a9-a09e:hellstorm-bolt-rifle, 550a-f5c4-d6a9-a09e:➤-astartes-grenade-launcher---frag, 550a-f5c4-d6a9-a09e:➤-astartes-grenade-launcher---krak, 550a-f5c4-d6a9-a09e:➤-infernus-heavy-bolter---heavy-bolter, 550a-f5c4-d6a9-a09e:➤-infernus-heavy-bolter---heavy-flamer
- unit_keywords removed: 050d-797a-bb9a-2e8b:tacticus, 2537-956c-98c0-bffb:tacticus, 3435-d900-05e9-19e6:tacticus, 550a-f5c4-d6a9-a09e:gravis, 77a2-7703-4d4f-f30d:gravis, 8778-e3cb-2c6f-b23d:tacticus, 9516-5ea3-ec42-dcfe:fly, 9516-5ea3-ec42-dcfe:grenades, 9516-5ea3-ec42-dcfe:imperium, 9516-5ea3-ec42-dcfe:infantry, 9516-5ea3-ec42-dcfe:jump-pack, 9ae9-4f7e-a148-cbfa:tacticus, ab41-fdc1-8d0f-bb74:tacticus, df47-6883-78e7-d725:tacticus
