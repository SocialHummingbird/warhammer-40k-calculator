# Changelog

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
- Extend rules engine to cover additional abilities (Devastating Wounds, damage caps, etc.) as richer data becomes available.
- Tie the reference output into the main CLI or a lightweight UI for quicker in-app lookups.
