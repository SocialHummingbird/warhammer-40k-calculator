from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .rules import available_rulesets, ruleset_capabilities


DEFAULT_EDITION = "10e"


def edition_dir_name(edition: str, *, default: str = DEFAULT_EDITION) -> str:
    cleaned = (edition or default).strip().lower()
    return cleaned or default


def build_edition_status(
    csv_dir: Path,
    requested_edition: str,
    source_after: dict[str, object],
    audit_report: dict[str, object],
    *,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = metadata if metadata is not None else read_metadata(csv_dir)
    metadata_edition = str(metadata.get("rules_edition") or "").strip()
    edition = metadata_edition or edition_dir_name(requested_edition)
    rulesets = available_rulesets()
    supported_rules = sorted(rulesets)
    rules_available = edition in supported_rules
    audit_summary = audit_report.get("summary", {}) if isinstance(audit_report.get("summary"), dict) else {}
    audit_errors = int(audit_summary.get("error", 0) or 0)
    calculable = rules_available and audit_errors == 0
    blockers: list[str] = []
    if not rules_available:
        blockers.append("Ruleset not implemented")
    if audit_errors:
        blockers.append(f"Audit has {audit_errors} error samples")

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "edition": edition,
        "requested_edition": edition_dir_name(requested_edition),
        "metadata_edition": metadata_edition,
        "rules_available": rules_available,
        "supported_rules_editions": supported_rules,
        "rule_capabilities": ruleset_capabilities(edition),
        "calculations_enabled": calculable,
        "status": "ready" if calculable else "blocked",
        "blockers": blockers,
        "data_dir": str(csv_dir),
        "source": {
            "remote_origin": source_after.get("remote_origin", ""),
            "branch": source_after.get("branch", ""),
            "commit": source_after.get("commit", ""),
            "commit_date": source_after.get("commit_date", ""),
            "commit_subject": source_after.get("commit_subject", ""),
            "dirty": bool(source_after.get("dirty")),
        },
        "counts": metadata.get("counts", {}),
        "audit_summary": audit_summary,
    }


def read_metadata(csv_dir: Path) -> dict[str, object]:
    path = Path(csv_dir) / "metadata.json"
    if not path.exists():
        return {}
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
