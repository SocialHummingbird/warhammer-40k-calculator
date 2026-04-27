from __future__ import annotations

from typing import Any, Dict

from . import api_payloads as api_payload_service
from .matchups import calculate_matchup
from .ml.advisory import ml_judgement_from_result
from .web_state import AppState, requested_rules_edition


def calculate_from_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    attacker = dataset.require_unit(
        str(payload.get("attacker", "")),
        unit_id=api_payload_service.optional_unit_id(payload.get("attacker_id")),
    )
    defender = dataset.require_unit(
        str(payload.get("defender", "")),
        unit_id=api_payload_service.optional_unit_id(payload.get("defender_id")),
    )
    mode = str(payload.get("mode", "ranged")).lower()
    if mode not in {"ranged", "melee"}:
        raise ValueError("mode must be ranged or melee")

    outgoing_context, incoming_context = api_payload_service.contexts_from_payload(payload)
    outgoing_weapon = api_payload_service.optional_weapon_name(payload.get("outgoing_weapon"))
    incoming_weapon = api_payload_service.optional_weapon_name(payload.get("incoming_weapon"))
    outgoing_multiplier = api_payload_service.optional_positive_int(
        payload.get("outgoing_multiplier", 1),
        field_name="outgoing_multiplier",
    ) or 1
    incoming_multiplier = api_payload_service.optional_positive_int(
        payload.get("incoming_multiplier", 1),
        field_name="incoming_multiplier",
    ) or 1

    result_payload = calculate_matchup(
        attacker,
        defender,
        mode,
        outgoing_context=outgoing_context,
        incoming_context=incoming_context,
        outgoing_weapon=outgoing_weapon,
        incoming_weapon=incoming_weapon,
        outgoing_multiplier=outgoing_multiplier,
        incoming_multiplier=incoming_multiplier,
        edition=edition,
    )
    ml_judgement = ml_judgement_from_result(
        state.ml_model_for_edition(edition),
        attacker=attacker,
        defender=defender,
        mode=mode,
        result=result_payload,
        edition=edition,
    )
    if ml_judgement:
        result_payload["ml_judgement"] = ml_judgement
    return result_payload
