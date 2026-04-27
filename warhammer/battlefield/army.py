from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List

from ..matchup_payloads import unit_summary
from ..profiles import UnitProfile
from .models import ArmyList, ArmyUnit, army_from_dict, to_dict


def validate_army_payload(payload: Dict[str, Any], units_by_id: Dict[str, UnitProfile]) -> Dict[str, Any]:
    army = army_from_dict(payload.get("army") or payload)
    return validate_army(army, units_by_id)


def validate_army(army: ArmyList, units_by_id: Dict[str, UnitProfile]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    total_points = 0
    units_payload = []
    names = []

    if army.side not in {"red", "blue"}:
        errors.append("Army side must be red or blue.")

    for index, entry in enumerate(army.units):
        if not entry.unit_id:
            errors.append(f"Unit row {index + 1} has no unit id.")
            continue
        unit = units_by_id.get(entry.unit_id)
        if unit is None:
            errors.append(f"Unknown unit id {entry.unit_id}.")
            continue
        count = max(1, entry.count)
        names.append(unit.name)
        if unit.points is None:
            warnings.append(f"{unit.name} has no points value.")
        else:
            total_points += unit.points * count
        if not unit.weapons:
            warnings.append(f"{unit.name} has no imported weapon profiles.")
        if unit.abilities:
            warnings.append(f"{unit.name} may have unsupported special rules in battlefield mode.")
        units_payload.append(
            {
                "entry": to_dict(entry),
                "unit": unit_summary(unit),
                "count": count,
                "points": (unit.points * count if unit.points is not None else None),
            }
        )

    duplicate_names = [name for name, count in Counter(names).items() if count > 1]
    for name in duplicate_names:
        warnings.append(f"Duplicate unit name in list: {name}.")

    return {
        "ok": not errors,
        "army": to_dict(army),
        "points": total_points,
        "unit_count": sum(max(1, entry.count) for entry in army.units),
        "units": units_payload,
        "errors": errors,
        "warnings": warnings,
    }


def units_by_id_from_units(units: Iterable[UnitProfile]) -> Dict[str, UnitProfile]:
    return {unit.unit_id: unit for unit in units if unit.unit_id}


def army_units_from_payload(rows: Iterable[Dict[str, Any]]) -> List[ArmyUnit]:
    return [ArmyUnit(unit_id=str(row.get("unit_id") or row.get("id") or ""), count=max(1, int(row.get("count") or 1))) for row in rows]
