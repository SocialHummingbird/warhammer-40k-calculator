# Warhammer 40K Damage Calculator

## Overview
This project estimates the expected damage exchange between two Warhammer 40,000 units. It reads unit and weapon profiles, resolves hit/wound/save probabilities, and reports average unsaved wounds, damage, models destroyed, estimated points removed, and a matchup judgement in each direction.

Key features:
- Deterministic calculator for ranged or melee engagements using expected values.
- Flexible dice parser that understands fixed values and expressions such as `D6`, `2D3+3`, etc.
- Import pipeline for BattleScribe/BSData catalogues so you can stay up to date with community data.
- Local HTML interface with attacker/defender weapon filters, weapon count multipliers, points-removed estimates, and generated matchup judgement.
- Reference generator that summarises all keywords and abilities found in an imported roster.

## Requirements
- Python 3.11 or newer.
- PowerShell (all examples below use `pwsh`).
- Optional: `pypdf` when extracting the official Warhammer 40,000 base-size guide PDF into CSV.
- No third-party Python dependencies are required.

## Setup (PowerShell)
```powershell
# Optional: create & activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Quick start with bundled data
These commands use the curated `units.json` file that ships with the project.

```powershell
# List available units
python main.py --list-units

# Calculate expected ranged damage from Space Marine Intercessors into Ork Boyz
python main.py --attacker "Space Marine Intercessor" --defender "Ork Boy" --mode ranged

# Calculate expected melee damage the other way around
python main.py --attacker "Ork Boy" --defender "Space Marine Intercessor" --mode melee
```

## Local web UI

### Standalone local HTML

Open `warhammer_calculator_local.html` directly, or double-click `open_local_html.bat`. This file embeds the imported unit data, audit report, update report, profile review summary, import diff, suspicious weapon summary, and browser-side calculator logic, so it does not need the local Python web server. Use the Data Review button to inspect the latest update summary, profile coverage, suspicious weapon categories, audit findings, and update diff in the browser.

The web UI preserves importer unit IDs and shows each selected unit and weapon's BSData source file, so duplicate unit names from different factions or variants remain selectable and auditable instead of being collapsed into one name.

To refresh the BSData checkout, rebuild all generated files, and open the standalone HTML in one step, double-click `update_and_open_local_html.bat` or run:

```powershell
.\update_and_open_local_html.ps1
.\update_and_open_local_html.ps1 -FailOnReviewIssues
.\update_and_open_local_html.ps1 -FailOnReviewIssues -MaxSuspiciousWeaponWarnings 18 -MaxLoadoutWarnings 143 -MaxNoWeaponUnits 16
.\update_and_open_local_html.ps1 -FailOnReviewIssues -ReviewThresholds config\review_thresholds_10e.json
.\update_and_open_local_html.ps1 -WriteReviewThresholds config\review_thresholds_10e.json
.\update_and_open_local_html.ps1 -MlModelType logistic_regression -MlLabels data\ml\10e\real_matchup_labels.csv
```

Regenerate it after refreshing `data\10e\latest`:

```powershell
python export_local_html.py --csv-dir data\10e\latest
```

To smoke-test the generated HTML in headless Chrome or Edge and compare its calculator output against the Python calculator, including selected weapons, multipliers, and engagement context:

```powershell
python -m pytest tests\test_local_html_smoke.py
```

The smoke test skips automatically when no compatible browser or generated HTML file is available.

### Local Python server

Run the browser front end from the project root:

```powershell
python -m warhammer.webapp --csv-dir data\10e\latest --port 8765
```

On Windows you can also run `run_web_ui.bat` from the project folder.

Then open `http://127.0.0.1:8765/`. The server loads units once at startup and serves a zero-dependency HTML interface for attacker/defender matchups, per-side faction-filtered unit search, ranged or melee mode, optional per-side weapon selection and weapon count multipliers, estimated points removed, generated matchup judgement, and separate engagement context for the attacker attack and return strike.

The local server also exposes the latest generated data review at `http://127.0.0.1:8765/api/data-review`, including `update_report.md` and `profile_review.md`, which powers the same Data Review button used by the standalone HTML.

