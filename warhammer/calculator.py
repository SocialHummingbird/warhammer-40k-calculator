from __future__ import annotations

from typing import Optional

from .context import EngagementContext, EngagementMode
from .profiles import UnitProfile, WeaponProfile
from .results import UnitResult, WeaponResult, scale_unit_result, scale_weapon_result
from .rules import Ruleset, get_ruleset
from .weapon_resolution import resolve_weapon

DEFAULT_RULES_EDITION = "10e"

__all__ = [
    "DEFAULT_RULES_EDITION",
    "EngagementContext",
    "EngagementMode",
    "UnitResult",
    "WeaponResult",
    "evaluate_unit",
    "evaluate_weapon",
    "scale_unit_result",
    "scale_weapon_result",
]


def evaluate_unit(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: EngagementMode,
    context: Optional[EngagementContext] = None,
    *,
    edition: str = DEFAULT_RULES_EDITION,
    ruleset: Optional[Ruleset] = None,
) -> UnitResult:
    context = context or EngagementContext()
    active_ruleset = ruleset or get_ruleset(edition)
    relevant_weapons = [weapon for weapon in attacker.weapons if weapon.type == mode]
    weapon_results = [
        resolve_weapon(attacker=attacker, defender=defender, weapon=weapon, context=context, ruleset=active_ruleset)
        for weapon in relevant_weapons
    ]
    return UnitResult(unit=attacker, weapons=weapon_results, target_wounds=defender.wounds)


def evaluate_weapon(
    attacker: UnitProfile,
    defender: UnitProfile,
    weapon: WeaponProfile,
    *,
    context: Optional[EngagementContext] = None,
    edition: str = DEFAULT_RULES_EDITION,
    ruleset: Optional[Ruleset] = None,
) -> WeaponResult:
    """Evaluate a single weapon profile against a defender."""

    return resolve_weapon(
        attacker=attacker,
        defender=defender,
        weapon=weapon,
        context=context or EngagementContext(),
        ruleset=ruleset or get_ruleset(edition),
    )
