# Changelog

## Planned Work
- [ ] Refactor core boundaries before adding ML-heavy features.
  - [x] Extract deterministic matchup orchestration into `warhammer.matchups` so the web API and future ML exporters can share one calculation path.
  - [x] Extract generated review artifact loading into `warhammer.data_review`.
  - [x] Extract edition metadata, discovery, and readiness rows into `warhammer.editions`.
  - [x] Extract API payload parsing into `warhammer.api_payloads` and unit filtering into `warhammer.unit_search`.
- [ ] Add ML foundation.
  - [x] Add `warhammer.ml.features` and `export_ml_features.py` to generate deterministic calculator-derived matchup feature rows.
  - [x] Add seeded sampling for capped feature exports so training rows cover more than the first sorted pair block.
  - [x] Add a dependency-free nearest-centroid advisory model trainer.
  - [x] Expose saved model predictions as a separate `ml_judgement` advisory in the local server UI and standalone HTML export.
  - [x] Surface model availability, training rows, and validation accuracy through `/api/health` and the UI status bar.
  - [x] Add a Markdown ML audit report covering label source, class balance, validation confusion, feature columns, and synthetic-label caveats.
  - [x] Add a `pre_match` ML feature set that excludes deterministic calculator output columns, while keeping the previous `full` feature set for comparison.
  - [x] Add same-mode weapon aggregate features to `pre_match` training rows so the model can see weapon profile shape without seeing calculator outputs.
  - [x] Surface ML model audit content and model artifact links through the Data Review screen and standalone HTML export.
  - [x] Regenerate ML features, model, and audit during `update_database.py` before rebuilding standalone HTML, with `--skip-ml` for data-only refreshes.
  - [x] Store feature CSV provenance in trained model JSON and surface the saved feature row count/hash in the ML audit report.
  - Later replace or augment the dependency-free baseline with a stronger optional model.
- [ ] Add multi-edition support so 10th edition and future 11th edition data can coexist without sharing incompatible rules assumptions.
  - [x] First step: introduce an explicit ruleset registry and route current calculator behavior through a `10e` ruleset while keeping current outputs unchanged.
  - [x] Add edition metadata to generated data artifacts and display the active rules edition in the UI status.
  - [x] Add an edition selector and calculate-request edition field, currently locked to available `10e` data.
  - [x] Add edition-scoped data layout with `data/10e/latest` and `data/10e/snapshots`, while mirroring `data/latest` for compatibility.
  - [x] Add server-side discovery for `data/<edition>/latest` folders and surface discovered edition data in the UI.
  - [x] Load discovered edition datasets server-side and route unit search, unit detail, data review, review downloads, and calculations through the selected edition.
  - [x] Keep discovered editions with missing rulesets visible as blocked, e.g. future `11e` data before an `11e` rules engine exists.
  - [x] Write `edition_status.json` during database updates so each generated data folder records ruleset availability, calculation readiness, blockers, and source provenance.
  - Later add separate 11th-edition importer/data snapshots once an upstream data source and rules mapping are available.

## 2025-10-02
- Ability parsing now recognises abilities that grant the [Assault] keyword, keeping those modifiers so ranged weapons fire after advancing when granted by enhancements.
- Combat resolution respects ability-granted Assault, skipping the advance shooting block, applying the correct hit penalties, and annotating the output notes accordingly.
- CSV loaders propagate Leadership and Objective Control columns into `UnitProfile`, exposing those stats for future CLI and rules features.
- Added regression tests covering ability-granted Assault behaviour and importer Leadership/OC wiring.

## 2025-09-24
- Ability parsing now detects hit/wound modifiers and rerolls from ability text and applies them when conditions match.
- Ability modifiers now honour ability-granted Torrent auto-hits and conditional Twin-linked triggers so keyword-driven abilities affect combat resolution.
- Added datasheet.py CLI to print a parsed unit datasheet for verification.
- Datasheet output hides Crusade upgrades/battle scars by default (use --include-crusade to show them).
- Rules engine now applies weapon keywords (Assault/Heavy/Rapid Fire/Twin-linked/Anti-X) and engagement context when resolving attacks; importer and profiles propagate keyword data end-to-end.
- Cover interactions (target in cover vs. Ignores Cover) and defender damage reduction from abilities now modify saves and damage during resolution.
- CSV loaders now apply heuristics when duplicate unit names exist (prefer matching faction, non-Legends/Library profiles).
- preset_matchups.py now reuses the main CLI data loaders so preset runs avoid duplicate warnings while retaining the original rules logic.
- preset_matchups.py now highlights fast defenders (>=10" Move or Advance+Charge) when printing preset tables so likely chargers stand out.
- Added --random-fair-duel to preset_matchups.py to auto-pair single-model units with shared keywords, similar points, and weapons for the requested mode.
- Formatted all matchup tables to display three decimal places so low-probability damage is visible.
- Matchup tables now print each weapon's profile (attacks, skill, strength, AP, damage, and standout keywords) so attacker stats sit beside defender defenses, with keyword abbreviations (ASLT, RF2, TL, etc.) to keep the column narrow.
- Added ai_clean.py helper that summarises importer CSV health and can query an AI model (defaults to gpt-5-mini) for potential data fixes.
- ai_clean.py now loads its API key from ~/.warhammer_ai_key (or credentials/ai_key.txt) before falling back to environment variables, ignoring comment lines so you can keep inline instructions.
- Added audit_import.py to highlight units missing points/min/max values and duplicate mappings, complementing the AI checker.
- Deduplicate weapon rows and unit-keyword mappings during import to avoid duplicate IDs in the exported CSVs.

### TODOs
- [x] Extend the rules engine and ability parser for the remaining keyword-driven effects (Anti-/Torrent/Blast, flat damage reduction, conditional Twin-linked).
- [ ] Refresh README advanced usage examples to cover keyword imports, engagement context flags, and preset matchup commands.
- [x] Add smoke tests around preset_matchups.py to catch header/format regressions when importing sample data.

## 2025-09-16
- Initial CLI damage calculator implemented: parses unit/weapon data, resolves expected wounds/damage, and prints summaries for both directions.
- Core modules added:
  - `warhammer.dice` for dice notation parsing to average values.
  - `warhammer.profiles` dataclasses for normalised unit/weapon definitions with validation helpers.
  - `warhammer.calculator` for probabilistic resolution of hit/wound/save sequences plus damage totals.
- Provided starter dataset (`units.json`) and usage documentation (`README.md`).
- Added BSData importer utilities: CSV schema definitions, XML parsing helpers, CLI (`import_bsdata.py`), sample catalogue, and `unit_keywords.csv` outputs.
- Extended profiles to capture abilities/keywords, built a CSV loader, and updated the main CLI (`--csv-dir`) to consume importer output directly.
- New `export_reference.py` creates Markdown keyword and ability reference sheets from importer CSV directories.
- Added `warhammer.reference` helper and `main.py --reference` option to generate keyword/ability summaries without leaving the CLI.
- Rules engine now models hit/wound rerolls, Sustained Hits, Lethal Hits, Devastating Wounds, Feel No Pain reductions, and defender damage caps; schema/CLI updated to accept these fields.

### Planned enhancements
- Broaden the importer coverage (e.g. detachment rules, complex wargear options) and integrate CSV outputs with future roster management tooling.
- Extend rules engine to interpret the weapon keywords and defensive modifiers we still ignore (e.g. Anti-X, Blast, Heavy/Assault/Torrent, Melta/Twin-linked, Ignores Cover, flat damage reduction).
- Tie the reference output into the main CLI or a lightweight UI for quicker in-app lookups.