To run the server with a non-default advisory model, pass `--model` through the module or PowerShell launcher:

```powershell
python -m warhammer.webapp --csv-dir data\10e\latest --model models\10e\matchup_logistic_model.json
.\run_web_ui.ps1 --model models\10e\matchup_logistic_model.json
```

## Importing units from BSData catalogues
1. Retrieve the Warhammer 40,000 BSData repository (for example, by cloning `https://github.com/BSData/wh40k-10e` or letting the importer download it on demand with `python import_bsdata.py --github-repo BSData/wh40k-10e --output data\10e\latest --edition 10e`).
2. Run the importer to convert catalogues into CSV extracts:
   ```powershell
   python import_bsdata.py "C:\path\to\wh40k-10e" --output data\10e\latest --edition 10e
   ```
   The script emits `units.csv`, `weapons.csv`, `abilities.csv`, `keywords.csv`, and `unit_keywords.csv` under `data\10e\latest`.
3. Point the calculator at the generated CSVs:
   ```powershell
   python main.py --csv-dir data\10e\latest --list-units
   python main.py --csv-dir data\10e\latest --attacker "Intercessor Squad" --defender "Necron Warrior" --mode ranged
   ```

Tip: Use `--github-ref` to pin to a specific release tag and `--github-subdir` if you only need a single faction folder (for example `--github-subdir "Imperium - Adeptus Custodes.cat"`).

### One-command database refresh

When `data\wh40k-10e` is a local Git checkout, refresh the whole generated database with:

```powershell
python update_database.py
```

The updater fast-forwards the BSData checkout from `https://github.com/BSData/wh40k-10e.git`, regenerates `data\10e\latest`, writes `audit_report.json`, `schema_review.csv`, `edition_status.json`, `edition_readiness.md`, `import_diff.json`, joined profile review files, official base-size footprint artifacts, and a readable `update_report.md`, refreshes the ML feature CSV/model/audit under `data\ml\10e` and `models\10e`, records linked ML artifact hashes in `artifact_manifest.json`, stores a commit-keyed snapshot under `data\10e\snapshots`, rebuilds `warhammer_calculator_local.html`, and mirrors artifacts to `data\latest` for older commands. Use `--skip-ml` to leave existing ML artifacts untouched during a data-only refresh, `--ml-model-type logistic_regression` to have the update pipeline train and embed the optional logistic advisory model, `--ml-labels data\ml\10e\real_matchup_labels.csv` to train and compare advisory models against curated labels, or `--fail-on-review-issues` to make the update exit non-zero when generated artifacts, schema, edition readiness, or error-severity audit rows fail the data review gate. Add `--review-fail-on-warnings` when you want warning rows to block the refresh too, `--review-thresholds config\review_thresholds_10e.json` to use the current accepted warning baseline, `--write-review-thresholds config\review_thresholds_10e.json` to write a new accepted baseline after a successful refresh, or threshold flags such as `--max-suspicious-weapon-warnings`, `--max-loadout-warnings`, and `--max-no-weapon-units` when existing warning rows are accepted but growth should fail the update.

Generated metadata records the active rules edition. The current supported value is `10e`; pass `--edition 10e` explicitly when scripting updates that will later coexist with additional edition snapshots. The server discovers `data\<edition>\latest` folders, reports them through `/api/health`, and routes unit search, unit detail, data review, review downloads, and calculations through the selected edition when a matching ruleset exists. If data exists for an edition whose ruleset is not implemented, the server reports it as blocked instead of silently hiding it. Each supported ruleset also publishes machine-readable capability coverage in `edition_status.json` and `/api/health.rulesets`, so future edition work can compare implemented mechanics such as hit rolls, wound rolls, saves, damage handling, and model removal before calculations are enabled. The standalone HTML remains a single embedded dataset but shows the edition used for that export.

