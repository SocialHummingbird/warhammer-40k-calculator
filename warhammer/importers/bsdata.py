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


def _build_parent_lookup(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    parents: Dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in list(parent):
            parents[child] = parent
    return parents


def _build_child_model_reference_ids(root: ET.Element, parent_lookup: Dict[ET.Element, ET.Element]) -> set[str]:
    ids: set[str] = set()
    for link in root.findall(".//entryLink"):
        target_id = link.get("targetId")
        if not target_id:
            continue
        current = parent_lookup.get(link)
        while current is not None:
            if current.tag == "selectionEntry" and (current.get("type") or "").strip().lower() in {"unit", "model"}:
                ids.add(target_id)
                break
            current = parent_lookup.get(current)
    return ids


def _direct_comment_text(element: ET.Element) -> str:
    return " ".join((comment.text or "") for comment in element.findall("comment")).casefold()


def _is_crusade_variant_unit(element: ET.Element) -> bool:
    return "crusade variant" in _direct_comment_text(element)


def _is_crusade_or_optional_modifier_node(element: ET.Element) -> bool:
    name = (element.get("name") or "").strip().lower()
    if name in {"crusade", "weapon modifications", "crusade relics"}:
        return True
    if "crusade relic" in name:
        return True
    comment_text = _direct_comment_text(element)
    if "crusade content" in comment_text or "crusade variant" in comment_text:
        return True
    for category in element.findall("categoryLinks/categoryLink"):
        category_name = (category.get("name") or "").casefold()
        if "enhancement / crusade relic" in category_name:
            return True
    return False


def _ids_from_group(group: ET.Element, entry_lookup: Dict[str, ET.Element], group_lookup: Dict[str, ET.Element]) -> List[str]:
    if _is_crusade_or_optional_modifier_node(group):
        return []
    ids: List[str] = []
    for child in group.findall("selectionEntries/selectionEntry"):
        if _is_crusade_or_optional_modifier_node(child):
            continue
        child_id = child.get("targetId") or child.get("id")
        if child_id:
            ids.append(child_id)
    for subgroup in group.findall("selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_or_optional_modifier_node(subgroup):
            continue
        ids.extend(_ids_from_group(subgroup, entry_lookup, group_lookup))
    for link in group.findall("entryLinks/entryLink"):
        if _is_crusade_or_optional_modifier_node(link):
            continue
        target = link.get("targetId")
        if not target:
            continue
        if target in entry_lookup:
            if not _is_crusade_or_optional_modifier_node(entry_lookup[target]):
                ids.append(target)
        elif target in group_lookup:
            target_group = group_lookup[target]
            if not _is_crusade_or_optional_modifier_node(target_group):
                ids.extend(_ids_from_group(target_group, entry_lookup, group_lookup))
    return ids


def _child_selection_ids(element: ET.Element, entry_lookup: Dict[str, ET.Element], group_lookup: Dict[str, ET.Element]) -> List[str]:
    ids: List[str] = []
    for child in element.findall("selectionEntries/selectionEntry"):
        if _is_crusade_or_optional_modifier_node(child):
            continue
        child_id = child.get("targetId") or child.get("id")
        if child_id:
            ids.append(child_id)
    for group in element.findall("selectionEntryGroups/selectionEntryGroup"):
        if _is_crusade_or_optional_modifier_node(group):
            continue
        ids.extend(_ids_from_group(group, entry_lookup, group_lookup))
    for link in element.findall("entryLinks/entryLink"):
        if _is_crusade_or_optional_modifier_node(link):
            continue
        target = link.get("targetId")
        if not target:
            continue
        if target in entry_lookup:
            if not _is_crusade_or_optional_modifier_node(entry_lookup[target]):
                ids.append(target)
        elif target in group_lookup:
            target_group = group_lookup[target]
            if not _is_crusade_or_optional_modifier_node(target_group):
                ids.extend(_ids_from_group(target_group, entry_lookup, group_lookup))
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
    """Import BSData catalogues with cross-catalogue link resolution for 40K 10e.

    This pass builds a global selection/group index across all discovered catalogues
    (excluding known non-40K systems like Adeptus Titanicus), then resolves entryLinks
    across files while extracting Unit, Weapon, and Ability profiles. This allows units
    that are declared in one file and have their stats in a library file to be
    materialised correctly (e.g., Primarchs referenced from supplements).
    """
    # Discover all catalogue files
    all_files: List[tuple[Path, str]] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            for file_path in sorted(path.rglob("*.cat")):
                all_files.append((file_path, file_path.relative_to(path).as_posix()))
            for file_path in sorted(path.rglob("*.gst")):
                all_files.append((file_path, file_path.relative_to(path).as_posix()))
        else:
            all_files.append((path, path.name))
    # Parse roots and filter out non-40K systems (e.g., Adeptus Titanicus)
    roots: List[ET.Element] = []
    factions: Dict[ET.Element, str] = {}
    source_files: Dict[ET.Element, str] = {}
    parent_lookups: Dict[ET.Element, Dict[ET.Element, ET.Element]] = {}
    child_model_reference_ids: Dict[ET.Element, set[str]] = {}
    for file_path, source_file in all_files:
        try:
            tree = ET.parse(file_path)
        except ET.ParseError:
            continue
        root = tree.getroot()
        _strip_namespace(root)
        name = root.get("name", file_path.stem)
        # Include all catalogues; some libraries (e.g., Titans) use a different gameSystemId
        # but still contain 40K-style Unit profiles referenced cross-catalogue.
        roots.append(root)
        factions[root] = name
        source_files[root] = source_file
        parent_lookups[root] = _build_parent_lookup(root)
        child_model_reference_ids[root] = _build_child_model_reference_ids(root, parent_lookups[root])

    # Build global lookups across all included catalogues
    global_entry_lookup: Dict[str, ET.Element] = {}
    global_group_lookup: Dict[str, ET.Element] = {}
    entry_source_files: Dict[ET.Element, str] = {}
    for root in roots:
        source_file = source_files.get(root, "")
        local_entries = _build_selection_entry_lookup(root)
        for entry_id, entry in local_entries.items():
            existing = global_entry_lookup.get(entry_id)
            if existing is None or _profile_count(entry) > _profile_count(existing):
                global_entry_lookup[entry_id] = entry
                entry_source_files[entry] = source_file
        local_groups = _build_selection_group_lookup(root)
        for group_id, group in local_groups.items():
            # Last one wins; group IDs are expected to be unique per repo
            global_group_lookup[group_id] = group

    units: List[UnitRow] = []
    weapons: List[WeaponRow] = []
    abilities: List[AbilityRow] = []
    keyword_rows: Dict[str, KeywordRow] = {}
    unit_keywords: List[UnitKeywordRow] = []

    processed_units: set[str] = set()

    # Extract from each root but resolve related entries against global lookups
    for root in roots:
        faction = factions[root]
        unit_source_file = source_files.get(root, "")
        for selection in root.findall(".//selectionEntry"):
            sel_type = (selection.get("type") or "").strip().lower()
            # Consider both 'unit' and 'model' carriers; some Primarchs are 'model'
            if sel_type not in {"unit", "model"}:
                continue
            if sel_type == "unit" and _is_crusade_variant_unit(selection):
                continue
            if sel_type == "model" and _is_non_standalone_model_without_direct_points(
                selection,
                parent_lookups[root],
                child_model_reference_ids[root],
            ):
                continue

            unit_id = selection.get("id") or _slugify(selection.get("name", "unit"))
            if unit_id in processed_units:
                continue

            related_entries = list(_collect_related_entries(global_entry_lookup, global_group_lookup, selection))
            # Gather all unit profiles across the selection and its related entries
            candidate_entries = [selection] + related_entries
            unit_profiles = [
                profile
                for entry in candidate_entries
                for profile in entry.findall("profiles/profile")
                if (profile.get("typeName") or "").strip().lower() == "unit"
            ]
            if not unit_profiles:
                # No materialised Unit profile -> skip
                continue

            processed_units.add(unit_id)
            stats = _extract_characteristics(unit_profiles)
            keywords = _collect_keywords(selection)

            min_models, max_models = _extract_unit_size(selection, related_entries)
            if sel_type == "model":
                min_models = 1
                max_models = 1
            units.append(
                UnitRow(
                    unit_id=unit_id,
                    faction=faction,
                    name=selection.get("name", "Unnamed Unit"),
                    toughness=_safe_int(stats.get("Toughness")) or _safe_int(stats.get("T")),
                    save=_clean_roll_stat(stats.get("Save"), max_allowed=7) or _clean_roll_stat(stats.get("SV"), max_allowed=7),
                    invulnerable_save=_clean_roll_stat(stats.get("Invulnerable Save")) or _clean_roll_stat(stats.get("INV")),
                    wounds=_safe_int(stats.get("Wounds")) or _safe_int(stats.get("W")),
                    move=_clean_stat(stats.get("Movement")) or _clean_stat(stats.get("M")),
                    leadership=_clean_stat(stats.get("Leadership")) or _clean_stat(stats.get("LD")),
                    objective_control=_safe_int(stats.get("Objective Control")) or _safe_int(stats.get("OC")),
                    points=_extract_points(candidate_entries),
                    models_min=min_models,
                    models_max=max_models,
                    feel_no_pain=_clean_roll_stat(stats.get("Feel No Pain")) or _clean_roll_stat(stats.get("FNP")) or None,
                    damage_cap=_clean_stat(stats.get("Damage Cap")) or None,
                    selection_type=sel_type,
                    source_file=unit_source_file,
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
            weapon_seen: set[tuple[str, str]] = set()
            for entry in candidate_entries:
                entry_id = entry.get("id") or ""
                for profile in entry.findall("profiles/profile"):
                    type_name = (profile.get("typeName") or "").strip().lower()
                    if type_name in weapon_profile_types:
                        weapon_key = (entry_id, type_name, profile.get("name") or "")
                        if weapon_key in weapon_seen:
                            continue
                        weapon_row = _weapon_from_profile(
                            profile,
                            unit_id,
                            source_file=entry_source_files.get(entry, unit_source_file),
                        )
                        if weapon_row:
                            weapons.append(weapon_row)
                            weapon_seen.add(weapon_key)

            abilities.extend(
                _ability_rows_from_entry(
                    selection,
                    source_type="unit",
                    source_id=unit_id,
                    source_file=unit_source_file,
                )
            )

    keywords = list(keyword_rows.values())
    keywords.sort(key=lambda row: row.keyword)
    unit_keywords.sort(key=lambda row: (row.unit_id, row.keyword_id))

    unique_weapons: dict[str, WeaponRow] = {}
    for weapon in weapons:
        unique_weapons.setdefault(weapon.weapon_id, weapon)

    unique_unit_keywords: list[UnitKeywordRow] = []
    seen_unit_keywords: set[tuple[str, str]] = set()
    for mapping in unit_keywords:
        key = (mapping.unit_id, mapping.keyword_id)
        if key in seen_unit_keywords:
            continue
        seen_unit_keywords.add(key)
        unique_unit_keywords.append(mapping)

    return units, list(unique_weapons.values()), abilities, keywords, unique_unit_keywords


def _parse_catalogue(path: Path) -> CatalogueRows:
    tree = ET.parse(path)
    root = tree.getroot()
    _strip_namespace(root)
    faction = root.get("name", path.stem)
    source_file = path.name

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
        if _is_crusade_variant_unit(selection):
            continue

        unit_id = selection.get("id") or _slugify(selection.get("name", "unit"))
        if unit_id in processed_units:
            continue
        processed_units.add(unit_id)
        related_entries = list(_collect_related_entries(entry_lookup, group_lookup, selection))
        candidate_entries = [selection] + related_entries
        unit_profiles = [
            profile
            for entry in candidate_entries
            for profile in entry.findall("profiles/profile")
            if (profile.get("typeName") or "").strip().lower() == "unit"
        ]
        if not unit_profiles:
            unit_profiles = selection.findall("profiles/profile[@typeName='Unit']")
        stats = _extract_characteristics(unit_profiles)
        keywords = _collect_keywords(selection)

        units.append(
            UnitRow(
                unit_id=unit_id,
                faction=faction,
                name=selection.get("name", "Unnamed Unit"),
                toughness=_safe_int(stats.get("Toughness")) or _safe_int(stats.get("T")),
                save=_clean_roll_stat(stats.get("Save"), max_allowed=7) or _clean_roll_stat(stats.get("SV"), max_allowed=7),
                invulnerable_save=_clean_roll_stat(stats.get("Invulnerable Save")) or _clean_roll_stat(stats.get("INV")),
                wounds=_safe_int(stats.get("Wounds")) or _safe_int(stats.get("W")),
                move=_clean_stat(stats.get("Movement")) or _clean_stat(stats.get("M")),
                leadership=_clean_stat(stats.get("Leadership")) or _clean_stat(stats.get("LD")),
                objective_control=_safe_int(stats.get("Objective Control")) or _safe_int(stats.get("OC")),
                points=_extract_points(candidate_entries),
                feel_no_pain=_clean_roll_stat(stats.get("Feel No Pain")) or _clean_roll_stat(stats.get("FNP")) or None,
                damage_cap=_clean_stat(stats.get("Damage Cap")) or None,
                selection_type="unit",
                source_file=source_file,
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
        weapon_seen: set[tuple[str, str]] = set()
        for entry in candidate_entries:
            entry_id = entry.get("id") or ""
            for profile in entry.findall("profiles/profile"):
                type_name = (profile.get("typeName") or "").strip().lower()
                if type_name in weapon_profile_types:
                    weapon_key = (entry_id, type_name, profile.get("name") or "")
                    if weapon_key in weapon_seen:
                        continue
                    weapon_row = _weapon_from_profile(profile, unit_id, source_file=source_file)
                    if weapon_row:
                        weapons.append(weapon_row)
                        weapon_seen.add(weapon_key)

        abilities.extend(_ability_rows_from_entry(selection, source_type="unit", source_id=unit_id, source_file=source_file))

    units.sort(key=lambda row: (row.faction, row.name))
    weapons.sort(key=lambda row: (row.unit_id, row.name))
    abilities.sort(key=lambda row: (row.source_id, row.name))
    keywords = list(keyword_rows.values())
    keywords.sort(key=lambda row: row.keyword)
    unit_keywords.sort(key=lambda row: (row.unit_id, row.keyword_id))

    unique_weapons: dict[str, WeaponRow] = {}
    for weapon in weapons:
        unique_weapons.setdefault(weapon.weapon_id, weapon)

    unique_unit_keywords: list[UnitKeywordRow] = []
    seen_unit_keywords: set[tuple[str, str]] = set()
    for mapping in unit_keywords:
        key = (mapping.unit_id, mapping.keyword_id)
        if key in seen_unit_keywords:
            continue
        seen_unit_keywords.add(key)
        unique_unit_keywords.append(mapping)

    return units, list(unique_weapons.values()), abilities, keywords, unique_unit_keywords


def _weapon_from_profile(profile: ET.Element, unit_id: str, *, source_file: str = "") -> Optional[WeaponRow]:
    name = profile.get("name")
    characteristics = _extract_characteristics([profile])

    if not name:
        return None


    attacks = characteristics.get("Attacks") or characteristics.get("A") or ""
    strength = characteristics.get("Strength") or characteristics.get("S") or ""
    ap = characteristics.get("AP") or characteristics.get("Armor Piercing") or ""
    damage = characteristics.get("Damage") or characteristics.get("D") or ""
    keywords = characteristics.get("Keywords") or "-"

    skill = (
        characteristics.get("Ballistic Skill")
        or characteristics.get("BS")
        or characteristics.get("Weapon Skill")
        or characteristics.get("WS")
        or ""
    )

    range_value = (characteristics.get("Range") or "").strip().lower()
    type_hint = (profile.get("typeName") or "").strip().lower()
    if "melee" in type_hint:
        weapon_type = "melee"
    elif "ranged" in type_hint:
        weapon_type = "ranged"
    elif range_value in {"melee", ""}:
        weapon_type = "melee"
    else:
        weapon_type = "ranged"

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
        source_file=source_file,
    )


def _ability_from_profile(
    profile: ET.Element,
    *,
    source_type: str,
    source_id: str,
    source_file: str = "",
) -> Optional[AbilityRow]:
    name = profile.get("name")
    if not name:
        return None

    characteristics = _extract_characteristics([profile])
    text = characteristics.get("Description") or characteristics.get("Text") or ""
    profile_id = profile.get("id")
    identity = f"{_slugify(name)}:{profile_id}" if profile_id else _slugify(name)

    return AbilityRow(
        ability_id=f"{source_id}:{identity}",
        source_type=source_type,
        source_id=source_id,
        name=name,
        text=text.strip(),
        source_file=source_file,
    )


def _ability_rows_from_entry(
    entry: ET.Element,
    *,
    source_type: str,
    source_id: str,
    source_file: str = "",
) -> List[AbilityRow]:
    rows: List[AbilityRow] = []
    seen: set[tuple[str, str]] = set()
    ability_profile_types = {"ability", "abilities"}
    for profile in entry.findall("profiles/profile"):
        type_name = (profile.get("typeName") or "").strip().lower()
        if type_name not in ability_profile_types:
            continue
        ability_row = _ability_from_profile(
            profile,
            source_type=source_type,
            source_id=source_id,
            source_file=source_file,
        )
        if not ability_row:
            continue
        ability_key = (ability_row.name, ability_row.text)
        if ability_key in seen:
            continue
        rows.append(ability_row)
        seen.add(ability_key)
    return rows


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


def _extract_unit_size(selection: ET.Element, related_entries: Sequence[ET.Element]) -> tuple[Optional[int], Optional[int]]:
    """Extract min/max number of models for a unit from BSData constraints.

    Heuristics:
    - Prefer summing min/max constraints across child model entries of this unit
      (e.g., 4 Intercessors + 1 Sergeant -> min 5 models).
    - If child-model parsing yields nothing, fall back to unit/group constraints
      in the subtree, then to linked entries.
    - If an upper bound is inconsistent (max < min), drop the max.
    """

    def parse_min_max_from_node(node: ET.Element) -> tuple[Optional[int], Optional[int]]:
        mins: List[int] = []
        maxs: List[int] = []
        for cons in node.findall("constraints/constraint"):
            field = (cons.get("field") or cons.get("fieldId") or "").strip().lower()
            ctype = (cons.get("type") or "").strip().lower()
            if field != "selections" and "selection" not in field:
                continue
            value_text = cons.get("value")
            try:
                value = int(float(value_text)) if value_text is not None else None
            except ValueError:
                value = None
            if value is None:
                continue
            if ctype == "min":
                mins.append(value)
            elif ctype == "max":
                # Ignore non-positive maxima which are often placeholders
                if value > 0:
                    maxs.append(value)
        min_v = max(mins) if mins else None
        max_v = min(maxs) if maxs else None
        return min_v, max_v

    # Pass 1: sum constraints across direct child models.
    # Nested model choices are usually alternatives inside a constrained group and
    # are handled by Pass 2; summing them here would double-count loadout choices.
    model_children = selection.findall("./selectionEntries/selectionEntry[@type='model']")

    total_min = 0
    total_max = 0
    have_any_child = False
    all_children_have_max = True

    for model in model_children:
        have_any_child = True
        mn, mx = parse_min_max_from_node(model)
        if mn is not None:
            total_min += mn
        # If a child lacks an explicit max, we cannot reliably sum maxima
        if mx is not None:
            total_max += mx
        else:
            all_children_have_max = False

    min_models: Optional[int] = None
    max_models: Optional[int] = None

    if have_any_child and total_min > 0:
        min_models = total_min
    if have_any_child and all_children_have_max and total_max > 0:
        max_models = total_max

    # Pass 2: consider selection groups that contain model entries (squad size groups)
    def group_min_max(root: ET.Element) -> tuple[Optional[int], Optional[int]]:
        # Sum min/max across distinct model-containing groups (e.g., Boyz + Boss Nob)
        total_min = 0
        total_max = 0
        have_any = False
        all_have_max = True
        for group in root.findall(".//selectionEntryGroup"):
            if not group.findall(".//selectionEntry[@type='model']"):
                continue
            g_min, g_max = parse_min_max_from_node(group)
            if g_min is None and g_max is None:
                continue
            if g_min is not None and g_min > 0:
                total_min += g_min
                have_any = True
                if g_max is not None and g_max > 0:
                    total_max += g_max
                else:
                    all_have_max = False
        min_v = total_min if have_any and total_min > 0 else None
        max_v = total_max if have_any and all_have_max and total_max > 0 else None
        return min_v, max_v

    if True:
        gmin, gmax = group_min_max(selection)
        # Required direct model entries plus model-containing groups are additive
        # (e.g. 1 champion + 9-19 squad members -> 10-20 models).
        if gmin is not None:
            if have_any_child and min_models is not None:
                min_models += gmin
            elif min_models is None or gmin > min_models:
                min_models = gmin
        if gmax is not None:
            if have_any_child and max_models is not None:
                max_models += gmax
            elif max_models is None:
                max_models = gmax
            else:
                max_models = max(max_models, gmax)

    # Pass 2b: if constrained groups did not provide a complete answer, fall
    # back to nested model constraints. Do this only for missing bounds so
    # alternative loadout models inside an already constrained group do not
    # inflate sizes (e.g. two 0-3 alternatives in a 1-3 model group).
    if min_models is None or max_models is None:
        nested_models = [
            model
            for model in selection.findall(".//selectionEntry[@type='model']")
            if model not in model_children
        ]
        nested_min = 0
        nested_max = 0
        have_nested = False
        all_nested_have_max = True
        for model in nested_models:
            mn, mx = parse_min_max_from_node(model)
            if mn is not None:
                nested_min += mn
                have_nested = True
            if mx is not None:
                nested_max += mx
            else:
                all_nested_have_max = False
        if min_models is None and have_nested and nested_min > 0:
            min_models = nested_min
        if max_models is None and have_nested and all_nested_have_max and nested_max > 0:
            max_models = nested_max

    # Pass 3: fall back to unit-level constraints in the subtree (non-group)
    if min_models is None or max_models is None:
        u_min, u_max = parse_min_max_from_node(selection)
        if min_models is None:
            min_models = u_min
        if max_models is None:
            max_models = u_max

    # Pass 4: consider related/linked entries and their groups as last resort
    if min_models is None or max_models is None:
        best_min = min_models
        best_max = max_models
        for node in related_entries:
            # Check groups first
            gmin2, gmax2 = group_min_max(node)
            if best_min is None and gmin2 is not None:
                best_min = gmin2
            if best_max is None and gmax2 is not None:
                best_max = gmax2
            if best_min is not None and best_max is not None:
                break
            # Then plain constraints on the node
            n_min, n_max = parse_min_max_from_node(node)
            if best_min is None and n_min is not None:
                best_min = n_min
            if best_max is None and n_max is not None:
                best_max = n_max
            if best_min is not None and best_max is not None:
                break
        min_models = best_min
        max_models = best_max

    # Adjust for required leader-style upgrades that add a model (e.g., Sergeant, Boss Nob)
    # Some catalogues encode these as 'upgrade' entries with selection constraints,
    # not as model selectionEntries. Add their required min to the total if detected.
    leader_keywords = [
        "sergeant",
        "champion",
        "boss nob",
        "nob",
        "pack leader",
        "squad leader",
        "exarch",
        "alpha",
    ]
    added_min = 0
    added_max = 0
    for node in selection.findall(".//selectionEntry"):
        name = (node.get("name") or "").strip().lower()
        ntype = (node.get("type") or "").strip().lower()
        # Count only leader-like upgrades/models; direct model entries were already counted above.
        if ntype not in {"upgrade", "model"} or node in model_children:
            continue
        if not any(k in name for k in leader_keywords):
            continue
        lmin, lmax = parse_min_max_from_node(node)
        if lmin and lmin > 0:
            added_min += lmin
        if lmax and lmax > 0:
            added_max += lmax
    if added_min > 0:
        min_models = (min_models or 0) + added_min
    if added_max > 0:
        if max_models is None:
            max_models = added_max
        else:
            max_models += added_max

    # Sanity check: drop contradictory max bounds
    if min_models is not None and max_models is not None and max_models < min_models:
        max_models = None

    return min_models, max_models


def _extract_points(entries: Sequence[ET.Element]) -> Optional[int]:
    primary_points: Optional[int] = None
    model_points: List[int] = []
    zero_points_seen = False

    for index, entry in enumerate(entries):
        entry_type = (entry.get("type") or "").strip().lower()
        for cost in entry.findall("costs/cost"):
            name = (cost.get("name") or "").strip().lower()
            if name not in {"pts", "points"}:
                continue
            value = cost.get("value")
            if not value:
                continue
            try:
                numeric = float(value)
            except ValueError:
                continue
            if abs(numeric - round(numeric)) <= 1e-6:
                points = int(round(numeric))
            else:
                points = int(numeric)
            if points <= 0:
                zero_points_seen = True
                continue
            if index == 0 and entry_type in {"unit", "model"}:
                primary_points = points
                continue
            if entry_type == "model":
                model_points.append(points)

    if primary_points is not None:
        return primary_points
    if model_points:
        return min(model_points)
    if zero_points_seen:
        return 0
    return None


def _is_non_standalone_model_without_direct_points(
    selection: ET.Element,
    parent_lookup: Dict[ET.Element, ET.Element],
    child_model_reference_ids: set[str],
) -> bool:
    if _direct_positive_points(selection) is not None:
        return False
    selection_id = selection.get("id")
    if selection_id and selection_id in child_model_reference_ids:
        return True

    current = parent_lookup.get(selection)
    while current is not None:
        if current.tag == "selectionEntry" and (current.get("type") or "").strip().lower() in {"unit", "model"}:
            return True
        current = parent_lookup.get(current)
    return False


def _direct_positive_points(entry: ET.Element) -> Optional[int]:
    for cost in entry.findall("costs/cost"):
        name = (cost.get("name") or "").strip().lower()
        if name not in {"pts", "points"}:
            continue
        value = cost.get("value")
        if not value:
            continue
        try:
            numeric = float(value)
        except ValueError:
            continue
        points = int(round(numeric)) if abs(numeric - round(numeric)) <= 1e-6 else int(numeric)
        if points > 0:
            return points
    return None


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


def _clean_roll_stat(value: Optional[str], *, max_allowed: int = 6) -> Optional[str]:
    cleaned = _clean_stat(value)
    if not cleaned:
        return None
    if cleaned.endswith("+"):
        return cleaned
    if cleaned.isdigit():
        roll = int(cleaned)
        if 2 <= roll <= max_allowed:
            return f"{roll}+"
    return cleaned


def _safe_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _slugify(value: str) -> str:
    return "-".join(value.lower().split())







