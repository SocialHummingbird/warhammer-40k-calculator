from __future__ import annotations

from typing import Any

from .profiles import UnitProfile


def unit_factions(units: Any) -> list[str]:
    return sorted({unit.faction for unit in units if unit.faction}, key=str.casefold)


def search_units(units: Any, *, text: str = "", faction: str = "", limit: int = 300) -> list[UnitProfile]:
    needle = (text or "").casefold().strip()
    faction_key = (faction or "").casefold().strip()
    matches = []
    for unit in sorted(units, key=lambda item: item.name.casefold()):
        if faction_key and (unit.faction or "").casefold() != faction_key:
            continue
        if needle:
            searchable = " ".join([unit.name, unit.faction or "", *unit.keywords]).casefold()
            if needle not in searchable:
                continue
        matches.append(unit)
        if len(matches) >= limit:
            break
    return matches