Matchup calculations are routed through `warhammer.matchups`, a reusable service layer shared by the web API and intended for future ML dataset export. Matchup payload formatting and AI judgement text live in `warhammer.matchup_payloads`, and the webapp now uses that module directly for unit and result serialization. Generated review artifacts, review downloads, and model download path parsing are loaded through `warhammer.data_review`, keeping audit/report parsing separate from HTTP routing. Edition discovery and readiness rows live in `warhammer.editions`, while loaded web datasets, default data paths, and ML model state live in `warhammer.web_state`. API payload parsing lives in `warhammer.api_payloads`, web calculate-request handling lives in `warhammer.web_calculation`, web API response payload and download-target selection live in `warhammer.web_api`, unit filtering lives in `warhammer.unit_search`, ability modifier collection lives in `warhammer.ability_resolver`, engagement state lives in `warhammer.context`, result dataclasses/scaling live in `warhammer.results`, and single-weapon orchestration lives in `warhammer.weapon_resolution`. The webapp routes to those modules directly instead of maintaining duplicate private helper proxies. `warhammer.calculator` remains the public compatibility API for callers. Edition-specific combat behavior lives behind `warhammer.rules`; the current `10e` ruleset owns hit rolls, hit rerolls, Lethal Hits, Sustained Hits, wound rolls, Anti critical wounds, Devastating Wounds pool splitting, modifier caps, advance firing, Rapid Fire, Blast, Heavy, Assault, cover/save resolution, FNP, expected damage, model removal, melta, and damage handling. Keep new advisory or prediction code behind these service layers so the deterministic rules engine and generated audit files remain the source of truth.

## ML feature export

The project can export deterministic matchup feature rows for future advisory machine-learning models. This does not train a model and does not replace the rules calculator; labels such as `winner_label`, `confidence`, and `edge` are generated from the current deterministic calculator outputs and are marked with `label_source=deterministic_calculator`.

```powershell
python export_ml_features.py --csv-dir data\10e\latest --output data\ml\10e\matchup_training_rows.csv --edition 10e --max-rows 10000 --strategy sample --seed 40
```

Use `--modes ranged,melee` to control included attack modes. The default `sample` strategy uses a stable seed to cover more of the database when a row cap is set; use `--strategy sequential --max-rows 0` to export every generated pair. Treat the resulting CSV as synthetic calculator-derived training data, not real-world tournament win-rate data.

Train the dependency-free baseline advisory model with:

```powershell
python train_ml_model.py --features data\ml\10e\matchup_training_rows.csv --output models\10e\matchup_centroid_model.json
```

By default the trainer uses `--feature-set pre_match`, which includes unit/profile inputs and same-mode weapon aggregates such as attacks, skill, strength, AP, damage, keyword count, and special rule count, while excluding calculator output metrics such as expected damage and points removed. Use `--feature-set full` only when you intentionally want a comparison model that can see those deterministic calculator outputs.

The default model type is the dependency-free nearest-centroid baseline. If `scikit-learn` is installed, you can train an optional stronger JSON-serialised logistic-regression advisory model without adding runtime dependencies to the web app or standalone HTML:

```powershell
python train_ml_model.py --model-type logistic_regression --features data\ml\10e\matchup_training_rows.csv --output models\10e\matchup_logistic_model.json --report models\10e\matchup_logistic_model.md
```

If you have curated or real-world matchup labels, pass them as an external labels CSV instead of relying only on calculator-derived labels. By default, labels are matched on `edition`, `mode`, `attacker_id`, and `defender_id`, and the label file must contain `winner_label` or `label`:

```powershell
python train_ml_model.py --features data\ml\10e\matchup_training_rows.csv --labels data\ml\10e\real_matchup_labels.csv --output models\10e\matchup_real_label_model.json
```

Use `--label-key-columns` when your label file uses a different matchup key. The generated model JSON and Markdown audit record the label override file, row count, matched rows, skipped rows, and whether labels came from external data.

The full data update pipeline can train and embed that optional model in one run:

```powershell
python update_database.py --ml-model-type logistic_regression
python update_database.py --ml-labels data\ml\10e\real_matchup_labels.csv --ml-label-key-columns edition mode attacker_id defender_id
```

To compare available model families on the same feature CSV without writing or replacing model artifacts:

```powershell
python compare_ml_models.py --features data\ml\10e\matchup_training_rows.csv
python compare_ml_models.py --features data\ml\10e\matchup_training_rows.csv --labels data\ml\10e\real_matchup_labels.csv
```

