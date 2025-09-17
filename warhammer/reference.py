"""Generate keyword and ability summaries from loaded unit profiles."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .profiles import UnitProfile


def build_reference(units: Iterable[UnitProfile]) -> str:
    keyword_to_units: Dict[str, List[str]] = defaultdict(list)
    ability_to_units: Dict[str, Dict[str, object]] = defaultdict(lambda: {"text": "", "units": set()})

    for unit in units:
        for keyword in unit.keywords:
            keyword_to_units[keyword].append(unit.name)
        for ability in unit.abilities:
            payload = ability_to_units[ability.name]
            if not payload["text"]:
                payload["text"] = ability.text.strip()
            elif ability.text.strip() and payload["text"] != ability.text.strip():
                payload["text"] = f"{payload['text']}\n\n{ability.text.strip()}"
            payload["units"].add(unit.name)

    lines: List[str] = []
    lines.append("# Keyword Reference")
    lines.append("")
    for keyword in sorted(keyword_to_units.keys(), key=str.lower):
        units_list = ", ".join(sorted(keyword_to_units[keyword])) or "None"
        lines.append(f"## {keyword}")
        lines.append("")
        lines.append(f"- Units: {units_list}")
        lines.append("")

    lines.append("# Ability Reference")
    lines.append("")
    for ability_name in sorted(ability_to_units.keys(), key=str.lower):
        payload = ability_to_units[ability_name]
        units_list = ", ".join(sorted(payload["units"])) or "None"
        text = payload["text"] or "(No description provided.)"
        lines.append(f"## {ability_name}")
        lines.append("")
        lines.append(f"- Units: {units_list}")
        lines.append("")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)
