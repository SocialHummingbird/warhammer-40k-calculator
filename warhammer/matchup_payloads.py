from __future__ import annotations

from typing import Any, Dict, Optional

from .context import EngagementContext
from .profiles import UnitProfile, WeaponProfile
from .results import UnitResult


def context_detail(context: EngagementContext) -> Dict[str, Any]:
    return {
        "attacker_moved": context.attacker_moved,
        "attacker_advanced": context.attacker_advanced,
        "target_within_half_range": context.target_within_half_range,
        "target_in_cover": context.target_in_cover,
        "target_model_count": context.target_model_count,
    }


def unit_summary(unit: UnitProfile) -> Dict[str, Any]:
    return {
        "id": unit.unit_id,
        "name": unit.name,
        "faction": unit.faction,
        "toughness": unit.toughness,
        "save": unit.save_label,
        "wounds": unit.wounds,
        "objective_control": unit.objective_control,
        "points": unit.points,
        "models_min": unit.models_min,
        "models_max": unit.models_max,
        "source_file": unit.source_file,
        "keywords": unit.keywords,
    }


def unit_detail(unit: UnitProfile) -> Dict[str, Any]:
    payload = unit_summary(unit)
    payload["weapons"] = [weapon_detail(weapon) for weapon in unit.weapons]
    payload["abilities"] = [
        {"name": ability.name, "text": ability.text, "source_file": ability.source_file}
        for ability in unit.abilities
    ]
    return payload


def weapon_detail(weapon: WeaponProfile) -> Dict[str, Any]:
    return {
        "name": weapon.name,
        "type": weapon.type,
        "attacks": weapon.attacks.label,
        "skill": weapon.skill_label,
        "strength": weapon.strength_label or str(weapon.strength),
        "ap": weapon.ap,
        "damage": weapon.damage.label,
        "range_inches": weapon.range_inches,
        "keywords": weapon.keywords,
        "source_file": weapon.source_file,
    }


def unit_result(result: UnitResult, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return {
        "total_damage": result.total_damage,
        "total_unsaved_wounds": result.total_unsaved_wounds,
        "expected_models_destroyed": result.expected_models_destroyed,
        "estimated_points_removed": points_removed(target, result.expected_models_destroyed),
        "points_per_model": points_per_model(target),
        "feel_no_pain_applied": result.feel_no_pain_applied,
        "weapons": [weapon_result(weapon_result_item, target=target) for weapon_result_item in result.weapons],
    }


def weapon_result(result: Any, *, target: Optional[UnitProfile] = None) -> Dict[str, Any]:
    return {
        "weapon": weapon_detail(result.weapon),
        "attacks": result.attacks,
        "hits": result.hits,
        "wounds": result.wounds,
        "unsaved_wounds": result.unsaved_wounds,
        "expected_damage": result.expected_damage,
        "expected_models_destroyed": result.expected_models_destroyed,
        "estimated_points_removed": points_removed(target, result.expected_models_destroyed),
        "hit_probability": result.hit_probability,
        "wound_probability": result.wound_probability,
        "failed_save_probability": result.failed_save_probability,
        "wound_roll": result.wound_roll_label,
        "save": result.save_used_label,
        "notes": result.ability_notes,
    }


def points_basis_models(unit: Optional[UnitProfile]) -> Optional[int]:
    if unit is None:
        return None
    if unit.models_min and unit.models_max:
        return max(1, round((unit.models_min + unit.models_max) / 2))
    if unit.models_max:
        return max(1, unit.models_max)
    if unit.models_min:
        return max(1, unit.models_min)
    return 1


def points_per_model(unit: Optional[UnitProfile]) -> Optional[float]:
    models = points_basis_models(unit)
    if unit is None or not unit.points or not models:
        return None
    return unit.points / models


def points_removed(unit: Optional[UnitProfile], models_destroyed: Optional[float]) -> Optional[float]:
    ppm = points_per_model(unit)
    if ppm is None or models_destroyed is None:
        return None
    return models_destroyed * ppm


def matchup_judgement(
    attacker: UnitProfile,
    defender: UnitProfile,
    *,
    outgoing: Dict[str, Any],
    incoming: Dict[str, Any],
) -> Dict[str, Any]:
    outgoing_points = _as_float(outgoing.get("estimated_points_removed"))
    incoming_points = _as_float(incoming.get("estimated_points_removed"))
    if outgoing_points is not None and incoming_points is not None:
        outgoing_score = outgoing_points
        incoming_score = incoming_points
        basis = "points_removed"
        basis_label = "estimated points removed"
    else:
        outgoing_score = _as_float(outgoing.get("total_damage")) or 0.0
        incoming_score = _as_float(incoming.get("total_damage")) or 0.0
        basis = "damage"
        basis_label = "expected damage"

    delta = outgoing_score - incoming_score
    total = max(outgoing_score + incoming_score, 0.01)
    edge = abs(delta) / total
    confidence = "narrow"
    if edge >= 0.45:
        confidence = "decisive"
    elif edge >= 0.22:
        confidence = "clear"

    close = edge < 0.08
    winner = attacker.name if delta >= 0 else defender.name
    loser_score = incoming_score if delta >= 0 else outgoing_score
    winner_score = outgoing_score if delta >= 0 else incoming_score
    damage_context = (
        f" Damage context: {attacker.name} deals {(_as_float(outgoing.get('total_damage')) or 0.0):.2f} "
        f"and {defender.name} returns {(_as_float(incoming.get('total_damage')) or 0.0):.2f}."
    )
    points_context = (
        f" Points context: {attacker.name} is {attacker.points} pts and {defender.name} is {defender.points} pts."
        if attacker.points and defender.points
        else ""
    )

    if close:
        title = "AI judgement: too close to call"
        body = (
            f"The exchange is nearly even on {basis_label}: {attacker.name} scores {outgoing_score:.2f} "
            f"and {defender.name} returns {incoming_score:.2f}."
        )
    elif basis == "points_removed":
        title = f"AI judgement: {winner} favored ({confidence})"
        body = (
            f"{winner} is favored on estimated points removed, scoring {winner_score:.2f} while giving up "
            f"{loser_score:.2f} in return."
        )
    else:
        title = f"AI judgement: {winner} favored ({confidence})"
        body = (
            f"{winner} is projected to deal {winner_score:.2f} damage while taking {loser_score:.2f} "
            "in the return strike."
        )

    return {
        "title": title,
        "body": f"{body}{damage_context if basis == 'points_removed' else points_context}",
        "winner": None if close else winner,
        "confidence": "close" if close else confidence,
        "basis": basis,
        "outgoing_score": outgoing_score,
        "incoming_score": incoming_score,
        "edge": edge,
    }


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