Database updates also write this comparison to `models\10e\model_comparison.md` and expose it in Data Review with the model audit downloads.

To embed a non-default model in the standalone HTML, pass it to the exporter:

```powershell
python export_local_html.py --csv-dir data\10e\latest --model models\10e\matchup_logistic_model.json
```

Training also stores feature CSV provenance in the model JSON, including feature row count, byte size, and SHA-256 hash. It also writes `models\10e\matchup_centroid_model.md`, a Markdown audit report with model type, feature set, label source, saved feature hash, class balance, validation confusion matrix, feature columns, and a warning when calculator output metrics are used as features. The Data Review view includes this report and download links for the model audit/JSON alongside the database audit files. To audit an existing model without retraining:

```powershell
python audit_ml_model.py --model models\10e\matchup_centroid_model.json --features data\ml\10e\matchup_training_rows.csv
```

Verify that the current feature CSV still matches the model's saved training provenance:

```powershell
python verify_ml_artifacts.py --features data\ml\10e\matchup_training_rows.csv --model models\10e\matchup_centroid_model.json
```

When `models\<edition>\matchup_centroid_model.json` exists, the local web API reports model status through `/api/health` and attaches a separate `ml_judgement` object to `/api/calculate` responses. The UI status bar shows the loaded model's validation accuracy, and results render the ML advisory beneath the deterministic rules judgement. `export_local_html.py` embeds the same small model JSON into `warhammer_calculator_local.html`, so the standalone file can show the advisory without a Python server.

For a compact terminal summary of the generated review artifacts, run:

```powershell
python data_review_summary.py --data-dir data\10e\latest
python data_review_summary.py --data-dir data\10e\latest --fail-on-issues
python data_review_summary.py --data-dir data\10e\latest --fail-on-issues --max-suspicious-weapon-warnings 18 --max-loadout-warnings 143 --max-no-weapon-units 16
python data_review_summary.py --data-dir data\10e\latest --fail-on-issues --thresholds config\review_thresholds_10e.json
python data_review_summary.py --data-dir data\10e\latest --write-thresholds config\review_thresholds_10e.json
```

For manual data review, open:

- `data\10e\latest\weapon_profile_review.csv` for every imported weapon joined to unit name, faction, source file, points, model count, parsed averages, parse status, and raw damage throughput.
- `data\10e\latest\suspicious_weapon_review.csv` for missing, unparsable, zero, or extreme weapon characteristics, with severity and category columns for manual review.
- `data\10e\latest\unit_profile_review.csv` for every imported unit with core stat, points, and model-count validation columns.
- `data\10e\latest\ability_profile_review.csv` for every imported ability joined to unit name, faction, and source file where applicable.
- `data\10e\latest\ability_modifier_review.csv` for derived ability effects that the calculator applies during matchup math.
- `data\10e\latest\unit_variant_review.csv` for duplicate-name unit rows with their unit IDs, factions, source files, points, and model counts.
- `data\10e\latest\unit_weapon_coverage_review.csv` for each unit's ranged/melee weapon counts and coverage category.
- `data\10e\latest\base_size_guide.csv` for extracted rows from the official January 2026 Base Size Guide.
- `data\10e\latest\unit_footprint_overrides.csv` for reviewable local footprint aliases or manual corrections that cannot be matched safely by name.
- `data\10e\latest\unit_footprint_rejections.csv` for reviewed footprint suggestions that should not be resurfaced as candidate matches.
- `data\10e\latest\unit_footprint_override_template.csv` for unmatched units prefilled with unit IDs and top suggestion context, ready for manual override research.
- `data\10e\latest\unit_footprint_review_queue.csv` for the same unmatched units sorted into a prioritized manual review queue.
- `data\10e\latest\unit_footprints.csv` for imported units joined to official base sizes, used by Battlefield blob sizing where a numeric base is available.
- `data\10e\latest\unit_footprint_review.csv` for unmatched, mixed-base, non-numeric-base, and faction-ambiguous footprint rows that need manual review.
- `data\10e\latest\unit_footprint_review.md` for a human-readable footprint triage report with status counts, high-confidence suggestions, and override workflow commands.
- `data\10e\latest\unit_footprint_suggestions.csv` for non-authoritative candidate official guide rows that can speed up manual footprint override review.
- `data\10e\latest\loadout_review.csv` for units with many imported weapon profiles where all-weapons calculations may need specific loadout selection.
- `data\10e\latest\source_catalogue_review.csv` for per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.
- `data\10e\latest\schema_review.csv` for required versus actual generated CSV columns.
- `data\10e\latest\edition_status.json` for ruleset availability, calculation readiness, blockers, source commit, row counts, and audit summary.
- `data\10e\latest\edition_readiness.md` for a readable compatibility report and migration checklist for future edition support.
- `data\10e\latest\artifact_manifest.json` for file sizes and SHA-256 hashes of generated artifacts and linked ML artifacts.
- `data\10e\latest\profile_review.md` for a short summary of imported profile coverage.

