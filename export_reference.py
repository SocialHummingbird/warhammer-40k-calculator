"""Generate keyword and ability reference sheets from importer CSV outputs."""

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import csv


def main() -> None:
    args = _parse_args()
    csv_dir = Path(args.csv_dir)
    if not csv_dir.exists():
        raise SystemExit(f"CSV directory not found: {csv_dir}")

    units = _read_csv(csv_dir / "units.csv")
    abilities = _read_csv(csv_dir / "abilities.csv")
    keywords = _read_csv(csv_dir / "keywords.csv")
    unit_keywords = _read_csv(csv_dir / "unit_keywords.csv")

    unit_names = {row["unit_id"]: row["name"] for row in units if row.get("unit_id")}

    keyword_entries = {}
    keyword_units: Dict[str, List[str]] = defaultdict(list)
    for row in keywords:
        keyword_id = row.get("keyword_id")
        keyword = row.get("keyword")
        if not keyword_id or not keyword:
            continue
        keyword_entries[keyword_id] = {
            "keyword": keyword,
            "description": row.get("description", "")
        }
    for row in unit_keywords:
        unit_id = row.get("unit_id")
        keyword_id = row.get("keyword_id")
        unit_name = unit_names.get(unit_id)
        if keyword_id in keyword_entries and unit_name:
            keyword_units[keyword_id].append(unit_name)

    ability_entries: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: {"text": "", "units": []})
    for row in abilities:
        if row.get("source_type", "").lower() != "unit":
            continue
        name = row.get("name")
        if not name:
            continue
        text = (row.get("text") or "").strip()
        if ability_entries[name]["text"] and text and ability_entries[name]["text"] != text:
            ability_entries[name]["text"] += f"\n\n{text}"
        elif text:
            ability_entries[name]["text"] = text
        unit_name = unit_names.get(row.get("source_id"))
        if unit_name and unit_name not in ability_entries[name]["units"]:
            ability_entries[name]["units"].append(unit_name)

    lines: List[str] = []
    lines.append("# Keyword Reference")
    lines.append("")
    for keyword_id, entry in sorted(keyword_entries.items(), key=lambda item: item[1]["keyword"].lower()):
        keyword = entry["keyword"]
        description = entry["description"].strip()
        units_list = sorted(keyword_units.get(keyword_id, []))
        lines.append(f"## {keyword}")
        lines.append("")
        lines.append(f"- Description: {description or 'None'}")
        if units_list:
            lines.append(f"- Units: {', '.join(units_list)}")
        else:
            lines.append("- Units: None")
        lines.append("")

    lines.append("# Ability Reference")
    lines.append("")
    for name, payload in sorted(ability_entries.items(), key=lambda item: item[0].lower()):
        text = payload["text"].strip()
        units_list = sorted(payload["units"])
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- Units: {', '.join(units_list) if units_list else 'None'}")
        lines.append("")
        if text:
            lines.append(text)
        else:
            lines.append("(No description provided.)")
        lines.append("")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote reference sheet to {output_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate keyword and ability references from importer CSVs")
    parser.add_argument("--csv-dir", required=True, help="Directory containing CSV exports from import_bsdata.py")
    parser.add_argument(
        "--output",
        default="references.md",
        help="Output Markdown file (default: %(default)s)"
    )
    return parser.parse_args()


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
