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

Open `warhammer_calculator_local.html` directly, or double-click `open_local_html.bat`. This file embeds the imported unit data, audit report, update report, profile review summary, import diff, and browser-side calculator logic, so it does not need the local Python web server. Use the Data Review button to inspect the latest update summary, profile coverage, audit findings, and update diff in the browser.

The web UI preserves importer unit IDs and shows each selected unit and weapon's BSData source file, so duplicate unit names from different factions or variants remain selectable and auditable instead of being collapsed into one name.

To refresh the BSData checkout, rebuild all generated files, and open the standalone HTML in one step, double-click `update_and_open_local_html.bat` or run:

```powershell
.\update_and_open_local_html.ps1
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

Then open `http://127.0.0.1:8765/`. The server loads units once at startup and serves a zero-dependency HTML interface for attacker/defender matchups, faction-filtered unit search, ranged or melee mode, optional per-side weapon selection and weapon count multipliers, estimated points removed, generated matchup judgement, and separate engagement context for the attacker attack and return strike.

The local server also exposes the latest generated data review at `http://127.0.0.1:8765/api/data-review`, including `update_report.md` and `profile_review.md`, which powers the same Data Review button used by the standalone HTML.

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

The updater fast-forwards the BSData checkout from `https://github.com/BSData/wh40k-10e.git`, regenerates `data\10e\latest`, writes `audit_report.json`, `schema_review.csv`, `edition_status.json`, `import_diff.json`, joined profile review files, and a readable `update_report.md`, refreshes the ML feature CSV/model/audit under `data\ml\10e` and `models\10e`, stores a commit-keyed snapshot under `data\10e\snapshots`, rebuilds `warhammer_calculator_local.html`, and mirrors artifacts to `data\latest` for older commands. Use `--skip-ml` to leave existing ML artifacts untouched during a data-only refresh.

Generated metadata records the active rules edition. The current supported value is `10e`; pass `--edition 10e` explicitly when scripting updates that will later coexist with additional edition snapshots. The server discovers `data\<edition>\latest` folders, reports them through `/api/health`, and routes unit search, unit detail, data review, review downloads, and calculations through the selected edition when a matching ruleset exists. If data exists for an edition whose ruleset is not implemented, the server reports it as blocked instead of silently hiding it. The standalone HTML remains a single embedded dataset but shows the edition used for that export.

Matchup calculations are routed through `warhammer.matchups`, a reusable service layer shared by the web API compatibility helpers and intended for future ML dataset export. Generated review artifacts are loaded through `warhammer.data_review`, keeping audit/report parsing separate from HTTP routing. Edition discovery and readiness rows live in `warhammer.editions`, so future edition folders can be audited without binding that logic to the web server. API payload parsing lives in `warhammer.api_payloads`, and unit filtering lives in `warhammer.unit_search`. Keep new advisory or prediction code behind these service layers so the deterministic rules engine and generated audit files remain the source of truth.

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

Training also writes `models\10e\matchup_centroid_model.md`, a Markdown audit report with model type, feature set, label source, class balance, validation confusion matrix, feature columns, and a warning when calculator output metrics are used as features. The Data Review view includes this report and download links for the model audit/JSON alongside the database audit files. To audit an existing model without retraining:

```powershell
python audit_ml_model.py --model models\10e\matchup_centroid_model.json --features data\ml\10e\matchup_training_rows.csv
```

When `models\<edition>\matchup_centroid_model.json` exists, the local web API reports model status through `/api/health` and attaches a separate `ml_judgement` object to `/api/calculate` responses. The UI status bar shows the loaded model's validation accuracy, and results render the ML advisory beneath the deterministic rules judgement. `export_local_html.py` embeds the same small model JSON into `warhammer_calculator_local.html`, so the standalone file can show the advisory without a Python server.

For manual data review, open:

- `data\10e\latest\weapon_profile_review.csv` for every imported weapon joined to unit name, faction, source file, points, model count, parsed averages, parse status, and raw damage throughput.
- `data\10e\latest\suspicious_weapon_review.csv` for zero or extreme parsed weapon damage characteristics that deserve manual review.
- `data\10e\latest\ability_profile_review.csv` for every imported ability joined to unit name, faction, and source file where applicable.
- `data\10e\latest\ability_modifier_review.csv` for derived ability effects that the calculator applies during matchup math.
- `data\10e\latest\unit_variant_review.csv` for duplicate-name unit rows with their unit IDs, factions, source files, points, and model counts.
- `data\10e\latest\unit_weapon_coverage_review.csv` for each unit's ranged/melee weapon counts and coverage category.
- `data\10e\latest\loadout_review.csv` for units with many imported weapon profiles where all-weapons calculations may need specific loadout selection.
- `data\10e\latest\source_catalogue_review.csv` for per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.
- `data\10e\latest\schema_review.csv` for required versus actual generated CSV columns.
- `data\10e\latest\edition_status.json` for ruleset availability, calculation readiness, blockers, source commit, row counts, and audit summary.
- `data\10e\latest\artifact_manifest.json` for file sizes and SHA-256 hashes of generated artifacts.
- `data\10e\latest\profile_review.md` for a short summary of imported profile coverage.