After reviewing high-confidence footprint suggestions, promote them into the manual override layer with a dry run first:

```powershell
python footprint_review_report.py --data-dir data\10e\latest
python accept_footprint_suggestions.py --min-score 0.9
python accept_footprint_suggestions.py --min-score 0.9 --apply
python reject_footprint_suggestions.py --min-score 0.8 --unit-id <unit-id> --apply
python plan_footprint_review.py --limit 50 --output data\10e\latest\unit_footprint_review_queue.csv
python promote_footprint_override_template.py --template data\10e\latest\unit_footprint_override_template.csv
python promote_footprint_override_template.py --template data\10e\latest\unit_footprint_override_template.csv --apply
python promote_footprint_override_template.py --queue data\10e\latest\unit_footprint_review_queue.csv
python promote_footprint_override_template.py --queue data\10e\latest\unit_footprint_review_queue.csv --apply
python update_database.py --skip-fetch --skip-ml
```

In `unit_footprint_override_template.csv`, leave uncertain rows blank. Set `review_decision` to
`accept_suggestion` to promote the prefilled official-guide suggestion, or `override` after filling the
`override_*` fields for a researched manual base-size row. The promotion script reports suggestion-ready,
manual override-ready, invalid, blank, skipped, and already-overridden rows before it writes anything.
Those same counts are visible in the Data Review screen as “Footprint Override Template Status”.
Data Review also renders “Footprint Review Queue” with the priority counts and first rows from
`unit_footprint_review_queue.csv`, and the Markdown footprint report includes the same prioritized
manual-review batch with suggested reviewer actions. The CLI data review summary and release verification output also
print the footprint review queue distribution so manual base-size audit debt is visible without opening
the browser.

Battlefield blob sizing uses official numeric base dimensions when available. Official guide rows that say only `Small Flying Base`, `Large Flying Base`, `Hull`, or `Unique` use explicit derived planning footprints in the UI, so they remain auditable instead of being treated as unknown generic blobs.

Verify generated artifacts, linked ML artifact hashes, and linked ML training provenance against their manifest with:

```powershell
python verify_artifacts.py --data-dir data\10e\latest
python verify_artifacts.py --data-dir data\10e\snapshots\32b4525d9f69
```

Run the full local release verification set with:

```powershell
python verify_release.py
.\verify_release.ps1
```

## Generating keyword & ability references
Create a Markdown cheat sheet listing every keyword and ability plus the units that use them.

```powershell
# Print the reference to the console
python main.py --csv-dir data\10e\latest --reference -

# Write the reference to a Markdown file
python main.py --csv-dir data\10e\latest --reference data\10e\latest\references.md
```

Prefer a standalone script? `python export_reference.py --csv-dir data\10e\latest --output data\10e\latest\references.md` produces the same Markdown output.

