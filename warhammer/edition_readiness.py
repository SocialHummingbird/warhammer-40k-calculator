from __future__ import annotations

from pathlib import Path
from typing import Any


def render_edition_readiness_report(status: dict[str, Any], *, project_root: Path | None = None) -> str:
    """Render a Markdown report for edition readiness and migration work."""

    edition = str(status.get("edition") or "unknown")
    supported = [str(value) for value in status.get("supported_rules_editions", [])]
    blockers = [str(value) for value in status.get("blockers", [])]
    counts = status.get("counts") if isinstance(status.get("counts"), dict) else {}
    audit = status.get("audit_summary") if isinstance(status.get("audit_summary"), dict) else {}
    source = status.get("source") if isinstance(status.get("source"), dict) else {}
    capabilities = status.get("rule_capabilities") if isinstance(status.get("rule_capabilities"), list) else []

    lines = [
        "# Edition Readiness Report",
        "",
        "## Summary",
        f"- Edition: `{edition}`",
        f"- Status: `{status.get('status', 'unknown')}`",
        f"- Calculations enabled: {_yes_no(status.get('calculations_enabled'))}",
        f"- Ruleset available: {_yes_no(status.get('rules_available'))}",
        f"- Supported rulesets: {', '.join(f'`{item}`' for item in supported) or 'none'}",
        f"- Data directory: `{_display_path(status.get('data_dir'), project_root=project_root)}`",
        f"- Source commit: `{source.get('commit', '') or 'unknown'}`",
        "",
        "## Data Counts",
        "",
        "| Table | Rows |",
        "| --- | ---: |",
    ]
    for key in ("units", "weapons", "abilities", "keywords", "unit_keywords"):
        lines.append(f"| {key} | {_int_text(counts.get(key))} |")

    lines.extend(
        [
            "",
            "## Audit Summary",
            "",
            "| Severity | Rows |",
            "| --- | ---: |",
            f"| Errors | {_int_text(audit.get('error'))} |",
            f"| Warnings | {_int_text(audit.get('warning'))} |",
            f"| Info | {_int_text(audit.get('info'))} |",
            f"| Total | {_int_text(audit.get('total'))} |",
            "",
            "## Ruleset Capability Coverage",
            "",
        ]
    )
    if capabilities:
        lines.extend(["| Capability | Status | Notes |", "| --- | --- | --- |"])
        for capability in capabilities:
            if not isinstance(capability, dict):
                continue
            notes = capability.get("notes") if isinstance(capability.get("notes"), list) else []
            lines.append(
                "| "
                f"{capability.get('label', capability.get('key', 'unknown'))} | "
                f"{capability.get('status', 'unknown')} | "
                f"{'; '.join(str(note) for note in notes)} |"
            )
    else:
        lines.append("No registered ruleset capabilities are available for this edition.")

    lines.extend(
        [
            "",
            "## Blockers",
        ]
    )
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None")

    lines.extend(["", "## Migration Checklist"])
    lines.extend(_migration_checklist(status))
    lines.append("")
    return "\n".join(lines)


def _migration_checklist(status: dict[str, Any]) -> list[str]:
    rules_available = bool(status.get("rules_available"))
    audit = status.get("audit_summary") if isinstance(status.get("audit_summary"), dict) else {}
    audit_errors = int(audit.get("error", 0) or 0)
    lines = [
        _check_line(rules_available, "Ruleset module exists and is registered in `warhammer.rules`."),
        _check_line(rules_available, "Edition-specific hit, wound, save, damage, and model-removal behavior is implemented."),
        _check_line(rules_available, "Edition-specific contextual mechanics are behind the ruleset interface."),
        _check_line(audit_errors == 0, "Generated data has no audit error samples."),
        _check_line(bool(status.get("calculations_enabled")), "Web/API calculations are enabled for this edition."),
    ]
    if not rules_available:
        lines.append("- [ ] Add focused parity tests for changed edition mechanics before enabling calculations.")
        lines.append("- [ ] Generate a real data snapshot for the new edition and keep it separate from `10e` data.")
    return lines


def _check_line(done: bool, text: str) -> str:
    return f"- [{'x' if done else ' '}] {text}"


def _yes_no(value: object) -> str:
    return "yes" if bool(value) else "no"


def _int_text(value: object) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"


def _display_path(value: object, *, project_root: Path | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    if project_root is None:
        return text
    path = Path(text)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        return text
