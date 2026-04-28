from __future__ import annotations

from typing import Any, Dict

from ..web_state import EditionDataset
from .army import validate_army
from .maps import battlefield_templates_payload as _templates_payload
from .maps import generate_map
from .models import action_from_dict, army_from_dict, map_from_dict, state_from_dict, to_dict
from .simulation import (
    advance_phase,
    ai_plan,
    autoplay_battle,
    autoplay_turn,
    available_actions,
    battle_summary,
    initial_battle_state,
    resolve_action,
    state_from_payload,
    unavailable_actions,
    validate_map,
    validate_state,
)


def battlefield_templates_payload() -> Dict[str, Any]:
    return _templates_payload()


def validate_army_payload(payload: Dict[str, Any], dataset: EditionDataset) -> Dict[str, Any]:
    return validate_army(army_from_dict(payload.get("army") or payload), dataset.units_by_id)


def validate_state_payload(payload: Dict[str, Any], dataset: EditionDataset) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    return validate_state(state, dataset.units_by_id)


def actions_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    return {
        "actions": [to_dict(action) for action in available_actions(state, dataset.units_by_id, edition=edition)],
        "unavailable_actions": unavailable_actions(state, dataset.units_by_id, edition=edition),
        "state": to_dict(state),
        "summary": battle_summary(state, dataset.units_by_id),
    }


def ai_plan_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    limit = max(1, int(payload.get("limit") or 8))
    plan = ai_plan(state, dataset.units_by_id, edition=edition, limit=limit)
    plan["unavailable_actions"] = unavailable_actions(state, dataset.units_by_id, edition=edition)
    plan["state"] = to_dict(state)
    return plan


def resolve_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    action = action_from_dict(payload.get("action") or {})
    outcome = resolve_action(state, action, dataset.units_by_id, edition=edition)
    return {
        "state": to_dict(outcome.state),
        "summary": battle_summary(outcome.state, dataset.units_by_id),
        "outcome": {
            "action": to_dict(outcome.action),
            "log_entry": outcome.log_entry,
            "damage": outcome.damage,
            "points_removed": outcome.points_removed,
            "score_delta": outcome.score_delta,
        },
    }


def advance_phase_payload(payload: Dict[str, Any], dataset: EditionDataset) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    next_state = advance_phase(state)
    return {
        "state": to_dict(next_state),
        "log_entry": next_state.log[-1] if next_state.log else {},
        "summary": battle_summary(next_state, dataset.units_by_id),
    }


def autoplay_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    turns = max(1, min(20, int(payload.get("turns") or 1)))
    if turns == 1:
        return autoplay_turn(state, dataset.units_by_id, edition=edition)
    return autoplay_battle(state, dataset.units_by_id, edition=edition, turns=turns)


def new_state_payload(payload: Dict[str, Any], dataset: EditionDataset) -> Dict[str, Any]:
    template_id = str(payload.get("template_id") or "strike_force_44x60")
    battle_map = map_from_dict(payload["map"]) if isinstance(payload.get("map"), dict) else generate_map(template_id)
    map_validation = validate_map(battle_map)
    if map_validation["errors"]:
        raise ValueError("; ".join(map_validation["errors"]))
    armies = [army_from_dict(row) for row in payload.get("armies", [])]
    battle_state = initial_battle_state(battle_map, armies, dataset.units_by_id)
    return {
        "state": to_dict(battle_state),
        "summary": battle_summary(battle_state, dataset.units_by_id),
        "warnings": map_validation["warnings"],
    }
