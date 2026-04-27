#!/usr/bin/env python3
"""Generate human-reviewable joined profile exports from importer CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
from urllib.parse import quote

from warhammer.dice import QuantityParseError, parse_quantity
from warhammer.profiles import UnitProfile, _extract_damage_reduction_from_text


WEAPON_REVIEW_HEADERS = [
    "faction",
    "unit_name",
    "selection_type",
    "unit_id",
    "source_file",
    "unit_points",
    "models_min",
    "models_max",
    "weapon_id",
    "weapon_name",
    "weapon_type",
    "attacks",
    "skill",
    "strength",
    "ap",
    "damage",
    "attacks_average",
    "strength_average",
    "damage_average",
    "attacks_parse_status",
    "strength_parse_status",
    "damage_parse_status",
    "raw_damage_throughput",
    "keywords",
    "hit_modifier",
    "wound_modifier",
    "reroll_hits",
    "reroll_wounds",
    "lethal_hits",
    "sustained_hits",
    "devastating_wounds",
]

SUSPICIOUS_WEAPON_REVIEW_HEADERS = [
    *WEAPON_REVIEW_HEADERS,
    "review_severity",
    "review_category",
    "review_reason",
]

ABILITY_REVIEW_HEADERS = [
    "faction",
    "unit_name",
    "selection_type",
    "unit_id",
    "source_file",
    "source_type",
    "source_id",
    "ability_id",
    "ability_name",
    "text",
]

ABILITY_MODIFIER_REVIEW_HEADERS = [
    "faction",
    "unit_name",
    "selection_type",
    "unit_id",
    "source_file",
    "modifier_type",
    "source",
    "description",
    "hit_modifier",
    "wound_modifier",
    "reroll_hits",
    "reroll_wounds",
    "grants",
    "anti_rules",
    "ignores_cover",
    "applies_to_ranged",
    "applies_to_melee",
    "target_keywords",
    "damage_reduction",
]

UNIT_VARIANT_REVIEW_HEADERS = [
    "unit_name",
    "variant_count",
    "unit_id",
    "source_file",
    "faction",
    "selection_type",
    "points",
    "models_min",
    "models_max",
    "toughness",
    "save",
    "wounds",
]

UNIT_WEAPON_COVERAGE_HEADERS = [
    "faction",
    "unit_name",
    "selection_type",
    "unit_id",
    "source_file",
    "points",
    "models_min",
    "models_max",
    "total_weapons",
    "ranged_weapons",
    "melee_weapons",
    "coverage",
]

LOADOUT_REVIEW_HEADERS = [
    *UNIT_WEAPON_COVERAGE_HEADERS,
    "review_severity",
    "review_category",
    "review_reason",
]

SOURCE_CATALOGUE_REVIEW_HEADERS = [
    "source_file",
    "source_url",
    "factions",
    "units",
    "weapon_profiles",
    "ability_profiles",
    "suspicious_weapon_profiles",
    "unit_profile_issue_rows",
    "loadout_review_rows",
    "duplicate_name_unit_rows",
    "no_weapon_units",
]

UNIT_PROFILE_REVIEW_HEADERS = [
    "faction",
    "unit_name",
    "selection_type",
    "unit_id",
    "source_file",
    "toughness",
    "save",
    "invulnerable_save",
    "wounds",
    "move",
    "leadership",
    "objective_control",
    "points",
    "models_min",
    "models_max",
    "feel_no_pain",
    "damage_cap",
    "toughness_status",
    "save_status",
    "wounds_status",
    "points_status",
    "model_count_status",
    "review_severity",
    "review_category",
    "review_reason",
]


def write_profile_review(csv_dir: Path) -> dict[str, int]:
    csv_dir = Path(csv_dir)
    units = _read_csv(csv_dir / "units.csv")
    weapons = _read_csv(csv_dir / "weapons.csv")
    abilities = _read_csv(csv_dir / "abilities.csv")

    unit_by_id = {row.get("unit_id", ""): row for row in units if row.get("unit_id")}
    weapon_rows = build_weapon_review_rows(weapons, unit_by_id)
    suspicious_weapon_rows = build_suspicious_weapon_review_rows(weapon_rows)
    ability_rows = build_ability_review_rows(abilities, unit_by_id)
    ability_modifier_rows = build_ability_modifier_review_rows(units, abilities)
    unit_variant_rows = build_unit_variant_review_rows(units)
    weapon_coverage_rows = build_unit_weapon_coverage_rows(units, weapons)
    loadout_rows = build_loadout_review_rows(weapon_coverage_rows)
    unit_profile_rows = build_unit_profile_review_rows(units)
    source_catalogue_rows = build_source_catalogue_review_rows(
        units,
        weapon_rows,
        ability_rows,
        suspicious_weapon_rows,
        unit_profile_rows,
        loadout_rows,
        unit_variant_rows,
        weapon_coverage_rows,
        source_blob_base_url=_source_blob_base_url(csv_dir / "metadata.json"),
    )

    _write_csv(csv_dir / "weapon_profile_review.csv", WEAPON_REVIEW_HEADERS, weapon_rows)
    _write_csv(csv_dir / "suspicious_weapon_review.csv", SUSPICIOUS_WEAPON_REVIEW_HEADERS, suspicious_weapon_rows)
    _write_csv(csv_dir / "unit_profile_review.csv", UNIT_PROFILE_REVIEW_HEADERS, unit_profile_rows)
    _write_csv(csv_dir / "ability_profile_review.csv", ABILITY_REVIEW_HEADERS, ability_rows)
    _write_csv(csv_dir / "ability_modifier_review.csv", ABILITY_MODIFIER_REVIEW_HEADERS, ability_modifier_rows)
    _write_csv(csv_dir / "unit_variant_review.csv", UNIT_VARIANT_REVIEW_HEADERS, unit_variant_rows)
    _write_csv(csv_dir / "unit_weapon_coverage_review.csv", UNIT_WEAPON_COVERAGE_HEADERS, weapon_coverage_rows)
    _write_csv(csv_dir / "loadout_review.csv", LOADOUT_REVIEW_HEADERS, loadout_rows)
    _write_csv(csv_dir / "source_catalogue_review.csv", SOURCE_CATALOGUE_REVIEW_HEADERS, source_catalogue_rows)
    (csv_dir / "profile_review.md").write_text(
        build_profile_review_markdown(
            units,
            weapon_rows,
            suspicious_weapon_rows,
            ability_rows,
            ability_modifier_rows,
            unit_variant_rows,
            weapon_coverage_rows,
            loadout_rows,
            unit_profile_rows,
            source_catalogue_rows,
        ),
        encoding="utf-8",
    )

    return {
        "units": len(units),
        "weapon_profiles": len(weapon_rows),
        "suspicious_weapon_profiles": len(suspicious_weapon_rows),
        "unit_profile_review_rows": len(unit_profile_rows),
        "unit_profile_issue_rows": sum(1 for row in unit_profile_rows if row.get("review_severity")),
        "ability_profiles": len(ability_rows),
        "ability_modifiers": len(ability_modifier_rows),
        "unit_name_variants": len(unit_variant_rows),
        "unit_weapon_coverage_rows": len(weapon_coverage_rows),
        "loadout_review_rows": len(loadout_rows),
        "source_catalogue_review_rows": len(source_catalogue_rows),
    }


def build_weapon_review_rows(
    weapons: Iterable[Dict[str, str]],
    unit_by_id: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for weapon in weapons:
        unit = unit_by_id.get(weapon.get("unit_id", ""), {})
        attacks_average, attacks_status = _quantity_average_and_status(weapon.get("attacks", ""))
        strength_average, strength_status = _quantity_average_and_status(
            weapon.get("strength", ""),
            allow_trailing_plus=True,
        )
        damage_average, damage_status = _quantity_average_and_status(weapon.get("damage", ""))
        rows.append(
            {
                "faction": unit.get("faction", ""),
                "unit_name": unit.get("name", ""),
                "selection_type": unit.get("selection_type", ""),
                "unit_id": weapon.get("unit_id", ""),
                "source_file": weapon.get("source_file") or unit.get("source_file", ""),
                "unit_points": unit.get("points", ""),
                "models_min": unit.get("models_min", ""),
                "models_max": unit.get("models_max", ""),
                "weapon_id": weapon.get("weapon_id", ""),
                "weapon_name": weapon.get("name", ""),
                "weapon_type": weapon.get("weapon_type", ""),
                "attacks": weapon.get("attacks", ""),
                "skill": weapon.get("skill", ""),
                "strength": weapon.get("strength", ""),
                "ap": weapon.get("ap", ""),
                "damage": weapon.get("damage", ""),
                "attacks_average": _format_average(attacks_average),
                "strength_average": _format_average(strength_average),
                "damage_average": _format_average(damage_average),
                "attacks_parse_status": attacks_status,
                "strength_parse_status": strength_status,
                "damage_parse_status": damage_status,
                "raw_damage_throughput": _format_average(attacks_average * damage_average),
                "keywords": weapon.get("keywords", ""),
                "hit_modifier": weapon.get("hit_modifier", ""),
                "wound_modifier": weapon.get("wound_modifier", ""),
                "reroll_hits": weapon.get("reroll_hits", ""),
                "reroll_wounds": weapon.get("reroll_wounds", ""),
                "lethal_hits": weapon.get("lethal_hits", ""),
                "sustained_hits": weapon.get("sustained_hits", ""),
                "devastating_wounds": weapon.get("devastating_wounds", ""),
            }
        )
    return sorted(rows, key=lambda row: (row["faction"].casefold(), row["unit_name"].casefold(), row["weapon_name"].casefold()))


def build_suspicious_weapon_review_rows(weapon_rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for row in weapon_rows:
        reasons = _weapon_review_reasons(row)
        if not reasons:
            continue
        rows.append(
            {
                **row,
                "review_severity": _weapon_review_severity(row, reasons),
                "review_category": _weapon_review_category(row, reasons),
                "review_reason": "; ".join(reasons),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            0 if row["review_severity"] == "error" else 1,
            row["review_category"],
            -(_float_or_none(row.get("raw_damage_throughput")) or 0.0),
            row["faction"].casefold(),
            row["unit_name"].casefold(),
            row["weapon_name"].casefold(),
        ),
    )


def _weapon_review_reasons(row: Dict[str, str]) -> List[str]:
    reasons: List[str] = []
    attacks = _float_or_none(row.get("attacks_average")) or 0.0
    strength = _float_or_none(row.get("strength_average")) or 0.0
    damage = _float_or_none(row.get("damage_average")) or 0.0
    throughput = _float_or_none(row.get("raw_damage_throughput")) or 0.0
    ap = _int_or_none(row.get("ap"))
    for field, label in (
        ("attacks_parse_status", "attacks"),
        ("strength_parse_status", "strength"),
        ("damage_parse_status", "damage"),
    ):
        status = row.get(field) or "ok"
        if status != "ok":
            reasons.append(f"{status} {label} expression")
    if throughput <= 0:
        reasons.append("zero raw damage throughput")
    if attacks <= 0:
        reasons.append("zero attacks average")
    if strength <= 0:
        reasons.append("zero strength average")
    if damage <= 0:
        reasons.append("zero damage average")
    if throughput >= 50:
        reasons.append("very high raw damage throughput")
    if attacks >= 20:
        reasons.append("very high attacks average")
    if damage >= 10:
        reasons.append("very high damage average")
    if ap is not None and ap <= -5:
        reasons.append("extreme AP")
    return reasons


def _weapon_review_severity(row: Dict[str, str], reasons: Sequence[str]) -> str:
    error_reasons = {
        "empty attacks expression",
        "placeholder attacks expression",
        "unsupported attacks expression",
        "empty strength expression",
        "placeholder strength expression",
        "unsupported strength expression",
        "empty damage expression",
        "placeholder damage expression",
        "unsupported damage expression",
        "zero raw damage throughput",
        "zero attacks average",
        "zero strength average",
        "zero damage average",
    }
    if any(reason in error_reasons for reason in reasons):
        return "error"
    if _float_or_none(row.get("raw_damage_throughput")) == 0:
        return "error"
    if _is_expected_large_platform_extreme(row, reasons):
        return "info"
    return "warning"


def _weapon_review_category(row: Dict[str, str], reasons: Sequence[str]) -> str:
    damage_status = row.get("damage_parse_status") or "ok"
    if damage_status in {"empty", "placeholder"}:
        return "missing_damage"
    if damage_status != "ok":
        return "invalid_damage"
    if "zero damage average" in reasons or "zero raw damage throughput" in reasons:
        return "zero_damage"
    if any(reason in reasons for reason in ("empty attacks expression", "placeholder attacks expression", "unsupported attacks expression")):
        return "invalid_attacks"
    if any(reason in reasons for reason in ("empty strength expression", "placeholder strength expression", "unsupported strength expression")):
        return "invalid_strength"
    if any(reason.startswith("very high") or reason == "extreme AP" for reason in reasons):
        if _is_expected_large_platform_extreme(row, reasons):
            return "large_platform_profile"
        return "extreme_profile"
    return "other"


def _is_expected_large_platform_extreme(row: Dict[str, str], reasons: Sequence[str]) -> bool:
    if not reasons:
        return False
    unit_points = _int_or_none(row.get("unit_points"))
    if unit_points is None or unit_points < 300:
        return False
    return all(reason.startswith("very high") or reason == "extreme AP" for reason in reasons)


def build_unit_profile_review_rows(units: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for unit in units:
        reasons = _unit_profile_review_reasons(unit)
        category = _unit_profile_review_category(unit, reasons)
        rows.append(
            {
                "faction": unit.get("faction", ""),
                "unit_name": unit.get("name", ""),
                "selection_type": unit.get("selection_type", ""),
                "unit_id": unit.get("unit_id", ""),
                "source_file": unit.get("source_file", ""),
                "toughness": unit.get("toughness", ""),
                "save": unit.get("save", ""),
                "invulnerable_save": unit.get("invulnerable_save", ""),
                "wounds": unit.get("wounds", ""),
                "move": unit.get("move", ""),
                "leadership": unit.get("leadership", ""),
                "objective_control": unit.get("objective_control", ""),
                "points": unit.get("points", ""),
                "models_min": unit.get("models_min", ""),
                "models_max": unit.get("models_max", ""),
                "feel_no_pain": unit.get("feel_no_pain", ""),
                "damage_cap": unit.get("damage_cap", ""),
                "toughness_status": _positive_int_status(unit.get("toughness", "")),
                "save_status": _save_status(unit.get("save", "")),
                "wounds_status": _positive_int_status(unit.get("wounds", "")),
                "points_status": _optional_positive_int_status(unit.get("points", "")),
                "model_count_status": _model_count_status(unit),
                "review_severity": _unit_profile_review_severity(unit, reasons),
                "review_category": category,
                "review_reason": "; ".join(reasons),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            0 if row["review_severity"] == "error" else 1 if row["review_severity"] == "warning" else 2,
            row["faction"].casefold(),
            row["unit_name"].casefold(),
            row["unit_id"],
        ),
    )


def _unit_profile_review_reasons(unit: Dict[str, str]) -> List[str]:
    reasons: List[str] = []
    if _positive_int_status(unit.get("toughness", "")) != "ok":
        reasons.append("missing or invalid toughness")
    if _save_status(unit.get("save", "")) != "ok":
        reasons.append("missing or invalid save")
    if _positive_int_status(unit.get("wounds", "")) != "ok":
        reasons.append("missing or invalid wounds")
    points_status = _optional_positive_int_status(unit.get("points", ""))
    if points_status == "missing":
        reasons.append("missing points")
    elif points_status != "ok":
        reasons.append("invalid points")
    model_status = _model_count_status(unit)
    if model_status == "missing":
        reasons.append("missing model count")
    elif model_status == "invalid":
        reasons.append("invalid model count")
    return reasons


def _unit_profile_review_severity(unit: Dict[str, str], reasons: Sequence[str]) -> str:
    if any(reason.startswith("missing or invalid") or reason == "invalid model count" for reason in reasons):
        return "error"
    if reasons:
        if _unit_profile_review_category(unit, reasons) == "model_points_unset":
            return "info"
        return "warning"
    return ""


def _unit_profile_review_category(unit: Dict[str, str], reasons: Sequence[str]) -> str:
    if not reasons:
        return "ok"
    if any(reason.startswith("missing or invalid") for reason in reasons):
        return "core_stats"
    if any("model count" in reason for reason in reasons):
        return "model_count"
    if set(reasons).issubset({"missing points", "invalid points"}):
        selection_type = (unit.get("selection_type") or "").strip().lower()
        return "model_points_unset" if selection_type == "model" else "unit_points_unset"
    return "other"


def _positive_int_status(value: str) -> str:
    parsed = _int_or_none(value)
    if parsed is None:
        return "missing"
    return "ok" if parsed > 0 else "invalid"


def _optional_positive_int_status(value: str) -> str:
    if not str(value or "").strip():
        return "missing"
    return _positive_int_status(value)


def _save_status(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "missing"
    if cleaned.endswith("+") and cleaned[:-1].isdigit():
        parsed = int(cleaned[:-1])
        if 2 <= parsed <= 7:
            return "ok"
    return "invalid"


def _model_count_status(unit: Dict[str, str]) -> str:
    minimum = _int_or_none(unit.get("models_min"))
    maximum = _int_or_none(unit.get("models_max"))
    if minimum is None and maximum is None:
        return "missing"
    if minimum is not None and minimum <= 0:
        return "invalid"
    if maximum is not None and maximum <= 0:
        return "invalid"
    if minimum is not None and maximum is not None and minimum > maximum:
        return "invalid"
    return "ok"


def build_ability_review_rows(
    abilities: Iterable[Dict[str, str]],
    unit_by_id: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for ability in abilities:
        unit = unit_by_id.get(ability.get("source_id", ""), {}) if ability.get("source_type") == "unit" else {}
        rows.append(
            {
                "faction": unit.get("faction", ""),
                "unit_name": unit.get("name", ""),
                "selection_type": unit.get("selection_type", ""),
                "unit_id": unit.get("unit_id", ""),
                "source_file": ability.get("source_file") or unit.get("source_file", ""),
                "source_type": ability.get("source_type", ""),
                "source_id": ability.get("source_id", ""),
                "ability_id": ability.get("ability_id", ""),
                "ability_name": ability.get("name", ""),
                "text": ability.get("text", ""),
            }
        )
    return sorted(rows, key=lambda row: (row["faction"].casefold(), row["unit_name"].casefold(), row["ability_name"].casefold()))


def build_ability_modifier_review_rows(
    units: Iterable[Dict[str, str]],
    abilities: Iterable[Dict[str, str]],
) -> List[Dict[str, str]]:
    abilities_by_unit: Dict[str, List[Dict[str, str]]] = {}
    for ability in abilities:
        if (ability.get("source_type") or "").lower() != "unit":
            continue
        source_id = ability.get("source_id", "")
        if source_id:
            abilities_by_unit.setdefault(source_id, []).append(ability)

    rows: List[Dict[str, str]] = []
    for unit in units:
        unit_id = unit.get("unit_id", "")
        unit_abilities = abilities_by_unit.get(unit_id, [])
        if not unit_abilities:
            continue
        profile = UnitProfile.from_dict(
            {
                "unit_id": unit_id,
                "name": unit.get("name", ""),
                "toughness": unit.get("toughness") or 1,
                "save": unit.get("save") or "7+",
                "wounds": unit.get("wounds") or 1,
                "faction": unit.get("faction", ""),
                "selection_type": unit.get("selection_type", ""),
                "abilities": [
                    {"name": ability.get("name", ""), "text": ability.get("text", "")}
                    for ability in unit_abilities
                ],
            }
        )
        for modifier in profile.ability_modifiers:
            rows.append(
                {
                    **_ability_modifier_unit_context(unit),
                    "modifier_type": "attack_modifier",
                    "source": modifier.source,
                    "description": modifier.description,
                    "hit_modifier": str(modifier.hit_modifier),
                    "wound_modifier": str(modifier.wound_modifier),
                    "reroll_hits": modifier.reroll_hits,
                    "reroll_wounds": modifier.reroll_wounds,
                    "grants": _modifier_grants(modifier),
                    "anti_rules": "; ".join(f"{keyword}:{threshold}+" for keyword, threshold in modifier.anti_rules),
                    "ignores_cover": str(modifier.ignores_cover).lower(),
                    "applies_to_ranged": str(modifier.applies_to_ranged).lower(),
                    "applies_to_melee": str(modifier.applies_to_melee).lower(),
                    "target_keywords": "; ".join(sorted(modifier.target_keywords)),
                    "damage_reduction": "",
                }
            )
        for ability in unit_abilities:
            damage_reduction = _extract_damage_reduction_from_text(
                f"{ability.get('name', '')}. {ability.get('text', '')}"
            )
            if damage_reduction <= 0:
                continue
            rows.append(
                {
                    **_ability_modifier_unit_context(unit),
                    "modifier_type": "damage_reduction",
                    "source": ability.get("name", ""),
                    "description": ability.get("text", ""),
                    "hit_modifier": "",
                    "wound_modifier": "",
                    "reroll_hits": "",
                    "reroll_wounds": "",
                    "grants": "",
                    "anti_rules": "",
                    "ignores_cover": "",
                    "applies_to_ranged": "",
                    "applies_to_melee": "",
                    "target_keywords": "",
                    "damage_reduction": _format_average(damage_reduction),
                }
            )
    return sorted(rows, key=lambda row: (row["faction"].casefold(), row["unit_name"].casefold(), row["source"].casefold(), row["modifier_type"]))


def _ability_modifier_unit_context(unit: Dict[str, str]) -> Dict[str, str]:
    return {
        "faction": unit.get("faction", ""),
        "unit_name": unit.get("name", ""),
        "selection_type": unit.get("selection_type", ""),
        "unit_id": unit.get("unit_id", ""),
        "source_file": unit.get("source_file", ""),
    }


def _modifier_grants(modifier: object) -> str:
    grants = []
    for attr, label in (
        ("grant_twin_linked", "Twin-linked"),
        ("grant_torrent", "Torrent"),
        ("grant_blast", "Blast"),
        ("grant_assault", "Assault"),
    ):
        if getattr(modifier, attr, False):
            grants.append(label)
    return "; ".join(grants)


def build_unit_variant_review_rows(units: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    by_name: Dict[str, List[Dict[str, str]]] = {}
    for unit in units:
        name = (unit.get("name") or "").strip()
        if not name:
            continue
        by_name.setdefault(name.casefold(), []).append(unit)

    rows: List[Dict[str, str]] = []
    for variants in by_name.values():
        if len(variants) < 2:
            continue
        variant_count = str(len(variants))
        for unit in variants:
            rows.append(
                {
                    "unit_name": unit.get("name", ""),
                    "variant_count": variant_count,
                    "unit_id": unit.get("unit_id", ""),
                    "source_file": unit.get("source_file", ""),
                    "faction": unit.get("faction", ""),
                    "selection_type": unit.get("selection_type", ""),
                    "points": unit.get("points", ""),
                    "models_min": unit.get("models_min", ""),
                    "models_max": unit.get("models_max", ""),
                    "toughness": unit.get("toughness", ""),
                    "save": unit.get("save", ""),
                    "wounds": unit.get("wounds", ""),
                }
            )
    return sorted(rows, key=lambda row: (row["unit_name"].casefold(), row["faction"].casefold(), row["unit_id"]))


def build_unit_weapon_coverage_rows(
    units: Iterable[Dict[str, str]],
    weapons: Iterable[Dict[str, str]],
) -> List[Dict[str, str]]:
    counts: Dict[str, Counter[str]] = {}
    for weapon in weapons:
        unit_id = weapon.get("unit_id", "")
        if not unit_id:
            continue
        weapon_type = (weapon.get("weapon_type") or "").strip().lower()
        counts.setdefault(unit_id, Counter())[weapon_type] += 1

    rows: List[Dict[str, str]] = []
    for unit in units:
        unit_id = unit.get("unit_id", "")
        unit_counts = counts.get(unit_id, Counter())
        ranged = unit_counts.get("ranged", 0)
        melee = unit_counts.get("melee", 0)
        total = sum(unit_counts.values())
        if ranged and melee:
            coverage = "both"
        elif ranged:
            coverage = "ranged_only"
        elif melee:
            coverage = "melee_only"
        else:
            coverage = "no_weapons"
        rows.append(
            {
                "faction": unit.get("faction", ""),
                "unit_name": unit.get("name", ""),
                "selection_type": unit.get("selection_type", ""),
                "unit_id": unit_id,
                "source_file": unit.get("source_file", ""),
                "points": unit.get("points", ""),
                "models_min": unit.get("models_min", ""),
                "models_max": unit.get("models_max", ""),
                "total_weapons": str(total),
                "ranged_weapons": str(ranged),
                "melee_weapons": str(melee),
                "coverage": coverage,
            }
        )
    return sorted(rows, key=lambda row: (row["coverage"], row["faction"].casefold(), row["unit_name"].casefold(), row["unit_id"]))


def build_loadout_review_rows(weapon_coverage_rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for row in weapon_coverage_rows:
        reasons = _loadout_review_reasons(row)
        if not reasons:
            continue
        rows.append(
            {
                **row,
                "review_severity": _loadout_review_severity(row),
                "review_category": _loadout_review_category(row),
                "review_reason": "; ".join(reasons),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            0 if row["review_severity"] == "warning" else 1,
            row["review_category"],
            -int(row.get("total_weapons") or 0),
            row["faction"].casefold(),
            row["unit_name"].casefold(),
            row["unit_id"],
        ),
    )


def _loadout_review_reasons(row: Dict[str, str]) -> List[str]:
    total = int(row.get("total_weapons") or 0)
    ranged = int(row.get("ranged_weapons") or 0)
    melee = int(row.get("melee_weapons") or 0)
    reasons: List[str] = []
    if total >= 12:
        reasons.append("many imported weapon profiles")
    if ranged >= 10:
        reasons.append("many ranged profiles")
    if melee >= 10:
        reasons.append("many melee profiles")
    if ranged and melee and total >= 8:
        reasons.append("mixed loadout profiles")
    return reasons


def _loadout_review_severity(row: Dict[str, str]) -> str:
    category = _loadout_review_category(row)
    if category in {"crucible_profile", "legends_profile"}:
        return "info"
    return "warning"


def _loadout_review_category(row: Dict[str, str]) -> str:
    unit_name = row.get("unit_name", "")
    total = int(row.get("total_weapons") or 0)
    ranged = int(row.get("ranged_weapons") or 0)
    melee = int(row.get("melee_weapons") or 0)
    if "[Crucible]" in unit_name:
        return "crucible_profile"
    if "[Legends]" in unit_name:
        return "legends_profile"
    if total >= 12:
        return "many_profiles"
    if ranged and melee and total >= 8:
        return "mixed_profiles"
    if ranged >= 10:
        return "many_ranged_profiles"
    if melee >= 10:
        return "many_melee_profiles"
    return "other"


def build_source_catalogue_review_rows(
    units: Iterable[Dict[str, str]],
    weapon_rows: Iterable[Dict[str, str]],
    ability_rows: Iterable[Dict[str, str]],
    suspicious_weapon_rows: Iterable[Dict[str, str]],
    unit_profile_rows: Iterable[Dict[str, str]],
    loadout_rows: Iterable[Dict[str, str]],
    unit_variant_rows: Iterable[Dict[str, str]],
    weapon_coverage_rows: Iterable[Dict[str, str]],
    *,
    source_blob_base_url: str = "",
) -> List[Dict[str, str]]:
    units = list(units)
    weapon_rows = list(weapon_rows)
    ability_rows = list(ability_rows)
    suspicious_weapon_rows = list(suspicious_weapon_rows)
    unit_profile_rows = list(unit_profile_rows)
    loadout_rows = list(loadout_rows)
    unit_variant_rows = list(unit_variant_rows)
    weapon_coverage_rows = list(weapon_coverage_rows)

    all_sources = {
        _source_label(row.get("source_file", ""))
        for rows in (units, weapon_rows, ability_rows, suspicious_weapon_rows, unit_profile_rows, loadout_rows, unit_variant_rows, weapon_coverage_rows)
        for row in rows
    }
    faction_by_source: dict[str, set[str]] = {source: set() for source in all_sources}
    for unit in units:
        source = _source_label(unit.get("source_file", ""))
        faction = unit.get("faction") or ""
        if faction:
            faction_by_source.setdefault(source, set()).add(faction)

    unit_counts = Counter(_source_label(row.get("source_file", "")) for row in units)
    weapon_counts = Counter(_source_label(row.get("source_file", "")) for row in weapon_rows)
    ability_counts = Counter(_source_label(row.get("source_file", "")) for row in ability_rows)
    suspicious_counts = Counter(_source_label(row.get("source_file", "")) for row in suspicious_weapon_rows)
    unit_profile_issue_counts = Counter(
        _source_label(row.get("source_file", ""))
        for row in unit_profile_rows
        if row.get("review_severity")
    )
    loadout_counts = Counter(_source_label(row.get("source_file", "")) for row in loadout_rows)
    variant_counts = Counter(_source_label(row.get("source_file", "")) for row in unit_variant_rows)
    no_weapon_counts = Counter(
        _source_label(row.get("source_file", ""))
        for row in weapon_coverage_rows
        if row.get("coverage") == "no_weapons"
    )

    rows: List[Dict[str, str]] = []
    for source in all_sources:
        rows.append(
            {
                "source_file": source,
                "source_url": _source_blob_url(source_blob_base_url, source),
                "factions": "; ".join(sorted(faction_by_source.get(source, set()), key=str.casefold)),
                "units": str(unit_counts[source]),
                "weapon_profiles": str(weapon_counts[source]),
                "ability_profiles": str(ability_counts[source]),
                "suspicious_weapon_profiles": str(suspicious_counts[source]),
                "unit_profile_issue_rows": str(unit_profile_issue_counts[source]),
                "loadout_review_rows": str(loadout_counts[source]),
                "duplicate_name_unit_rows": str(variant_counts[source]),
                "no_weapon_units": str(no_weapon_counts[source]),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["units"]),
            -int(row["weapon_profiles"]),
            row["source_file"].casefold(),
        ),
    )


def _source_label(value: str) -> str:
    return (value or "").strip() or "<unknown source>"


def _source_blob_base_url(metadata_path: Path) -> str:
    if not metadata_path.exists():
        return ""
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    revisions = metadata.get("source_revisions")
    if not isinstance(revisions, list) or not revisions:
        return ""
    revision = revisions[0]
    if not isinstance(revision, dict):
        return ""
    remote = str(revision.get("remote_origin") or "")
    commit = str(revision.get("commit") or "")
    subdir = str(metadata.get("github_subdir") or "").strip("/")
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.split(":", 1)[1]
    if not remote.startswith("https://github.com/") or not commit:
        return ""
    base = f"{remote}/blob/{commit}/"
    if subdir:
        base += f"{quote(subdir, safe='/')}/"
    return base


def _source_blob_url(base_url: str, source: str) -> str:
    if not base_url or source == "<unknown source>":
        return ""
    return f"{base_url}{quote(source, safe='/')}"


def build_profile_review_markdown(
    units: List[Dict[str, str]],
    weapon_rows: List[Dict[str, str]],
    suspicious_weapon_rows: List[Dict[str, str]],
    ability_rows: List[Dict[str, str]],
    ability_modifier_rows: List[Dict[str, str]],
    unit_variant_rows: List[Dict[str, str]],
    weapon_coverage_rows: List[Dict[str, str]],
    loadout_rows: List[Dict[str, str]],
    unit_profile_rows: List[Dict[str, str]],
    source_catalogue_rows: List[Dict[str, str]],
) -> str:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    faction_counts = Counter(row.get("faction", "") or "<no faction>" for row in units)
    unit_weapon_counts = Counter(row.get("unit_name", "") or "<unknown unit>" for row in weapon_rows)
    variant_name_counts = Counter(row.get("unit_name", "") or "<unknown unit>" for row in unit_variant_rows)
    coverage_counts = Counter(row.get("coverage", "") or "<unknown>" for row in weapon_coverage_rows)
    modifier_type_counts = Counter(row.get("modifier_type", "") or "<unknown>" for row in ability_modifier_rows)
    unit_profile_issue_counts = Counter(row.get("review_severity") or "ok" for row in unit_profile_rows)
    unit_profile_category_counts = Counter(row.get("review_category") or "ok" for row in unit_profile_rows)
    unit_profile_reason_counts = Counter()
    for row in unit_profile_rows:
        for reason in (row.get("review_reason") or "").split("; "):
            if reason:
                unit_profile_reason_counts[reason] += 1

    lines = [
        "# Imported Profile Review",
        "",
        f"Generated: {generated_at}",
        "",
        "## Files",
        "",
        "- `weapon_profile_review.csv`: one row per imported weapon profile, joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.",
        "- `suspicious_weapon_review.csv`: filtered weapon profiles with zero or extreme parsed damage characteristics for manual inspection.",
        "- `unit_profile_review.csv`: one row per imported unit with core stat, points, and model-count validation for manual inspection.",
        "- `ability_profile_review.csv`: one row per imported ability profile, joined to unit name, faction, and source file where applicable.",
        "- `ability_modifier_review.csv`: one row per imported ability effect that the calculator turns into a modifier.",
        "- `unit_variant_review.csv`: one row per unit whose name appears more than once, preserving IDs, faction context, and source file.",
        "- `unit_weapon_coverage_review.csv`: one row per unit showing ranged/melee weapon counts and coverage category.",
        "- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need manual loadout selection.",
        "- `source_catalogue_review.csv`: one row per BSData source catalogue with imported row counts, review-risk counts, and exact upstream GitHub file URLs when metadata is available.",
        "",
        "## Counts",
        "",
        "| Item | Count |",
        "| --- | ---: |",
        f"| Units | {len(units)} |",
        f"| Weapon profiles | {len(weapon_rows)} |",
        f"| Suspicious weapon profiles | {len(suspicious_weapon_rows)} |",
        f"| Unit profile review rows | {len(unit_profile_rows)} |",
        f"| Unit profile issue rows | {sum(count for severity, count in unit_profile_issue_counts.items() if severity != 'ok')} |",
        f"| Ability profiles | {len(ability_rows)} |",
        f"| Ability modifier rows | {len(ability_modifier_rows)} |",
        f"| Duplicate-name unit rows | {len(unit_variant_rows)} |",
        f"| Weapon coverage rows | {len(weapon_coverage_rows)} |",
        f"| Loadout review rows | {len(loadout_rows)} |",
        f"| Source catalogue rows | {len(source_catalogue_rows)} |",
        "",
        "## Largest Factions",
        "",
        "| Faction | Units |",
        "| --- | ---: |",
    ]
    for faction, count in faction_counts.most_common(12):
        lines.append(f"| {faction} | {count} |")

    lines.extend(
        [
            "",
            "## Source Catalogue Coverage",
            "",
            "| Source File | Factions | Units | Weapons | Suspicious Weapons | Unit Issues | Loadout Rows |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in source_catalogue_rows[:12]:
        source_label = _markdown_link(row["source_file"], row.get("source_url", ""))
        lines.append(
            f"| {source_label} | {_markdown_cell(row['factions'])} "
            f"| {row['units']} | {row['weapon_profiles']} "
            f"| {row['suspicious_weapon_profiles']} | {row['unit_profile_issue_rows']} "
            f"| {row['loadout_review_rows']} |"
        )

    lines.extend(
        [
            "",
            "## Units With Most Weapon Profiles",
            "",
            "| Unit | Weapon Profiles |",
            "| --- | ---: |",
        ]
    )
    for unit_name, count in unit_weapon_counts.most_common(12):
        lines.append(f"| {unit_name} | {count} |")

    high_throughput = sorted(
        (
            row
            for row in weapon_rows
            if _float_or_none(row.get("raw_damage_throughput")) is not None
        ),
        key=lambda row: _float_or_none(row.get("raw_damage_throughput")) or 0.0,
        reverse=True,
    )
    lines.extend(
        [
            "",
            "## Highest Raw Damage Throughput",
            "",
            "| Unit | Weapon | Raw Throughput |",
            "| --- | --- | ---: |",
        ]
    )
    for row in high_throughput[:12]:
        lines.append(f"| {row['unit_name']} | {row['weapon_name']} | {row['raw_damage_throughput']} |")

    suspicious_reason_counts = Counter()
    suspicious_severity_counts = Counter(row.get("review_severity") or "unknown" for row in suspicious_weapon_rows)
    suspicious_category_counts = Counter(row.get("review_category") or "unknown" for row in suspicious_weapon_rows)
    for row in suspicious_weapon_rows:
        for reason in (row.get("review_reason") or "").split("; "):
            if reason:
                suspicious_reason_counts[reason] += 1
    lines.extend(
        [
            "",
            "## Suspicious Weapon Review Reasons",
            "",
            "| Reason | Rows |",
            "| --- | ---: |",
        ]
    )
    if suspicious_reason_counts:
        for reason, count in suspicious_reason_counts.most_common():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Suspicious Weapon Severity",
            "",
            "| Severity | Rows |",
            "| --- | ---: |",
        ]
    )
    if suspicious_severity_counts:
        for severity, count in sorted(suspicious_severity_counts.items()):
            lines.append(f"| {severity} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Suspicious Weapon Categories",
            "",
            "| Category | Rows |",
            "| --- | ---: |",
        ]
    )
    if suspicious_category_counts:
        for category, count in sorted(suspicious_category_counts.items()):
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Unit Profile Validation",
            "",
            "| Severity | Rows |",
            "| --- | ---: |",
        ]
    )
    for severity, count in sorted(unit_profile_issue_counts.items()):
        lines.append(f"| {severity} | {count} |")

    lines.extend(
        [
            "",
            "## Unit Profile Review Reasons",
            "",
            "| Reason | Rows |",
            "| --- | ---: |",
        ]
    )
    if unit_profile_reason_counts:
        for reason, count in unit_profile_reason_counts.most_common():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Unit Profile Review Categories",
            "",
            "| Category | Rows |",
            "| --- | ---: |",
        ]
    )
    for category, count in sorted(unit_profile_category_counts.items()):
        lines.append(f"| {category} | {count} |")


    lines.extend(
        [
            "",
            "## Derived Ability Modifiers",
            "",
            "| Modifier Type | Rows |",
            "| --- | ---: |",
        ]
    )
    if modifier_type_counts:
        for modifier_type, count in sorted(modifier_type_counts.items()):
            lines.append(f"| {modifier_type} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Duplicate Unit Names",
            "",
            "| Unit Name | Variants |",
            "| --- | ---: |",
        ]
    )
    if variant_name_counts:
        for unit_name, count in variant_name_counts.most_common(12):
            lines.append(f"| {unit_name} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Unit Weapon Coverage",
            "",
            "| Coverage | Units |",
            "| --- | ---: |",
        ]
    )
    for coverage, count in sorted(coverage_counts.items()):
        lines.append(f"| {coverage} | {count} |")

    loadout_reason_counts = Counter()
    loadout_severity_counts = Counter(row.get("review_severity") or "unknown" for row in loadout_rows)
    loadout_category_counts = Counter(row.get("review_category") or "unknown" for row in loadout_rows)
    for row in loadout_rows:
        for reason in (row.get("review_reason") or "").split("; "):
            if reason:
                loadout_reason_counts[reason] += 1
    lines.extend(
        [
            "",
            "## Loadout Review Reasons",
            "",
            "| Reason | Rows |",
            "| --- | ---: |",
        ]
    )
    if loadout_reason_counts:
        for reason, count in loadout_reason_counts.most_common():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Loadout Review Severity",
            "",
            "| Severity | Rows |",
            "| --- | ---: |",
        ]
    )
    if loadout_severity_counts:
        for severity, count in sorted(loadout_severity_counts.items()):
            lines.append(f"| {severity} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend(
        [
            "",
            "## Loadout Review Categories",
            "",
            "| Category | Rows |",
            "| --- | ---: |",
        ]
    )
    if loadout_category_counts:
        for category, count in sorted(loadout_category_counts.items()):
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.append("")
    return "\n".join(lines)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _quantity_average(value: str, *, allow_trailing_plus: bool = False) -> float:
    average, _status = _quantity_average_and_status(value, allow_trailing_plus=allow_trailing_plus)
    return average


def _quantity_average_and_status(value: str, *, allow_trailing_plus: bool = False) -> tuple[float, str]:
    cleaned = (value or "").strip()
    if not cleaned:
        return 0.0, "empty"
    if _is_placeholder_quantity(cleaned):
        return 0.0, "placeholder"
    if allow_trailing_plus and cleaned.endswith("+") and cleaned[:-1].isdigit():
        cleaned = cleaned[:-1]
    try:
        return parse_quantity(cleaned).average, "ok"
    except QuantityParseError:
        return 0.0, "unsupported"


def _is_placeholder_quantity(value: str) -> bool:
    cleaned = value.strip()
    return cleaned in {"*", "-", "—", "â€”"} or cleaned.lower() in {"n/a", "na", "none"}


def _markdown_cell(value: str) -> str:
    return str(value).replace("|", "/")


def _markdown_link(label: str, url: str) -> str:
    label = _markdown_cell(label)
    if not url:
        return label
    return f"[{label}]({url})"


def _format_average(value: float) -> str:
    return f"{value:.2f}"


def _float_or_none(value: Optional[str]) -> Optional[float]:
    try:
        return float(value or "")
    except ValueError:
        return None


def _int_or_none(value: Optional[str]) -> Optional[int]:
    try:
        return int(value or "")
    except ValueError:
        return None


def _write_csv(path: Path, headers: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate joined CSVs for manual review of imported profiles")
    parser.add_argument("--csv-dir", type=Path, default=Path("data/latest"), help="Directory containing importer CSVs")
    args = parser.parse_args(argv)

    counts = write_profile_review(args.csv_dir)
    print(
        f"Wrote profile review files for {counts['units']} units, "
        f"{counts['weapon_profiles']} weapons, {counts['ability_profiles']} abilities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
