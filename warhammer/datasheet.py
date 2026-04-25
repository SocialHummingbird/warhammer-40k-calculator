
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.profiles import AbilityModifier, UnitProfile, load_units


def _describe_ability_modifier(modifier: AbilityModifier) -> str:
    base = modifier.description or modifier.source or "Ability modifier"
    scope_parts: List[str] = []
    if modifier.applies_to_ranged and not modifier.applies_to_melee:
        scope_parts.append("ranged attacks only")
    elif modifier.applies_to_melee and not modifier.applies_to_ranged:
        scope_parts.append("melee attacks only")
    if modifier.target_keywords:
        scope_parts.append("vs " + "/".join(sorted(keyword.upper() for keyword in modifier.target_keywords)))
    if scope_parts:
        base = f"{base} ({', '.join(scope_parts)})"
    return base



def format_unit_datasheet(unit: UnitProfile, *, include_crusade: bool = False, core_ability_limit: int = 10) -> str:
    lines: List[str] = []
    lines.append(f"Unit: {unit.name}")
    if unit.faction:
        lines.append(f"Faction: {unit.faction}")
    if unit.points is not None:
        lines.append(f"Points: {unit.points}pt")
    if unit.models_min or unit.models_max:
        if unit.models_min and unit.models_max:
            if unit.models_min == unit.models_max:
                lines.append(f"Models: {unit.models_min}")
            else:
                lines.append(f"Models: {unit.models_min}-{unit.models_max}")
        elif unit.models_min:
            lines.append(f"Models: >={unit.models_min}")
        elif unit.models_max:
            lines.append(f"Models: <={unit.models_max}")

    defence_parts = [
        f"Toughness {unit.toughness}",
        f"Save {unit.save_label}",
    ]
    if unit.invulnerable_label:
        defence_parts.append(f"Invulnerable {unit.invulnerable_label}")
    if unit.feel_no_pain_label:
        defence_parts.append(f"FNP {unit.feel_no_pain_label}")
    if unit.damage_cap is not None:
        defence_parts.append(f"Damage cap {unit.damage_cap:g}")
    lines.append("Defence: " + ", ".join(defence_parts))

    keywords = ", ".join(sorted(unit.keywords)) if unit.keywords else "None"
    lines.append(f"Keywords: {keywords}")

    if unit.weapons:
        lines.append("Weapons:")
        for weapon in unit.weapons:
            lines.append(f"  - {weapon.name} ({weapon.type.title()})")
            stats_parts = [f"Attacks {weapon.attacks.label}"]
            if weapon.auto_hits:
                stats_parts.append("Skill Auto")
            else:
                stats_parts.append(f"Skill {weapon.skill_label}")
            stats_parts.extend(
                [
                    f"Strength {weapon.strength}",
                    f"AP {weapon.ap}",
                    f"Damage {weapon.damage.label}",
                ]
            )
            if getattr(weapon, "hit_modifier", 0):
                stats_parts.append(f"Hit modifier {weapon.hit_modifier:+d}")
            if getattr(weapon, "wound_modifier", 0):
                stats_parts.append(f"Wound modifier {weapon.wound_modifier:+d}")
            lines.append("    " + ", ".join(stats_parts))
            weapon_notes: List[str] = []
            if weapon.reroll_hits != "none":
                weapon_notes.append(
                    "Re-roll hits" if weapon.reroll_hits == "all" else "Re-roll hit rolls of 1"
                )
            if weapon.reroll_wounds != "none":
                weapon_notes.append(
                    "Re-roll wounds" if weapon.reroll_wounds == "all" else "Re-roll wound rolls of 1"
                )
            if weapon.lethal_hits:
                weapon_notes.append("Lethal Hits")
            if weapon.sustained_hits:
                weapon_notes.append(f"Sustained Hits {weapon.sustained_hits}")
            if weapon.devastating_wounds:
                weapon_notes.append("Devastating Wounds")
            if weapon.auto_hits:
                weapon_notes.append("Auto-hitting")
            if weapon_notes:
                lines.append("      Abilities: " + ", ".join(weapon_notes))

    ability_limit = len(unit.abilities) if include_crusade else min(core_ability_limit, len(unit.abilities))
    displayed_abilities = unit.abilities[:ability_limit]
    omitted_abilities = len(unit.abilities) - ability_limit

    ability_sources = {ability.name for ability in displayed_abilities if ability.name}
    modifiers = unit.ability_modifiers
    if not include_crusade:
        modifiers = [m for m in modifiers if m.source in ability_sources]
    omitted_modifiers = len(unit.ability_modifiers) - len(modifiers)

    if modifiers:
        lines.append("Derived Modifiers:")
        for modifier in modifiers:
            lines.append("  - " + _describe_ability_modifier(modifier))
        if not include_crusade and omitted_modifiers > 0:
            lines.append(
                f"  ... {omitted_modifiers} additional modifiers hidden (use --include-crusade to show all)"
            )

    if displayed_abilities:
        lines.append("Abilities:")
        for ability in displayed_abilities:
            name = ability.name or "(Unnamed)"
            text = (ability.text or "").strip()
            if text:
                wrapped = textwrap.fill(
                    text,
                    width=100,
                    initial_indent="      ",
                    subsequent_indent="      ",
                )
                lines.append(f"  - {name}:")
                lines.append(wrapped)
            else:
                lines.append(f"  - {name}")
        if not include_crusade and omitted_abilities > 0:
            lines.append(
                f"  ... {omitted_abilities} additional abilities hidden (use --include-crusade to show all)"
            )
    else:
        lines.append("Abilities: None")

    return "\n".join(lines) + "\n"

