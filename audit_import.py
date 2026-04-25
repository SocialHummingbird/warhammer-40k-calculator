#!/usr/bin/env python3
"""Audit importer CSV exports for missing or inconsistent profile data."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from warhammer.dice import QuantityParseError, parse_quantity


IssueMap = Dict[str, List[str]]

_PLACEHOLDERS = {"", "*", "d*", "-", "--", "—", "n/a", "na", "none", "null"}
_INT_PATTERN = re.compile(r"^[+-]?\d+$")

_ERROR_ISSUES = {
    "missing_unit_ids",
    "duplicate_unit_ids",
    "invalid_toughness",
    "invalid_wounds",
    "invalid_save",
    "invalid_invulnerable_save",
    "duplicate_weapon_ids",
    "orphaned_weapons",
    "missing_weapon_names",
    "placeholder_attacks",
    "placeholder_strength",
    "placeholder_ap",
    "placeholder_damage",
    "invalid_attacks_expression",
    "invalid_damage_expression",
    "invalid_strength",
    "invalid_ap",
    "invalid_skill",
    "invalid_weapon_type",
    "duplicate_ability_ids",
    "orphaned_unit_abilities",
    "orphaned_unit_keywords",
    "orphaned_keyword_ids",
}

_WARNING_ISSUES = {
    "missing_points",
    "missing_models_min",
    "missing_models_max",
    "duplicate_names",
    "duplicate_weapon_profiles_per_unit",
    "missing_keywords",
    "missing_ability_names",
    "duplicate_pairs",
}



def _safe_print(message: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(message.encode(encoding, errors="replace").decode(encoding))


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _top(entries: Iterable[str], limit: int = 10) -> List[str]:
    counter = Counter(entries)
    most_common = counter.most_common(limit)
    return [f"{value} (x{count})" for value, count in most_common]


def _normalise(value: Optional[str]) -> str:
    return (value or "").strip()


def _is_placeholder(value: Optional[str]) -> bool:
    return _normalise(value).lower() in _PLACEHOLDERS


def _sample(rows: Iterable[str], limit: int = 10) -> List[str]:
    return list(rows)[:limit]


def _row_label(row: Dict[str, str], *, id_field: str = "unit_id") -> str:
    name = _normalise(row.get("name")) or "<unnamed>"
    identifier = _normalise(row.get(id_field))
    return f"{name} [{identifier}]" if identifier else name


def _valid_roll(value: Optional[str], *, allow_auto: bool = False, max_allowed: int = 6) -> bool:
    cleaned = _normalise(value)
    if allow_auto and cleaned.lower() in {"auto", "automatic", "n/a", "na", "-", "none"}:
        return True
    if cleaned.endswith("+"):
        cleaned = cleaned[:-1]
    if not cleaned.isdigit():
        return False
    roll = int(cleaned)
    return 2 <= roll <= max_allowed


def _valid_int(value: Optional[str]) -> bool:
    return bool(_INT_PATTERN.match(_normalise(value)))


def _valid_strength(value: Optional[str]) -> bool:
    if _is_placeholder(value):
        return False
    cleaned = _normalise(value)
    if cleaned.endswith("+") and cleaned[:-1].isdigit():
        cleaned = cleaned[:-1]
    try:
        parse_quantity(cleaned)
    except QuantityParseError:
        return False
    return True


def _all_issue_values(*issue_maps: IssueMap) -> List[str]:
    values: List[str] = []
    for issue_map in issue_maps:
        for issue_values in issue_map.values():
            values.extend(issue_values)
    return values


def _severity(issue_key: str) -> str:
    if issue_key in _ERROR_ISSUES:
        return "error"
    if issue_key in _WARNING_ISSUES:
        return "warning"
    return "info"


def audit_units(rows: List[Dict[str, str]]) -> IssueMap:
    issues: IssueMap = defaultdict(list)

    missing_ids = [row.get("name") or "<unnamed>" for row in rows if not _normalise(row.get("unit_id"))]
    if missing_ids:
        issues["missing_unit_ids"] = _sample(missing_ids)

    duplicate_ids = [row["unit_id"].strip() for row in rows if _normalise(row.get("unit_id"))]
    duplicates = [unit_id for unit_id, count in Counter(duplicate_ids).items() if count > 1]
    if duplicates:
        issues["duplicate_unit_ids"] = sorted(duplicates)[:10]

    unit_rows = [row for row in rows if (row.get("selection_type") or "").strip().lower() == "unit"]

    missing_points = [row["name"] for row in unit_rows if not (row.get("points") or "").strip()]
    if missing_points:
        issues["missing_points"] = _top(missing_points)

    missing_min = [row["name"] for row in unit_rows if not (row.get("models_min") or "").strip()]
    if missing_min:
        issues["missing_models_min"] = _top(missing_min)

    missing_max = [row["name"] for row in unit_rows if not (row.get("models_max") or "").strip()]
    if missing_max:
        issues["missing_models_max"] = _top(missing_max)

    duplicate_names = [row["name"].strip() for row in rows if row.get("name")]
    duplicates = [name for name, count in Counter(duplicate_names).items() if count > 1]
    if duplicates:
        issues["duplicate_names"] = sorted(duplicates)[:10]

    for field in ("toughness", "wounds"):
        bad_rows = [
            _row_label(row)
            for row in rows
            if _is_placeholder(row.get(field)) or not _valid_int(row.get(field))
        ]
        if bad_rows:
            issues[f"invalid_{field}"] = _sample(bad_rows)

    bad_saves = [_row_label(row) for row in rows if not _valid_roll(row.get("save"), max_allowed=7)]
    if bad_saves:
        issues["invalid_save"] = _sample(bad_saves)

    bad_invulnerable = [
        _row_label(row)
        for row in rows
        if _normalise(row.get("invulnerable_save")) and not _valid_roll(row.get("invulnerable_save"))
    ]
    if bad_invulnerable:
        issues["invalid_invulnerable_save"] = _sample(bad_invulnerable)

    return issues


def audit_weapons(rows: List[Dict[str, str]], unit_ids: Optional[Set[str]] = None) -> IssueMap:
    issues: IssueMap = defaultdict(list)

    missing_keywords = [row["weapon_id"] for row in rows if not (row.get("keywords") or "").strip()]
    if missing_keywords:
        issues["missing_keywords"] = missing_keywords[:10]

    duplicate_ids = [row["weapon_id"] for row in rows if row.get("weapon_id")]
    duplicates = [weapon_id for weapon_id, count in Counter(duplicate_ids).items() if count > 1]
    if duplicates:
        issues["duplicate_weapon_ids"] = duplicates[:10]

    duplicate_profile_keys = [
        f"{unit_id}:{name}:{weapon_type}"
        for (unit_id, name, weapon_type), count in Counter(
            (
                _normalise(row.get("unit_id")),
                _normalise(row.get("name")).lower(),
                _normalise(row.get("weapon_type")).lower(),
            )
            for row in rows
        ).items()
        if count > 1 and unit_id and name
    ]
    if duplicate_profile_keys:
        issues["duplicate_weapon_profiles_per_unit"] = duplicate_profile_keys[:10]

    if unit_ids is not None:
        orphaned = [
            _row_label(row, id_field="weapon_id")
            for row in rows
            if _normalise(row.get("unit_id")) not in unit_ids
        ]
        if orphaned:
            issues["orphaned_weapons"] = _sample(orphaned)

    missing_names = [_normalise(row.get("weapon_id")) or "<missing weapon id>" for row in rows if not _normalise(row.get("name"))]
    if missing_names:
        issues["missing_weapon_names"] = _sample(missing_names)

    for field in ("attacks", "strength", "ap", "damage"):
        placeholders = [
            f"{_row_label(row, id_field='weapon_id')} {field}={_normalise(row.get(field)) or '<blank>'}"
            for row in rows
            if _is_placeholder(row.get(field))
        ]
        if placeholders:
            issues[f"placeholder_{field}"] = _sample(placeholders)

    for field in ("attacks", "damage"):
        invalid = []
        for row in rows:
            value = row.get(field)
            if _is_placeholder(value):
                continue
            try:
                parse_quantity(value or "")
            except QuantityParseError:
                invalid.append(f"{_row_label(row, id_field='weapon_id')} {field}={_normalise(value)!r}")
        if invalid:
            issues[f"invalid_{field}_expression"] = _sample(invalid)

    invalid_strength = [
        f"{_row_label(row, id_field='weapon_id')} strength={_normalise(row.get('strength'))!r}"
        for row in rows
        if not _is_placeholder(row.get("strength")) and not _valid_strength(row.get("strength"))
    ]
    if invalid_strength:
        issues["invalid_strength"] = _sample(invalid_strength)

    invalid_ap = [
        f"{_row_label(row, id_field='weapon_id')} ap={_normalise(row.get('ap'))!r}"
        for row in rows
        if not _is_placeholder(row.get("ap")) and not _valid_int(row.get("ap"))
    ]
    if invalid_ap:
        issues["invalid_ap"] = _sample(invalid_ap)

    invalid_skills = [
        f"{_row_label(row, id_field='weapon_id')} skill={_normalise(row.get('skill'))!r}"
        for row in rows
        if not _valid_roll(row.get("skill"), allow_auto=True)
    ]
    if invalid_skills:
        issues["invalid_skill"] = _sample(invalid_skills)

    invalid_types = [
        f"{_row_label(row, id_field='weapon_id')} type={_normalise(row.get('weapon_type'))!r}"
        for row in rows
        if _normalise(row.get("weapon_type")).lower() not in {"ranged", "melee"}
    ]
    if invalid_types:
        issues["invalid_weapon_type"] = _sample(invalid_types)

    return issues


def audit_abilities(rows: List[Dict[str, str]], unit_ids: Optional[Set[str]] = None) -> IssueMap:
    issues: IssueMap = defaultdict(list)

    missing_names = [
        _normalise(row.get("ability_id")) or f"{_normalise(row.get('source_type'))}:{_normalise(row.get('source_id'))}"
        for row in rows
        if not _normalise(row.get("name"))
    ]
    if missing_names:
        issues["missing_ability_names"] = _sample(missing_names)

    duplicate_ids = [row["ability_id"].strip() for row in rows if _normalise(row.get("ability_id"))]
    duplicates = [ability_id for ability_id, count in Counter(duplicate_ids).items() if count > 1]
    if duplicates:
        issues["duplicate_ability_ids"] = duplicates[:10]

    if unit_ids is not None:
        orphaned = [
            _row_label(row, id_field="ability_id")
            for row in rows
            if _normalise(row.get("source_type")).lower() == "unit"
            and _normalise(row.get("source_id")) not in unit_ids
        ]
        if orphaned:
            issues["orphaned_unit_abilities"] = _sample(orphaned)

    return issues


def audit_unit_keywords(
    rows: List[Dict[str, str]],
    unit_ids: Optional[Set[str]] = None,
    keyword_ids: Optional[Set[str]] = None,
) -> IssueMap:
    issues: IssueMap = defaultdict(list)
    duplicates: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for row in rows:
        key = (row.get("unit_id", ""), row.get("keyword_id", ""))
        if key in seen:
            duplicates.append(key)
        else:
            seen.add(key)
    if duplicates:
        issues["duplicate_pairs"] = [f"{unit}:{keyword}" for unit, keyword in duplicates[:10]]

    if unit_ids is not None:
        orphaned_units = [
            f"{_normalise(row.get('unit_id'))}:{_normalise(row.get('keyword_id'))}"
            for row in rows
            if _normalise(row.get("unit_id")) not in unit_ids
        ]
        if orphaned_units:
            issues["orphaned_unit_keywords"] = _sample(orphaned_units)

    if keyword_ids is not None:
        orphaned_keywords = [
            f"{_normalise(row.get('unit_id'))}:{_normalise(row.get('keyword_id'))}"
            for row in rows
            if _normalise(row.get("keyword_id")) not in keyword_ids
        ]
        if orphaned_keywords:
            issues["orphaned_keyword_ids"] = _sample(orphaned_keywords)

    return issues


def _print_section(title: str, issues: IssueMap, clean_message: str) -> None:
    _safe_print(f"\n=== {title} ===")
    if not issues:
        _safe_print(clean_message)
        return

    for key, values in issues.items():
        _safe_print(f"- {key.replace('_', ' ')} ({len(values)} sample{'s' if len(values) != 1 else ''} shown): {', '.join(values)}")


def _load_optional_csv(csv_dir: Path, filename: str) -> List[Dict[str, str]]:
    path = csv_dir / filename
    if not path.exists():
        return []
    return _load_csv(path)


def build_audit_report(csv_dir: Path) -> dict[str, object]:
    """Build a structured audit report for importer CSV outputs."""

    csv_dir = Path(csv_dir)
    units = _load_csv(csv_dir / "units.csv")
    weapons = _load_csv(csv_dir / "weapons.csv")
    abilities = _load_optional_csv(csv_dir, "abilities.csv")
    keywords = _load_optional_csv(csv_dir, "keywords.csv")
    unit_keywords = _load_optional_csv(csv_dir, "unit_keywords.csv")

    unit_ids = {_normalise(row.get("unit_id")) for row in units if _normalise(row.get("unit_id"))}
    keyword_ids = {_normalise(row.get("keyword_id")) for row in keywords if _normalise(row.get("keyword_id"))}

    raw_sections = {
        "units": audit_units(units),
        "weapons": audit_weapons(weapons, unit_ids=unit_ids),
        "abilities": audit_abilities(abilities, unit_ids=unit_ids),
        "unit_keywords": audit_unit_keywords(unit_keywords, unit_ids=unit_ids, keyword_ids=keyword_ids),
    }
    sections = {name: _section_report(issues) for name, issues in raw_sections.items()}
    summary = {
        "error": sum(
            len(issue["samples"])
            for section in sections.values()
            for issue in section["issues"]
            if issue["severity"] == "error"
        ),
        "warning": sum(
            len(issue["samples"])
            for section in sections.values()
            for issue in section["issues"]
            if issue["severity"] == "warning"
        ),
        "info": sum(
            len(issue["samples"])
            for section in sections.values()
            for issue in section["issues"]
            if issue["severity"] == "info"
        ),
    }
    summary["total"] = summary["error"] + summary["warning"] + summary["info"]

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "csv_dir": str(csv_dir),
        "row_counts": {
            "units": len(units),
            "weapons": len(weapons),
            "abilities": len(abilities),
            "keywords": len(keywords),
            "unit_keywords": len(unit_keywords),
        },
        "summary": summary,
        "sections": sections,
    }


def _section_report(issues: IssueMap) -> dict[str, object]:
    issue_entries = []
    for key, values in issues.items():
        issue_entries.append(
            {
                "key": key,
                "label": key.replace("_", " "),
                "severity": _severity(key),
                "samples": list(values),
                "sample_count": len(values),
            }
        )
    return {
        "issue_count": sum(len(entry["samples"]) for entry in issue_entries),
        "issues": issue_entries,
    }


def write_audit_report(report: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit importer CSVs for missing or suspicious profile data")
    parser.add_argument("--csv-dir", type=Path, default=Path("data/latest"), help="Directory containing the CSV exports")
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with status 1 if any audit issue is detected.",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        help="Optional path to write the structured audit report as JSON.",
    )
    args = parser.parse_args(argv)

    csv_dir = args.csv_dir
    report = build_audit_report(csv_dir)
    if args.json_report:
        write_audit_report(report, args.json_report)

    _safe_print(f"Auditing CSV exports in {csv_dir}")
    row_counts = report["row_counts"]
    _safe_print(
        f"Rows: {row_counts['units']} units, {row_counts['weapons']} weapons, "
        f"{row_counts['abilities']} abilities, {row_counts['keywords']} keywords, "
        f"{row_counts['unit_keywords']} unit-keyword links"
    )

    for title, section_name, clean_message in (
        ("Units", "units", "All units passed the profile checks."),
        ("Weapons", "weapons", "All weapons passed the profile checks."),
        ("Abilities", "abilities", "All abilities passed the profile checks."),
        ("Unit keywords", "unit_keywords", "All unit-keyword mappings passed the profile checks."),
    ):
        _print_section_from_report(title, report["sections"][section_name], clean_message)

    issue_count = report["summary"]["total"]
    if args.json_report:
        _safe_print(f"\nWrote audit report to {args.json_report}")
    _safe_print(f"\nAudit complete: {issue_count} sampled issue value{'s' if issue_count != 1 else ''} reported.")
    return 1 if issue_count and args.fail_on_issues else 0


def _print_section_from_report(title: str, section: dict[str, object], clean_message: str) -> None:
    _safe_print(f"\n=== {title} ===")
    issues = section["issues"]
    if not issues:
        _safe_print(clean_message)
        return
    for issue in issues:
        samples = issue["samples"]
        sample_word = "samples" if len(samples) != 1 else "sample"
        _safe_print(
            f"- [{issue['severity'].upper()}] {issue['label']} "
            f"({len(samples)} {sample_word} shown): {', '.join(samples)}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
