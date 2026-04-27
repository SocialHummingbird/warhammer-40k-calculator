from __future__ import annotations

from typing import Any, Dict, Optional

from .calculator import evaluate_unit, evaluate_weapon
from .context import EngagementContext
from .profiles import UnitProfile, WeaponProfile
from .results import UnitResult, scale_unit_result
from .matchup_payloads import (
    context_detail,
    matchup_judgement,
    points_basis_models,
    points_per_model,
    points_removed,
    unit_detail,
    unit_result,
    unit_summary,
    weapon_detail,
    weapon_result,
)


def calculate_matchup(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    *,
    outgoing_context: EngagementContext,
    incoming_context: EngagementContext,
    outgoing_weapon: Optional[str] = None,
    incoming_weapon: Optional[str] = None,
    outgoing_multiplier: int = 1,
    incoming_multiplier: int = 1,
    edition: str = "10e",
) -> Dict[str, Any]:
    """Run the deterministic two-way matchup calculation and return a JSON-ready payload."""

    outgoing = evaluate_unit_with_weapon_filter(
        attacker,
        defender,
        mode,
        context=outgoing_context,
        weapon_name=outgoing_weapon,
        multiplier=outgoing_multiplier,
        edition=edition,
    )
    incoming = evaluate_unit_with_weapon_filter(
        defender,
        attacker,
        mode,
        context=incoming_context,
        weapon_name=incoming_weapon,
        multiplier=incoming_multiplier,
        edition=edition,
    )
    outgoing_payload = unit_result(outgoing, target=defender)
    incoming_payload = unit_result(incoming, target=attacker)
    return {
        "attacker": unit_summary(attacker),
        "defender": unit_summary(defender),
        "mode": mode,
        "edition": edition,
        "contexts": {
            "outgoing": context_detail(outgoing_context),
            "incoming": context_detail(incoming_context),
        },
        "weapon_filters": {
            "outgoing": outgoing_weapon,
            "incoming": incoming_weapon,
        },
        "multipliers": {
            "outgoing": outgoing_multiplier,
            "incoming": incoming_multiplier,
        },
        "outgoing": outgoing_payload,
        "incoming": incoming_payload,
        "judgement": matchup_judgement(attacker, defender, outgoing=outgoing_payload, incoming=incoming_payload),
    }


def evaluate_unit_with_weapon_filter(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    *,
    context: EngagementContext,
    weapon_name: Optional[str],
    multiplier: int = 1,
    edition: str = "10e",
) -> UnitResult:
    if not weapon_name:
        result = evaluate_unit(attacker, defender, mode, context=context, edition=edition)  # type: ignore[arg-type]
        return scale_unit_result(result, multiplier)

    matches = [
        weapon
        for weapon in attacker.weapons
        if weapon.type == mode and weapon.name.casefold() == weapon_name.casefold()
    ]
    if not matches:
        raise ValueError(f"{attacker.name} has no {mode} weapon named {weapon_name}")
    result = UnitResult(
        unit=attacker,
        weapons=[evaluate_weapon(attacker, defender, weapon, context=context, edition=edition) for weapon in matches],
        target_wounds=defender.wounds,
    )
    return scale_unit_result(result, multiplier)
