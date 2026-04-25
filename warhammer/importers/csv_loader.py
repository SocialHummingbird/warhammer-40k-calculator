"""Helpers for loading importer CSV outputs into UnitProfile objects."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..profiles import UnitProfile


def load_units_from_directory(directory: Path) -> Dict[str, UnitProfile]:
    """Load units from a directory containing importer CSV outputs."""

    directory = Path(directory)
    unit_rows = _read_csv(directory / "units.csv")
    weapon_rows = _read_csv(directory / "weapons.csv")
    ability_rows = _read_csv(directory / "abilities.csv")
    keyword_rows = _read_csv(directory / "keywords.csv")
    unit_keyword_rows = _read_csv(directory / "unit_keywords.csv")

    units: Dict[str, Dict] = {}
    for row in unit_rows:
        unit_id = row["unit_id"]
        units[unit_id] = {
            "name": row["name"],
            "toughness": _to_int(row.get("toughness"), default=1),
            "save": row.get("save") or "7+",
            "wounds": _to_int(row.get("wounds"), default=1),
            "move": _to_optional_float(row.get("move")),
            "invulnerable_save": row.get("invulnerable_save") or None,
            "feel_no_pain": row.get("feel_no_pain") or None,
            "damage_cap": row.get("damage_cap") or None,
            "points": _to_optional_int(row.get("points")),
            "models_min": _to_optional_int(row.get("models_min")),
            "models_max": _to_optional_int(row.get("models_max")),
            "faction": row.get("faction") or None,
            "selection_type": (row.get("selection_type") or None),
            "leadership": _to_optional_int(row.get("leadership")),
            "objective_control": _to_optional_int(row.get("objective_control")),
            "weapons": [],
            "abilities": [],
            "keywords": [],
        }

    for row in weapon_rows:
        unit_id = row.get("unit_id")
        if unit_id not in units:
            continue
        weapon_data = {
            "name": row.get("name", "Unnamed Weapon"),
            "type": (row.get("weapon_type") or "ranged").lower(),
            "attacks": row.get("attacks") or "0",
            "skill": row.get("skill") or "6+",
            "strength": row.get("strength") or 0,
            "ap": row.get("ap") or 0,
            "damage": row.get("damage") or "1",
            "hit_modifier": row.get("hit_modifier") or "0",
            "wound_modifier": row.get("wound_modifier") or "0",
            "keywords": row.get("keywords") or "",
            "reroll_hits": row.get("reroll_hits") or "none",
            "reroll_wounds": row.get("reroll_wounds") or "none",
            "lethal_hits": row.get("lethal_hits") or "",
            "sustained_hits": row.get("sustained_hits") or "0",
            "devastating_wounds": row.get("devastating_wounds") or "",
        }
        units[unit_id]["weapons"].append(weapon_data)

    for row in ability_rows:
        if row.get("source_type", "").lower() != "unit":
            continue
        unit_id = row.get("source_id")
        if unit_id not in units:
            continue
        units[unit_id]["abilities"].append({"name": row.get("name", ""), "text": row.get("text", "")})

    keyword_lookup = {row.get("keyword_id"): row.get("keyword") for row in keyword_rows if row.get("keyword_id")}
    for row in unit_keyword_rows:
        unit_id = row.get("unit_id")
        keyword_id = row.get("keyword_id")
        keyword = keyword_lookup.get(keyword_id)
        if unit_id in units and keyword:
            units[unit_id]["keywords"].append(keyword)

    # Infer invulnerable saves from abilities when the units.csv column is empty
    for payload in units.values():
        invul = (payload.get("invulnerable_save") or "").strip()
        if invul:
            continue
        texts: List[str] = []
        for ability in payload.get("abilities", []):
            name = (ability.get("name") or "")
            text = (ability.get("text") or "")
            if "invulnerable" in name.lower() or "invulnerable" in text.lower():
                texts.append(f"{name}: {text}")
        if not texts:
            continue
        best = _extract_best_invulnerable_from_text("\n".join(texts))
        if best is not None:
            payload["invulnerable_save"] = f"{best}+"

    profiles: Dict[str, UnitProfile] = {}
    for unit_id, payload in units.items():
        unit_dict = {
            "name": payload["name"],
            "toughness": payload["toughness"],
            "save": payload["save"],
            "wounds": payload["wounds"],
            "move": payload.get("move"),
            "invulnerable_save": payload["invulnerable_save"],
            "feel_no_pain": payload["feel_no_pain"],
            "damage_cap": payload["damage_cap"],
            "points": payload.get("points"),
            "models_min": payload.get("models_min"),
            "models_max": payload.get("models_max"),
            "faction": payload.get("faction"),
            "selection_type": payload.get("selection_type"),
            "leadership": payload.get("leadership"),
            "objective_control": payload.get("objective_control"),
            "weapons": payload["weapons"],
            "abilities": payload["abilities"],
            "keywords": payload["keywords"],
        }
        profile = UnitProfile.from_dict(unit_dict)
        profiles[unit_id] = profile

    return profiles


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _to_int(value: Optional[str], *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None



def _to_optional_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().strip('"').strip("'")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def _extract_best_invulnerable_from_text(text: str) -> Optional[int]:
    """Extract the strongest (lowest) invulnerable save roll mentioned in text.

    Looks for patterns like '4+ invulnerable save' or 'invulnerable save ... 4+' and
    returns the smallest value found (2-6). Returns None if no match.
    """
    if not text:
        return None
    # Pattern where 'invulnerable' precedes the roll value
    p1 = re.compile(r"(?i)invulnerable[^\d]{0,50}?([2-6])\s*\+")
    # Pattern where the roll value precedes 'invulnerable'
    p2 = re.compile(r"([2-6])\s*\+[^\d]{0,50}?invulnerable", re.IGNORECASE)
    candidates: List[int] = []
    candidates += [int(m.group(1)) for m in p1.finditer(text)]
    candidates += [int(m.group(1)) for m in p2.finditer(text)]
    if not candidates:
        return None
    return min(candidates)

