from __future__ import annotations

from typing import Any, Dict, Optional

from .context import EngagementContext


def contexts_from_payload(payload: Dict[str, Any]) -> tuple[EngagementContext, EngagementContext]:
    outgoing_payload = payload.get("outgoing_context") or payload.get("context") or {}
    incoming_payload = payload.get("incoming_context") or {}
    if not isinstance(outgoing_payload, dict) or not isinstance(incoming_payload, dict):
        raise ValueError("context values must be JSON objects")
    return context_from_payload(outgoing_payload), context_from_payload(incoming_payload)


def context_from_payload(payload: Dict[str, Any]) -> EngagementContext:
    return EngagementContext(
        attacker_moved=optional_bool(payload.get("attacker_moved", False), field_name="attacker_moved"),
        attacker_advanced=optional_bool(payload.get("attacker_advanced", False), field_name="attacker_advanced"),
        target_within_half_range=optional_bool(
            payload.get("target_within_half_range", False),
            field_name="target_within_half_range",
        ),
        target_in_cover=optional_bool(payload.get("target_in_cover", False), field_name="target_in_cover"),
        target_model_count=optional_positive_int(payload.get("target_model_count"), field_name="target_model_count"),
    )


def optional_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError(f"{field_name} must be true or false")
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    raise ValueError(f"{field_name} must be true or false")


def optional_positive_int(value: Any, *, field_name: str) -> Optional[int]:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def optional_weapon_name(value: Any) -> Optional[str]:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError("weapon filters must be strings")
    value = value.strip()
    if not value or value.casefold() == "__all__":
        return None
    return value


def optional_unit_id(value: Any) -> Optional[str]:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError("unit ids must be strings")
    value = value.strip()
    return value or None


def query_limit(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 300
    return max(1, min(1000, value))
