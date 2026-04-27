from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from .profiles import UnitProfile, WeaponProfile


@dataclass
class AppliedModifiers:
    hit_modifier: int = 0
    wound_modifier: int = 0
    reroll_hits: str = "none"
    reroll_wounds: str = "none"
    grant_twin_linked: bool = False
    grant_torrent: bool = False
    grant_blast: bool = False
    grant_assault: bool = False
    ignores_cover: bool = False
    anti_rules: List[Tuple[str, int]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def normalise_keywords(keywords: List[str]) -> Set[str]:
    return {keyword.lower() for keyword in keywords}


def merge_reroll(primary: str, extra: str) -> str:
    hierarchy = {"none": 0, "ones": 1, "all": 2}
    if primary not in hierarchy:
        primary = "none"
    if extra not in hierarchy:
        extra = "none"
    return primary if hierarchy[primary] >= hierarchy[extra] else extra


def collect_ability_modifiers(
    attacker: UnitProfile, defender_keywords: Set[str], weapon: WeaponProfile
) -> AppliedModifiers:
    result = AppliedModifiers()
    modifiers = getattr(attacker, "ability_modifiers", None)
    if not modifiers:
        return result

    for modifier in modifiers:
        if not modifier.applies_to(weapon.type, defender_keywords):
            continue
        result.hit_modifier += modifier.hit_modifier
        result.wound_modifier += modifier.wound_modifier
        result.reroll_hits = merge_reroll(result.reroll_hits, modifier.reroll_hits)
        result.reroll_wounds = merge_reroll(result.reroll_wounds, modifier.reroll_wounds)
        if modifier.grant_twin_linked:
            result.grant_twin_linked = True
        if modifier.grant_torrent:
            result.grant_torrent = True
        if modifier.grant_blast:
            result.grant_blast = True
        if modifier.grant_assault:
            result.grant_assault = True
        if modifier.ignores_cover:
            result.ignores_cover = True
        if modifier.anti_rules:
            result.anti_rules.extend(modifier.anti_rules)
        if modifier.description:
            result.notes.append(modifier.description)
    return result


def resolve_anti_threshold(
    weapon: WeaponProfile,
    applied_modifiers: AppliedModifiers,
    defender_keywords: Set[str],
) -> Optional[int]:
    weapon_threshold = weapon.anti_threshold_for(defender_keywords)
    ability_threshold = None
    if applied_modifiers.anti_rules:
        matching_thresholds = [
            value for keyword, value in applied_modifiers.anti_rules if keyword in defender_keywords
        ]
        if matching_thresholds:
            ability_threshold = min(matching_thresholds)

    threshold = None
    for candidate in (weapon_threshold, ability_threshold):
        if candidate is not None:
            threshold = candidate if threshold is None else min(threshold, candidate)
    return threshold


def build_ability_notes(weapon: WeaponProfile) -> List[str]:
    notes: List[str] = []
    if weapon.reroll_hits != "none":
        label = "Hit rerolls (all)" if weapon.reroll_hits == "all" else "Hit rerolls (ones)"
        notes.append(label)
    if weapon.reroll_wounds != "none":
        label = "Wound rerolls (all)" if weapon.reroll_wounds == "all" else "Wound rerolls (ones)"
        notes.append(label)
    if weapon.lethal_hits:
        notes.append("Lethal Hits")
    if weapon.sustained_hits:
        notes.append(f"Sustained Hits {weapon.sustained_hits}")
    if weapon.devastating_wounds:
        notes.append("Devastating Wounds")
    if weapon.twin_linked:
        notes.append("Twin-linked")
    if weapon.assault:
        notes.append("Assault")
    if weapon.heavy:
        notes.append("Heavy")
    if weapon.torrent:
        notes.append("Torrent")
    if weapon.ignores_cover:
        notes.append("Ignores Cover")
    if weapon.blast:
        notes.append("Blast")
    if weapon.melta is not None:
        notes.append(f"Melta {weapon.melta}" if weapon.melta else "Melta")
    if weapon.rapid_fire is not None:
        notes.append(f"Rapid Fire {weapon.rapid_fire}" if weapon.rapid_fire else "Rapid Fire")
    if weapon.anti_rules:
        anti_text = "/".join(sorted(f"{keyword.upper()} {threshold}+" for keyword, threshold in weapon.anti_rules))
        notes.append(f"Anti-{anti_text}")
    if weapon.auto_hits:
        notes.append("Auto-hitting")
    return notes
