from __future__ import annotations

from typing import Any, Iterable

from .base import RuleCapability, Ruleset
from .registry import available_rulesets


def capability_to_dict(capability: RuleCapability) -> dict[str, Any]:
    return {
        "key": capability.key,
        "label": capability.label,
        "status": capability.status,
        "notes": list(capability.notes),
    }


def ruleset_capabilities(edition: str) -> list[dict[str, Any]]:
    ruleset = available_rulesets().get(str(edition or "").strip())
    if ruleset is None:
        return []
    return [capability_to_dict(capability) for capability in getattr(ruleset, "capabilities", ())]


def ruleset_registry_payload() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for edition, ruleset in sorted(available_rulesets().items()):
        capabilities = [capability_to_dict(capability) for capability in getattr(ruleset, "capabilities", ())]
        payload[edition] = ruleset_payload(ruleset, capabilities=capabilities)
    return payload


def ruleset_payload(ruleset: Ruleset, *, capabilities: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    capability_rows = capabilities if capabilities is not None else [
        capability_to_dict(capability) for capability in getattr(ruleset, "capabilities", ())
    ]
    return {
        "label": getattr(ruleset, "label", getattr(ruleset, "edition", "unknown")),
        "capability_count": len(capability_rows),
        "capabilities": capability_rows,
    }


def capability_key_drift(edition: str, generated_capabilities: Iterable[Any]) -> dict[str, Any] | None:
    ruleset = available_rulesets().get(str(edition or "").strip())
    if ruleset is None:
        return None
    expected_keys = [capability.key for capability in getattr(ruleset, "capabilities", ())]
    actual_keys = [
        str(capability.get("key") or "").strip()
        for capability in generated_capabilities
        if isinstance(capability, dict) and str(capability.get("key") or "").strip()
    ]
    missing = sorted(set(expected_keys) - set(actual_keys))
    extra = sorted(set(actual_keys) - set(expected_keys))
    ok = bool(expected_keys) and not missing and not extra and len(actual_keys) == len(expected_keys)
    return {
        "ok": ok,
        "expected_count": len(expected_keys),
        "actual_count": len(actual_keys),
        "missing_keys": missing,
        "extra_keys": extra,
    }
