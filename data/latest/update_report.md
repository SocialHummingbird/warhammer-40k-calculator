# Warhammer Data Update Report

Generated: 2026-04-28T07:00:53.681245Z
Source: https://github.com/BSData/wh40k-10e.git
Branch: main
Commit: 1228d35e79bcf02a5e70ec94e422b7ffce4f980e -> 1228d35e79bcf02a5e70ec94e422b7ffce4f980e
Commit date: 2026-04-28 00:10:49 +0100
Commit subject: Armageddon Faction Pack update
Commit URL: https://github.com/BSData/wh40k-10e/commit/1228d35e79bcf02a5e70ec94e422b7ffce4f980e

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
| units | 1471 |
| weapons | 8655 |
| abilities | 3143 |
| keywords | 1413 |
| unit_keywords | 9576 |

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
- `edition_readiness.md`: readable edition compatibility and migration checklist.
- `artifact_manifest.json`: file sizes and SHA-256 hashes for generated data artifacts.
- `schema_review.csv`: required versus actual importer CSV columns for schema auditing.

## Import Diff

| Table | Before | After | Delta | Added | Removed | Changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| units | 1471 | 1471 | +0 | 0 | 0 | 0 |
| weapons | 8655 | 8655 | +0 | 0 | 0 | 0 |
| abilities | 3143 | 3143 | +0 | 0 | 0 | 0 |
| keywords | 1413 | 1413 | +0 | 0 | 0 | 0 |
| unit_keywords | 9576 | 9576 | +0 | 0 | 0 | 0 |
