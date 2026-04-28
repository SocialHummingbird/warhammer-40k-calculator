"""Tactical battlefield planner MVP.

This package intentionally models a transparent planning layer over the
existing damage calculator. It is not a complete tournament rules simulator.
"""

from .api import (
    actions_payload,
    advance_phase_payload,
    ai_plan_payload,
    autoplay_payload,
    battlefield_templates_payload,
    new_state_payload,
    resolve_payload,
    validate_army_payload,
    validate_state_payload,
)

__all__ = [
    "actions_payload",
    "advance_phase_payload",
    "ai_plan_payload",
    "autoplay_payload",
    "battlefield_templates_payload",
    "new_state_payload",
    "resolve_payload",
    "validate_army_payload",
    "validate_state_payload",
]