## Advanced usage tips
- Prefer `data\10e\latest` for current generated data. `data\latest` is still mirrored for older commands, but edition-scoped paths make future 11th-edition data safer to keep beside 10th edition.
- `main.py` accepts `--mode melee` or `--mode ranged` for direct attacker-versus-defender calculations. CLI calls use default engagement context: stationary attacker, no cover, no half-range bonus unless a rule is profile-driven.
- When using `--csv-dir`, the calculator consumes importer CSV output directly. Keep generated columns such as `keywords`, `reroll_hits`, `reroll_wounds`, `lethal_hits`, `sustained_hits`, `devastating_wounds`, `feel_no_pain`, `damage_cap`, ability text, unit IDs, points, and model counts so rules, duplicate unit selection, points removed, and audit views stay connected.
- Advanced 10th-edition rules such as Heavy, Assault, Rapid Fire, Blast, Ignores Cover, Melta, Anti, Twin-linked, Lethal Hits, Sustained Hits, Devastating Wounds, Feel No Pain, and damage reduction are resolved through the `10e` ruleset. Movement, half-range, cover, and target model count need engagement context when you use the Python API or `/api/calculate`.
- `preset_matchups.py` wraps the source-backed CLI for preset target tables and duels. Combine `--preset`, `--weapon-mode`, `--seed`, and `--csv-dir` to control tables, pair `--attacker` with `--defender` for a single duel, and use `--scenario realistic` with `--explain` when you want AI commentary to consider positioning. Use `--random-fair-duel` with `--max-point-delta` to auto-pair similar single-model units.
- The local web server and standalone HTML are usually better for repeated manual review because they expose unit IDs, faction filtering, weapon filters, model multipliers, deterministic judgement, ML advisory output, and Data Review links.

Direct CLI examples:

```powershell
python main.py --csv-dir data\10e\latest --attacker "Intercessor Squad" --defender "Boyz" --mode ranged
python main.py --csv-dir data\10e\latest --attacker "Boyz" --defender "Intercessor Squad" --mode melee
```

Python API example with explicit engagement context:

```powershell
python -c "from pathlib import Path; from warhammer.datasheet import load_units_from_csv; from warhammer.calculator import EngagementContext, evaluate_unit; units = load_units_from_csv(Path('data/10e/latest')); attacker = units['Garran Branatar']; defender = units['Rhino']; context = EngagementContext(attacker_moved=True, attacker_advanced=True, target_within_half_range=True, target_in_cover=True, target_model_count=1); result = evaluate_unit(attacker, defender, 'ranged', context=context, edition='10e'); print(f'{attacker.name} vs {defender.name} expected damage: {result.total_damage:.2f}; models destroyed: {result.expected_models_destroyed:.2f}')"
```

Preset and duel examples:

```powershell
python preset_matchups.py --csv-dir data\10e\latest --attacker "Garran Branatar" --preset vehicles --preset monsters --weapon-mode all
python preset_matchups.py --csv-dir data\10e\latest --attacker "Bladeguard Veteran Squad" --defender "Custodian Wardens" --weapon-mode melee --explain --scenario realistic
python preset_matchups.py --csv-dir data\10e\latest --random-fair-duel --fair-require-both --weapon-mode all --max-point-delta 40 --explain --scenario realistic
```

Local server API example:

```powershell
python -m warhammer.webapp --csv-dir data\10e\latest --port 8765

$body = @{
  edition = "10e"
  attacker = "Intercessor Squad"
  defender = "Boyz"
  mode = "ranged"
  outgoing_context = @{ attacker_moved = $true; target_in_cover = $true }
  incoming_context = @{ attacker_moved = $false }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/calculate -Body $body -ContentType "application/json"
```

Data and ML audit examples:

```powershell
python verify_artifacts.py --data-dir data\10e\latest
python verify_ml_artifacts.py --features data\ml\10e\matchup_training_rows.csv --model models\10e\matchup_centroid_model.json
python main.py --rulesets
python main.py --rulesets-json
python datasheet.py --csv-dir data\10e\latest --unit "Intercessor Squad"
```

## Directory recap
- `main.py` - CLI damage calculator.
- `import_bsdata.py` - BSData catalogue importer that emits CSV tables.
- `export_reference.py` - Markdown reference generator for keywords and abilities.
- `warhammer/` - Package containing the dice parser, profile models, calculator, importer helpers, and reference utilities.

## Support & contributions
This repository is intended for hobby and educational purposes. Feel free to fork the project and tailor it to your army. If you extend the rules engine or importer, document the changes in `CHANGELOG.md` and update this README so PowerShell users know which commands to run.


