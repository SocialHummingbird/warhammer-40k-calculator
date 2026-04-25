# Warhammer Data Update Report

Generated: 2026-04-25T18:21:29.465187Z
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
| units | 2093 |
| weapons | 10808 |
| abilities | 3173 |
| keywords | 1425 |
| unit_keywords | 9644 |

## Manual Review Files

- `profile_review.md`: summary of imported profile counts and largest factions.
- `weapon_profile_review.csv`: every imported weapon profile joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.
- `suspicious_weapon_review.csv`: zero or extreme parsed weapon damage characteristics for manual review.
- `ability_profile_review.csv`: every imported ability profile joined to unit name, faction, and source file where applicable.
- `ability_modifier_review.csv`: derived ability effects that the calculator applies during matchup math.
- `unit_variant_review.csv`: duplicate-name unit rows joined to IDs, faction context, and source file.
- `unit_weapon_coverage_review.csv`: each unit's ranged/melee weapon counts and coverage category.
- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need loadout selection.
- `source_catalogue_review.csv`: per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.
- `artifact_manifest.json`: file sizes and SHA-256 hashes for generated data artifacts.
- `schema_review.csv`: required versus actual importer CSV columns for schema auditing.

## Import Diff

| Table | Before | After | Delta | Added | Removed | Changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| units | 2093 | 2093 | +0 | 0 | 0 | 0 |
| weapons | 10808 | 10808 | +0 | 0 | 0 | 0 |
| abilities | 3173 | 3173 | +0 | 0 | 0 | 0 |
| keywords | 1425 | 1425 | +0 | 0 | 0 | 0 |
| unit_keywords | 9644 | 9644 | +0 | 0 | 0 | 0 |
