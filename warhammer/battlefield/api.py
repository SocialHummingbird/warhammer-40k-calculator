from __future__ import annotations

from typing import Any, Dict

from ..web_state import EditionDataset
from .army import validate_army
from .maps import battlefield_templates_payload as _templates_payload
from .maps import generate_map
from .models import action_from_dict, army_from_dict, state_from_dict, to_dict
from .simulation import (
    ai_plan,
    autoplay_turn,
    available_actions,
    initial_battle_state,
    resolve_action,
    state_from_payload,
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
        "state": to_dict(state),
    }


def ai_plan_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    limit = max(1, int(payload.get("limit") or 8))
    plan = ai_plan(state, dataset.units_by_id, edition=edition, limit=limit)
    plan["state"] = to_dict(state)
    return plan


def resolve_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    action = action_from_dict(payload.get("action") or {})
    outcome = resolve_action(state, action, dataset.units_by_id, edition=edition)
    return {
        "state": to_dict(outcome.state),
        "outcome": {
            "action": to_dict(outcome.action),
            "log_entry": outcome.log_entry,
            "damage": outcome.damage,
            "points_removed": outcome.points_removed,
            "score_delta": outcome.score_delta,
        },
    }


def autoplay_payload(payload: Dict[str, Any], dataset: EditionDataset, *, edition: str) -> Dict[str, Any]:
    state = state_from_payload(payload, dataset.units_by_id)
    return autoplay_turn(state, dataset.units_by_id, edition=edition)


def new_state_payload(payload: Dict[str, Any], dataset: EditionDataset) -> Dict[str, Any]:
    template_id = str(payload.get("template_id") or "strike_force_44x60")
    battle_map = generate_map(template_id)
    armies = [army_from_dict(row) for row in payload.get("armies", [])]
    return {"state": to_dict(initial_battle_state(battle_map, armies, dataset.units_by_id))}