## Datasheet inspection

Quickly confirm that imported data is parsed correctly:

```powershell
# Print a specific unit datasheet
python datasheet.py --csv-dir data\10e\latest --unit "Intercessor Squad"

# Pick a random unit and print its datasheet
python -c "import random; from pathlib import Path; from warhammer.datasheet import load_units_from_csv, print_unit_datasheet; units = load_units_from_csv(Path('data/10e/latest')); unit = random.choice(list(units.values())); print(f'Random unit selected: {unit.name}'); print_unit_datasheet(unit)"
```

Use `--include-crusade` if you want the CLI to show Crusade battle scars and upgrades.


## Matchups vs preset targets

Run a quick matchup by picking a random attacker and comparing it against keyword-driven defender tables.

Each table now includes a weapon profile column, so you can see attacks, skill, strength, AP, damage, and standout keywords for every weapon alongside the defender statistics. Profiles use short codes such as ASLT (Assault), RF2 (Rapid Fire 2), TL (Twin-linked), and DVW (Devastating Wounds) to keep the column compact.

Preset tables:

| Label | Required keywords |
| --- | --- |
| Core Infantry | core, infantry |
| Elite Infantry | infantry |
| Vehicle | vehicle |
| Monster | monster |
| Character | character |

Commands:

```powershell
# Random attacker vs every preset (uses importer CSV output)
python main.py --csv-dir data/10e/latest --weapon-tables-all-presets-random --weapon-mode all --ppm-basis average

# Lock to a specific attacker and melee weapons only
python main.py --csv-dir data/10e/latest --attacker "Garran Branatar" --weapon-tables-all-presets --weapon-mode melee

# Export the tables to Markdown for later reference
python main.py --csv-dir data/10e/latest --attacker "Garran Branatar" --weapon-tables-all-presets --weapon-mode all --export-table data/10e/latest/garran-vs-presets.md --export-format md

# Optional helper: focus on selected presets through the wrapper
python preset_matchups.py --csv-dir data/10e/latest --attacker "Garran Branatar" --preset vehicles --preset monsters

# Discover available presets without running calculations
python preset_matchups.py --list-presets

# Ask the AI for a preset rundown (Bladeguard)
python preset_matchups.py --csv-dir data/10e/latest --attacker "Bladeguard Veteran Squad" --preset elite --weapon-mode melee --explain --scenario realistic

# Ask the AI for a preset rundown (Wardens)
python preset_matchups.py --csv-dir data/10e/latest --attacker "Custodian Wardens" --preset elite --weapon-mode melee --explain --scenario realistic

# Random two-unit duel (tables only)
python -c "import random, subprocess; from pathlib import Path; from warhammer.datasheet import load_units_from_csv; units = load_units_from_csv(Path('data/10e/latest'));
eligible = [u for u in units.values() if getattr(u, 'points', 0) and any(getattr(w, 'type', '').lower() == 'melee' for w in getattr(u, 'weapons', []))];
if len(eligible) < 2: raise SystemExit('Not enough melee-capable units with points to sample.');
attacker = random.choice(eligible);
defenders = [u for u in eligible if u is not attacker];
defender = random.choice(defenders);
print(f'Selected attacker: {attacker.name} ({attacker.points} pts)');
print(f'Selected defender: {defender.name} ({defender.points} pts)');
subprocess.run(['python', 'preset_matchups.py', '--csv-dir', 'data/10e/latest', '--attacker', attacker.name, '--defender', defender.name, '--weapon-mode', 'melee'], check=False)"

# Two-unit duel (tables only)
python preset_matchups.py --csv-dir data/10e/latest --attacker "Bladeguard Veteran Squad" --defender "Custodian Wardens" --weapon-mode melee

# Random fair duel (single-model, similar points, melee + ranged)
python preset_matchups.py --csv-dir data/10e/latest --random-fair-duel --fair-require-both --weapon-mode all --max-point-delta 40 --explain --scenario realistic

# Random two-unit duel with AI commentary
python -c "import random, subprocess; from pathlib import Path; from warhammer.datasheet import load_units_from_csv; units = load_units_from_csv(Path('data/10e/latest'));
eligible = [u for u in units.values() if getattr(u, 'points', 0) and any(getattr(w, 'type', '').lower() == 'melee' for w in getattr(u, 'weapons', []))];
if len(eligible) < 2: raise SystemExit('Not enough melee-capable units with points to sample.');
attacker = random.choice(eligible);
defenders = [u for u in eligible if u is not attacker];
defender = random.choice(defenders);
print(f'Selected attacker: {attacker.name} ({attacker.points} pts)');
print(f'Selected defender: {defender.name} ({defender.points} pts)');
subprocess.run(['python', 'preset_matchups.py', '--csv-dir', 'data/10e/latest', '--attacker', attacker.name, '--defender', defender.name, '--weapon-mode', 'melee', '--explain', '--scenario', 'realistic'], check=False)"

# Direct duel with AI commentary
python preset_matchups.py --csv-dir data/10e/latest --attacker "Bladeguard Veteran Squad" --defender "Custodian Wardens" --weapon-mode melee --explain --scenario realistic
```

