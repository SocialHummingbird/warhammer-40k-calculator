"""BattleScribe / BSData catalogue importer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .schema import AbilityRow, KeywordRow, UnitKeywordRow, UnitRow, WeaponRow


CatalogueRows = Tuple[
    List[UnitRow],
    List[WeaponRow],
    List[AbilityRow],
    List[KeywordRow],
    List[UnitKeywordRow],
]


def _strip_namespace(element: ET.Element) -> None:
    """Recursively remove XML namespace prefixes in-place."""

    tag = getattr(element, "tag", None)
    if isinstance(tag, str) and tag.startswith("{"):
        element.tag = tag.split("}", 1)[1]
    for child in list(element):
        _strip_namespace(child)


def _profile_count(entry: ET.Element) -> int:
    return len(entry.findall("profiles/profile"))


def _build_selection_entry_lookup(root: ET.Element) -> Dict[str, ET.Element]:
    lookup: Dict[str, ET.Element] = {}
    for entry in root.findall(".//selectionEntry"):
        entry_id = entry.get("id")
        if not entry_id:
            continue
        existing = lookup.get(entry_id)
        if existing is None or _profile_count(entry) > _profile_count(existing):
            lookup[entry_id] = entry
    return lookup


def _build_selection_group_lookup(root: ET.Element) -> Dict[str, ET.Element]:
    groups: Dict[str, ET.Element] = {}
    for group in root.findall(".//selectionEntryGroup"):
        group_id = group.get("id")
        if group_id:
            groups[group_id] = group
    return groups


def _ids_from_group(group: ET.Element, entry_lookup: Dict[str, ET.Element], group_lookup: Dict[str, ET.Element]) -> List[str]:
    ids: List[str] = []
    for child in group.findall("selectionEntries/selectionEntry"):
        child_id = child.get("targetId") or child.get("id")
        if child_id:
            ids.append(child_id)
    for subgroup in group.findall("selectionEntryGroups/selectionEntryGroup"):
        ids.extend(_ids_from_group(subgroup, entry_lookup, group_lookup))
    for link in group.findall("entryLinks/entryLink"):
        target = link.get("targetId")
        if not target:
            continue
        if target in entry_lookup:
            ids.append(target)
        elif target in group_lookup:
            ids.extend(_ids_from_group(group_lookup[target], entry_lookup, group_lookup))
    return ids


def _child_selection_ids(element: ET.Element, entry_lookup: Dict[str, ET.Element], group_lookup: Dict[str, ET.Element]) -> List[str]:
    ids: List[str] = []
    for child in element.findall("selectionEntries/selectionEntry"):
        child_id = child.get("targetId") or child.get("id")
        if child_id:
            ids.append(child_id)
    for group in element.findall("selectionEntryGroups/selectionEntryGroup"):
        ids.extend(_ids_from_group(group, entry_lookup, group_lookup))
    for link in element.findall("entryLinks/entryLink"):
        target = link.get("targetId")
        if not target:
            continue
        if target in entry_lookup:
            ids.append(target)
        elif target in group_lookup:
            ids.extend(_ids_from_group(group_lookup[target], entry_lookup, group_lookup))
    return ids


def _collect_related_entries(entry_lookup: Dict[str, ET.Element], group_lookup: Dict[str, ET.Element], unit_entry: ET.Element) -> Iterable[ET.Element]:
    start_ids: List[str] = []
    unit_id = unit_entry.get("id")
    if unit_id:
        start_ids.append(unit_id)
    start_ids.extend(_child_selection_ids(unit_entry, entry_lookup, group_lookup))

    seen: set[str] = set()
    stack = list(start_ids)
    while stack:
        entry_id = stack.pop()
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        entry = entry_lookup.get(entry_id)
        if entry is None:
            continue
        yield entry
        stack.extend(_child_selection_ids(entry, entry_lookup, group_lookup))


def import_catalogues(paths: Sequence[Path]) -> CatalogueRows:
    units: List[UnitRow] = []
    weapons: List[WeaponRow] = []
    abilities: List[AbilityRow] = []
    keyword_lookup: Dict[str, KeywordRow] = {}
    unit_keywords: List[UnitKeywordRow] = []
    processed_units: set[str] = set()
    processed_units: set[str] = set()

    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            sub_paths = sorted(path.rglob("*.cat")) + sorted(path.rglob("*.gst"))
            sub_units, sub_weapons, sub_abilities, sub_keywords, sub_unit_keywords = import_catalogues(sub_paths)
            units.extend(sub_units)
            weapons.extend(sub_weapons)
            abilities.extend(sub_abilities)
            unit_keywords.extend(sub_unit_keywords)
            for keyword in sub_keywords:
                keyword_lookup.setdefault(keyword.keyword, keyword)
            continue

        parsed_units, parsed_weapons, parsed_abilities, parsed_keywords, parsed_unit_keywords = _parse_catalogue(path)
        units.extend(parsed_units)
        weapons.extend(parsed_weapons)
        abilities.extend(parsed_abilities)
        unit_keywords.extend(parsed_unit_keywords)
        for keyword in parsed_keywords:
            keyword_lookup.setdefault(keyword.keyword, keyword)

    keywords = list(keyword_lookup.values())
    keywords.sort(key=lambda row: row.keyword)
    unit_keywords.sort(key=lambda row: (row.unit_id, row.keyword_id))
    return units, weapons, abilities, keywords, unit_keywords


def _parse_catalogue(path: Path) -> CatalogueRows:
    tree = ET.parse(path)
    root = tree.getroot()
    _strip_namespace(root)
    faction = root.get("name", path.stem)

    entry_lookup = _build_selection_entry_lookup(root)
    group_lookup = _build_selection_group_lookup(root)

    units: List[UnitRow] = []
    weapons: List[WeaponRow] = []
    abilities: List[AbilityRow] = []
    keyword_rows: Dict[str, KeywordRow] = {}
    unit_keywords: List[UnitKeywordRow] = []
    processed_units: set[str] = set()

    for selection in root.findall(".//selectionEntry"):
        if selection.get("type") != "unit":
            continue

        unit_id = selection.get("id") or _slugify(selection.get("name", "unit"))
        if unit_id in processed_units:
            continue
        processed_units.add(unit_id)
        stats = _extract_characteristics(selection.findall("profiles/profile[@typeName='Unit']"))
        keywords = _collect_keywords(selection)

        units.append(
            UnitRow(
                unit_id=unit_id,
                faction=faction,
                name=selection.get("name", "Unnamed Unit"),
                toughness=_safe_int(stats.get("Toughness")),
                save=_clean_stat(stats.get("Save")),
                invulnerable_save=_clean_stat(stats.get("Invulnerable Save")),
                wounds=_safe_int(stats.get("Wounds")),
                leadership=_clean_stat(stats.get("Leadership")),
                objective_control=_safe_int(stats.get("Objective Control")) or _safe_int(stats.get("OC")),
                feel_no_pain=_clean_stat(stats.get("Feel No Pain")) or None,
                damage_cap=_clean_stat(stats.get("Damage Cap")) or None,
            )
        )

        seen_keyword_ids = set()
        for keyword in keywords:
            keyword_entry = keyword_rows.setdefault(
                keyword,
                KeywordRow(keyword_id=_slugify(keyword), keyword=keyword, description=""),
            )
            if keyword_entry.keyword_id not in seen_keyword_ids:
                unit_keywords.append(UnitKeywordRow(unit_id=unit_id, keyword_id=keyword_entry.keyword_id))
                seen_keyword_ids.add(keyword_entry.keyword_id)

        weapon_profile_types = {"weapon", "weapons", "ranged weapon", "ranged weapons", "melee weapon", "melee weapons"}
        ability_profile_types = {"ability", "abilities"}
        weapon_seen: set[tuple[str, str]] = set()
        ability_seen: set[tuple[str, str]] = set()
        for entry in _collect_related_entries(entry_lookup, group_lookup, selection):
            entry_id = entry.get("id") or ""
            for profile in entry.findall("profiles/profile"):
                type_name = (profile.get("typeName") or "").strip().lower()
                if type_name in weapon_profile_types:
                    weapon_key = (entry_id, profile.get("name") or "")
                    if weapon_key in weapon_seen:
                        continue
                    weapon_row = _weapon_from_profile(profile, unit_id)
                    if weapon_row:
                        weapons.append(weapon_row)
                        weapon_seen.add(weapon_key)
                elif type_name in ability_profile_types:
                    ability_row = _ability_from_profile(profile, source_type="unit", source_id=unit_id)
                    if ability_row:
                        ability_key = (ability_row.name, ability_row.text)
                        if ability_key in ability_seen:
                            continue
                        abilities.append(ability_row)
                        ability_seen.add(ability_key)

    units.sort(key=lambda row: (row.faction, row.name))
    weapons.sort(key=lambda row: (row.unit_id, row.name))
    abilities.sort(key=lambda row: (row.source_id, row.name))
    keywords = list(keyword_rows.values())
    keywords.sort(key=lambda row: row.keyword)
    unit_keywords.sort(key=lambda row: (row.unit_id, row.keyword_id))

    return units, weapons, abilities, keywords, unit_keywords


def _weapon_from_profile(profile: ET.Element, unit_id: str) -> Optional[WeaponRow]:
    name = profile.get("name")
    characteristics = _extract_characteristics([profile])

    if not name:
        return None

    attacks = characteristics.get("Attacks") or characteristics.get("A") or ""
    strength = characteristics.get("Strength") or characteristics.get("S") or ""
    ap = characteristics.get("AP") or characteristics.get("Armor Piercing") or ""
    damage = characteristics.get("Damage") or characteristics.get("D") or ""
    keywords = characteristics.get("Keywords") or ""

    skill = (
        characteristics.get("Ballistic Skill")
        or characteristics.get("BS")
        or characteristics.get("Weapon Skill")
        or characteristics.get("WS")
        or ""
    )

    range_value = characteristics.get("Range") or ""
    weapon_type = "melee" if range_value.lower() in {"melee", ""} and not range_value.strip("0123456789") else "ranged"

    return WeaponRow(
        weapon_id=f"{unit_id}:{_slugify(name)}",
        unit_id=unit_id,
        name=name,
        weapon_type=weapon_type,
        attacks=attacks,
        skill=skill,
        strength=strength,
        ap=ap,
        damage=damage,
        keywords=keywords,
        reroll_hits=characteristics.get("Reroll Hits", ""),
        reroll_wounds=characteristics.get("Reroll Wounds", ""),
        lethal_hits=characteristics.get("Lethal Hits", ""),
        sustained_hits=characteristics.get("Sustained Hits", ""),
        devastating_wounds=characteristics.get("Devastating Wounds", ""),
    )


def _ability_from_profile(profile: ET.Element, *, source_type: str, source_id: str) -> Optional[AbilityRow]:
    name = profile.get("name")
    if not name:
        return None

    characteristics = _extract_characteristics([profile])
    text = characteristics.get("Description") or characteristics.get("Text") or ""

    return AbilityRow(
        ability_id=f"{source_id}:{_slugify(name)}",
        source_type=source_type,
        source_id=source_id,
        name=name,
        text=text.strip(),
    )


def _extract_characteristics(profiles: Iterable[ET.Element]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for profile in profiles:
        characteristics = profile.find("characteristics")
        if characteristics is None:
            continue
        for characteristic in characteristics.findall("characteristic"):
            label = characteristic.get("name")
            if not label:
                continue
            value = (characteristic.text or "").strip()
            data[label] = value
    return data


def _collect_keywords(selection: ET.Element) -> List[str]:
    keywords: List[str] = []
    for link in selection.findall("categoryLinks/categoryLink"):
        name = link.get("name")
        if name:
            keywords.append(name)
    text_characteristics = _extract_characteristics(selection.findall("profiles/profile[@typeName='Keywords']"))
    if "Keywords" in text_characteristics:
        keywords.extend(k.strip() for k in text_characteristics["Keywords"].split(",") if k.strip())
    return keywords


def _clean_stat(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    return value or None


def _safe_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _slugify(value: str) -> str:
    return "-".join(value.lower().split())
