# Warhammer 40K Damage Calculator

## Overview
This project estimates the expected damage exchange between two Warhammer 40,000 units. It reads unit and weapon profiles, resolves hit/wound/save probabilities, and reports the average unsaved wounds, damage, and models destroyed in each direction.

Key features:
- Deterministic calculator for ranged or melee engagements using expected values.
- Flexible dice parser that understands fixed values and expressions such as `D6`, `2D3+3`, etc.
- Import pipeline for BattleScribe/BSData catalogues so you can stay up to date with community data.
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

## Importing units from BSData catalogues
1. Retrieve the Warhammer 40,000 BSData repository (for example, by cloning `https://github.com/BSData/wh40k-10e` or letting the importer download it on demand with `python import_bsdata.py --github-repo BSData/wh40k-10e --output data\latest`).
2. Run the importer to convert catalogues into CSV extracts:
   ```powershell
   python import_bsdata.py "C:\path\to\wh40k-10e" --output data\latest
   ```
   The script emits `units.csv`, `weapons.csv`, `abilities.csv`, `keywords.csv`, and `unit_keywords.csv` under `data\latest`.
3. Point the calculator at the generated CSVs:
   ```powershell
   python main.py --csv-dir data\latest --list-units
   python main.py --csv-dir data\latest --attacker "Intercessor Squad" --defender "Necron Warrior" --mode ranged
   ```

Tip: Use `--github-ref` to pin to a specific release tag and `--github-subdir` if you only need a single faction folder (for example `--github-subdir "Imperium - Adeptus Custodes.cat"`).

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
- When using `--csv-dir`, the calculator consumes the CSV outputs directly—no need to maintain a separate JSON file.
- Supply optional fields such as `reroll_hits`, `reroll_wounds`, `lethal_hits`, `sustained_hits`, `devastating_wounds`, `feel_no_pain`, or `damage_cap` to model common 10th-edition abilities.

## Directory recap
- `main.py` – CLI damage calculator.
- `import_bsdata.py` – BSData catalogue importer that emits CSV tables.
- `export_reference.py` – Markdown reference generator for keywords and abilities.
- `warhammer/` – Package containing the dice parser, profile models, calculator, importer helpers, and reference utilities.

## Support & contributions
This repository is intended for hobby and educational purposes. Feel free to fork the project and tailor it to your army. If you extend the rules engine or importer, document the changes in `CHANGELOG.md` and update this README so PowerShell users know which commands to run.