def print_unit_datasheet(unit: UnitProfile, *, include_crusade: bool = False, core_ability_limit: int = 10) -> None:
    output = format_unit_datasheet(unit, include_crusade=include_crusade, core_ability_limit=core_ability_limit)
    encoding = sys.stdout.encoding or "utf-8"
    print(output.encode(encoding, errors="replace").decode(encoding))


def load_units_from_json(path: Path) -> Dict[str, UnitProfile]:
    if not path.exists():
        raise SystemExit(f"Data file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "units" not in payload or not isinstance(payload["units"], list):
        raise SystemExit("Data file must contain a top-level 'units' list")
    units = load_units(payload["units"])
    return {unit.name.casefold(): unit for unit in units}




def _profile_priority(profile: UnitProfile, preferred_faction: str | None) -> tuple[int, int, int, int, str]:
    faction = (profile.faction or "").casefold()
    name_lower = profile.name.casefold()
    score = 0
    if preferred_faction and preferred_faction in faction:
        score += 1000
    if faction:
        score += 50
    if "library" in faction:
        score -= 200
    if "legends" in faction or "legends" in name_lower:
        score -= 100
    if "index" in faction:
        score -= 20
    selection_type = getattr(profile, "selection_type", "") or ""
    if selection_type:
        score += 10
    models_max = profile.models_max or 0
    models_min = profile.models_min or 0
    return (score, models_max, -models_min, -len(faction), faction)


def load_units_from_csv(directory: Path, *, prefer_faction: Optional[str] = None) -> Dict[str, UnitProfile]:
    if not directory.exists():
        raise SystemExit(f"CSV directory not found: {directory}")
    profiles_by_id = load_units_from_directory(directory)
    if not profiles_by_id:
        raise SystemExit(f"No units found in CSV directory: {directory}")

    buckets: Dict[str, List[UnitProfile]] = {}
    for profile in profiles_by_id.values():
        buckets.setdefault(profile.name.casefold(), []).append(profile)

    preferred = prefer_faction.casefold() if prefer_faction else None
    units: Dict[str, UnitProfile] = {}

    for key, profiles in buckets.items():
        if len(profiles) == 1:
            units[key] = profiles[0]
            continue

        ranked = sorted(
            profiles,
            key=lambda profile: _profile_priority(profile, preferred),
            reverse=True,
        )
        choice = ranked[0]
        units[key] = choice

    
    return units