The helper flags defenders with >=10" Move or Advance+Charge when you run preset tables so fast targets stand out immediately.

These commands delegate to the source-backed CLI that already understands engagement context, weapon keywords, and points-per-model math.

The `--random-fair-duel` flag narrows the pool to single-model units that share battlefield keywords, have weapons for the requested `--weapon-mode`, and fall within the configurable `--max-point-delta` (set a negative delta to ignore points entirely).

Enable `--explain` once your ChatGPT API key is available (the helper reuses the same loader as `ai_clean.py`). Override the default `gpt-5-mini` model with `--explain-model` if you want a different tone or latency trade-off. Pair `--attacker` with `--defender` for a head-to-head duel without presets, and add `--scenario realistic` (or your own prompt) when you want the AI to discuss closing distance, potential kiting, and other engagement nuance.

### AI-assisted data checks

If you want an AI pass over the importer outputs, install the optional dependency and expose your API key:

```powershell
pip install openai  # Optional helper depends on the OpenAI client
# Store your API key in credentials/ai_key.txt (first non-comment line)
```

Run the helper to review the latest CSV exports:

```powershell
# Collects heuristic stats and lets the model flag questionable rows
python ai_clean.py --csv-dir data/10e/latest

# Skip the model call and only print the heuristics
python ai_clean.py --csv-dir data/10e/latest --summary-only
```

The script summarises missing values, duplicate names, and other quick checks before handing the report to the model you specify (default: `gpt-5-mini`).

Store your API key in a file rather than hard-coding it:

- Create `%USERPROFILE%\.warhammer_ai_key` (or `credentials/ai_key.txt` inside the repo) and place the key on the first non-comment line (lines starting with `#` are ignored).
- Optional: point to a different location with `WARHAMMER_AI_KEY_FILE` or continue using `WARHAMMER_AI_API_KEY`/`OPENAI_API_KEY` if you prefer environment variables.

The helper in `preset_matchups.py` simply reuses that engine for convenience when you want to focus on a subset of presets or discover the available defender tables.

### Data completeness audit

Run the audit whenever you refresh the importer output to see which units still need manual points/min/max data and to catch suspicious weapon/profile rows, such as placeholder damage, invalid Strength/AP values, orphaned weapon links, duplicate profile IDs, and duplicate mappings:

```powershell
python audit_import.py --csv-dir data/10e/latest
```

Write the same results to JSON for review tooling or the web UI:

```powershell
python audit_import.py --csv-dir data/10e/latest --json-report data/10e/latest/audit_report.json
```

Use `--fail-on-issues` when you want a CI-style non-zero exit code:

```powershell
python audit_import.py --csv-dir data/10e/latest --fail-on-issues
```

This helper only uses the exported CSVs, so it behaves just like the AI checker but without requiring an API key. The latest generation timestamp and source path are stored in `data/10e/latest/metadata.json`.

For a human-readable update summary, open `data/10e/latest/update_report.md`. It includes the source BSData commit, audit status, row counts, import diff counts, and any review-gate thresholds applied during the refresh, and it is also copied into each `data/10e/snapshots/<commit>` folder.











