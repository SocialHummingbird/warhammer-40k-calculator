from __future__ import annotations

from typing import Dict

from .base import Ruleset
from .tenth import TenthEditionRules


_RULESETS: Dict[str, Ruleset] = {
    "10e": TenthEditionRules(),
}


def get_ruleset(edition: str = "10e") -> Ruleset:
    key = (edition or "10e").strip().casefold()
    try:
        return _RULESETS[key]
    except KeyError as exc:
        supported = ", ".join(sorted(_RULESETS))
        raise ValueError(f"Unsupported rules edition {edition!r}; supported editions: {supported}") from exc


def available_rulesets() -> Dict[str, Ruleset]:
    return dict(_RULESETS)