Verify generated artifacts against their manifest with:

```powershell
python verify_artifacts.py --data-dir data\10e\latest
python verify_artifacts.py --data-dir data\10e\snapshots\32b4525d9f69
```

## Generating keyword & ability references
Create a Markdown cheat sheet listing every keyword and ability plus the units that use them.

```powershell
# Print the reference to the console
python main.py --csv-dir data\latest --reference -

# Write the reference to a Markdown file
python main.py --csv-dir data\latest --reference data\latest\references.md
```

Prefer a standalone script? `python export_reference.py --csv-dir data\latest --output data\latest\references.md` produces the same Markdown output.

## Advanced usage tips
- `main.py` accepts `--mode melee` or `--mode ranged` to restrict calculations to weapons of that type.
- When using `--csv-dir`, the calculator consumes the CSV outputs directly-no need to maintain a separate JSON file. Include the optional keyword columns your importer emits (`keywords`, weapon `reroll_hits`, `reroll_wounds`, `lethal_hits`, `sustained_hits`, `devastating_wounds`, etc.) so advanced weapon rules propagate end-to-end.
- Supply optional fields such as `reroll_hits`, `reroll_wounds`, `lethal_hits`, `sustained_hits`, `devastating_wounds`, `feel_no_pain`, `damage_cap`, `keywords`, or ability text that grants Twin-linked/Anti-X/Ignore Cover to model common 10th-edition abilities.
- Advanced rules like Heavy, Assault, Rapid Fire, Ignores Cover, and damage reduction require engagement context. When calling the API use `EngagementContext(attacker_moved=..., attacker_advanced=..., target_within_half_range=..., target_in_cover=...)` (see the Python snippet below). CLI invocations presently assume a stationary attacker and no cover, so reach for the snippet or the `preset_matchups.py` helper whenever you need to model advancing, half-range bonuses, or defending units in cover.
- preset_matchups.py wraps the source-backed CLI so you can stick with the original preset commands while still benefiting from preserved keyword data. Combine `--preset`, `--weapon-mode`, `--seed`, and `--csv-dir` to control which tables print without scripting, pair `--attacker` with `--defender` for a single-target duel, and use `--scenario` to feed extra context when you want the AI narrative to weigh positioning or tactics. Use `--random-fair-duel` (optionally with `--max-point-delta`) to auto-pair single-model units that share battlefield keywords and have weapons for the selected mode.

Example: Account for an advancing attacker that fires at half range into a unit in cover by using the Python API directly:

```powershell
python -c "from pathlib import Path; from warhammer.datasheet import load_units_from_csv; from warhammer.calculator import EngagementContext, evaluate_unit; units = load_units_from_csv(Path('data/latest')); attacker = units['Garran Branatar']; defender = units['Rhino']; context = EngagementContext(attacker_moved=True, attacker_advanced=True, target_within_half_range=True, target_in_cover=True); result = evaluate_unit(attacker, defender, 'ranged', context=context); print(f'{attacker.name} vs {defender.name} (ranged) expected damage: {result.total_damage:.2f}')"
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
python datasheet.py --csv-dir data\latest --unit "Intercessor Squad"

# Pick a random unit and print its datasheet
python -c "import random; from pathlib import Path; from warhammer.datasheet import load_units_from_csv, print_unit_datasheet; units = load_units_from_csv(Path('data/latest')); unit = random.choice(list(units.values())); print(f'Random unit selected: {unit.name}'); print_unit_datasheet(unit)"
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
python main.py --csv-dir data/latest --weapon-tables-all-presets-random --weapon-mode all --ppm-basis average

# Lock to a specific attacker and melee weapons only
python main.py --csv-dir data/latest --attacker "Garran Branatar" --weapon-tables-all-presets --weapon-mode melee

# Export the tables to Markdown for later reference
python main.py --csv-dir data/latest --attacker "Garran Branatar" --weapon-tables-all-presets --weapon-mode all --export-table data/latest/garran-vs-presets.md --export-format md

# Optional helper: focus on selected presets through the wrapper
python preset_matchups.py --csv-dir data/latest --attacker "Garran Branatar" --preset vehicles --preset monsters

# Discover available presets without running calculations
python preset_matchups.py --list-presets

# Ask the AI for a preset rundown (Bladeguard)
python preset_matchups.py --csv-dir data/latest --attacker "Bladeguard Veteran Squad" --preset elite --weapon-mode melee --explain --scenario realistic

# Ask the AI for a preset rundown (Wardens)
python preset_matchups.py --csv-dir data/latest --attacker "Custodian Wardens" --preset elite --weapon-mode melee --explain --scenario realistic

# Random two-unit duel (tables only)
python -c "import random, subprocess; from pathlib import Path; from warhammer.datasheet import load_units_from_csv; units = load_units_from_csv(Path('data/latest'));
eligible = [u for u in units.values() if getattr(u, 'points', 0) and any(getattr(w, 'type', '').lower() == 'melee' for w in getattr(u, 'weapons', []))];
if len(eligible) < 2: raise SystemExit('Not enough melee-capable units with points to sample.');
attacker = random.choice(eligible);
defenders = [u for u in eligible if u is not attacker];
defender = random.choice(defenders);
print(f'Selected attacker: {attacker.name} ({attacker.points} pts)');
print(f'Selected defender: {defender.name} ({defender.points} pts)');
subprocess.run(['python', 'preset_matchups.py', '--csv-dir', 'data/latest', '--attacker', attacker.name, '--defender', defender.name, '--weapon-mode', 'melee'], check=False)"

# Two-unit duel (tables only)
python preset_matchups.py --csv-dir data/latest --attacker "Bladeguard Veteran Squad" --defender "Custodian Wardens" --weapon-mode melee

# Random fair duel (single-model, similar points, melee + ranged)
python preset_matchups.py --csv-dir data/latest --random-fair-duel --fair-require-both --weapon-mode all --max-point-delta 40 --explain --scenario realistic

# Random two-unit duel with AI commentary
python -c "import random, subprocess; from pathlib import Path; from warhammer.datasheet import load_units_from_csv; units = load_units_from_csv(Path('data/latest'));
eligible = [u for u in units.values() if getattr(u, 'points', 0) and any(getattr(w, 'type', '').lower() == 'melee' for w in getattr(u, 'weapons', []))];
if len(eligible) < 2: raise SystemExit('Not enough melee-capable units with points to sample.');
attacker = random.choice(eligible);
defenders = [u for u in eligible if u is not attacker];
defender = random.choice(defenders);
print(f'Selected attacker: {attacker.name} ({attacker.points} pts)');
print(f'Selected defender: {defender.name} ({defender.points} pts)');
subprocess.run(['python', 'preset_matchups.py', '--csv-dir', 'data/latest', '--attacker', attacker.name, '--defender', defender.name, '--weapon-mode', 'melee', '--explain', '--scenario', 'realistic'], check=False)"

# Direct duel with AI commentary
python preset_matchups.py --csv-dir data/latest --attacker "Bladeguard Veteran Squad" --defender "Custodian Wardens" --weapon-mode melee --explain --scenario realistic
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
python ai_clean.py --csv-dir data/latest

# Skip the model call and only print the heuristics
python ai_clean.py --csv-dir data/latest --summary-only
```

The script summarises missing values, duplicate names, and other quick checks before handing the report to the model you specify (default: `gpt-5-mini`).

Store your API key in a file rather than hard-coding it:

- Create `%USERPROFILE%\.warhammer_ai_key` (or `credentials/ai_key.txt` inside the repo) and place the key on the first non-comment line (lines starting with `#` are ignored).
- Optional: point to a different location with `WARHAMMER_AI_KEY_FILE` or continue using `WARHAMMER_AI_API_KEY`/`OPENAI_API_KEY` if you prefer environment variables.

The helper in `preset_matchups.py` simply reuses that engine for convenience when you want to focus on a subset of presets or discover the available defender tables.

### Data completeness audit

Run the audit whenever you refresh the importer output to see which units still need manual points/min/max data and to catch suspicious weapon/profile rows, such as placeholder damage, invalid Strength/AP values, orphaned weapon links, duplicate profile IDs, and duplicate mappings:

```powershell
python audit_import.py --csv-dir data/latest
```

Write the same results to JSON for review tooling or the web UI:

```powershell
python audit_import.py --csv-dir data/latest --json-report data/latest/audit_report.json
```

Use `--fail-on-issues` when you want a CI-style non-zero exit code:

```powershell
python audit_import.py --csv-dir data/latest --fail-on-issues
```

This helper only uses the exported CSVs, so it behaves just like the AI checker but without requiring an API key. The latest generation timestamp and source path are stored in `data/latest/metadata.json`.

For a human-readable update summary, open `data/latest/update_report.md`. It includes the source BSData commit, audit status, row counts, and import diff counts, and it is also copied into each `data/snapshots/<commit>` folder.











