from __future__ import annotations

from typing import Any, Mapping

from warhammer.data_review import source_info_from_metadata


REVIEW_THRESHOLD_KEYS = {
    "audit_warnings",
    "suspicious_weapon_warnings",
    "unit_profile_warnings",
    "loadout_warnings",
    "no_weapon_units",
}


def render_data_review_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(build_data_review_summary_lines(payload)) + "\n"


def build_current_review_thresholds(payload: Mapping[str, Any]) -> dict[str, int]:
    return {
        "audit_warnings": _as_int(_nested(payload, "audit_report", "summary", "warning")),
        "suspicious_weapon_warnings": _as_int(_nested(payload, "suspicious_weapon_summary", "by_severity", "warning")),
        "unit_profile_warnings": _as_int(_nested(payload, "unit_profile_summary", "by_severity", "warning")),
        "loadout_warnings": _as_int(_nested(payload, "loadout_summary", "by_severity", "warning")),
        "no_weapon_units": _as_int(_nested(payload, "weapon_coverage_summary", "no_weapon_total")),
    }


def normalize_review_thresholds(raw_thresholds: Mapping[str, Any] | None) -> dict[str, int]:
    if not raw_thresholds:
        return {}
    thresholds: dict[str, int] = {}
    for key in sorted(REVIEW_THRESHOLD_KEYS):
        if key not in raw_thresholds:
            continue
        value = _as_int(raw_thresholds.get(key))
        if value >= 0:
            thresholds[key] = value
    return thresholds


def build_review_threshold_summary_lines(thresholds: Mapping[str, int]) -> list[str]:
    if not thresholds:
        return []
    labels = {
        "audit_warnings": "audit warnings",
        "suspicious_weapon_warnings": "suspicious weapon warnings",
        "unit_profile_warnings": "unit profile warnings",
        "loadout_warnings": "loadout warnings",
        "no_weapon_units": "no-weapon units",
    }
    return ["Review gate thresholds:"] + [
        f"- {labels.get(key, key)}: {thresholds[key]}"
        for key in sorted(thresholds)
    ]


def build_data_review_gate_failures(
    payload: Mapping[str, Any],
    *,
    fail_on_warnings: bool = False,
    thresholds: Mapping[str, int] | None = None,
) -> list[str]:
    failures: list[str] = []
    thresholds = thresholds or {}

    status = _nested(payload, "edition_status", "status")
    if status and status != "ready":
        failures.append(f"edition status is {status}")

    verification = _mapping(payload.get("verification_report"))
    if verification and not verification.get("ok", False):
        failures.append(
            "artifact verification failed: "
            f"{verification.get('failed_count', 0)} failed of {verification.get('artifact_count', 0)} checks"
        )

    schema_status = _mapping(_nested(payload, "schema_summary", "by_status"))
    for status_name in ["fail", "error"]:
        count = _as_int(schema_status.get(status_name))
        if count:
            failures.append(f"schema review has {count} {status_name} rows")

    audit_summary = _mapping(_nested(payload, "audit_report", "summary"))
    _append_severity_failures(
        failures,
        "audit samples",
        audit_summary,
        fail_on_warnings=fail_on_warnings,
        max_warnings=thresholds.get("audit_warnings"),
    )
    _append_severity_failures(
        failures,
        "suspicious weapons",
        _mapping(_nested(payload, "suspicious_weapon_summary", "by_severity")),
        fail_on_warnings=fail_on_warnings,
        max_warnings=thresholds.get("suspicious_weapon_warnings"),
    )
    _append_severity_failures(
        failures,
        "unit profiles",
        _mapping(_nested(payload, "unit_profile_summary", "by_severity")),
        fail_on_warnings=fail_on_warnings,
        max_warnings=thresholds.get("unit_profile_warnings"),
    )
    _append_severity_failures(
        failures,
        "loadout review",
        _mapping(_nested(payload, "loadout_summary", "by_severity")),
        fail_on_warnings=fail_on_warnings,
        max_warnings=thresholds.get("loadout_warnings"),
    )

    max_no_weapon_units = thresholds.get("no_weapon_units")
    if max_no_weapon_units is not None:
        no_weapon_total = _as_int(_nested(payload, "weapon_coverage_summary", "no_weapon_total"))
        if no_weapon_total > max_no_weapon_units:
            failures.append(f"weapon coverage has {no_weapon_total} no-weapon units, above threshold {max_no_weapon_units}")

    return failures


def build_data_review_summary_lines(payload: Mapping[str, Any]) -> list[str]:
    edition = payload.get("edition") or _nested(payload, "edition_status", "edition") or "unknown"
    status = _nested(payload, "edition_status", "status") or "unknown"
    lines = [f"Data review summary ({edition})", f"Edition status: {status}"]

    source = source_info_from_metadata(_mapping(payload.get("metadata")))
    if source:
        generated_at = source.get("generated_at") or "unknown"
        commit = source.get("commit_short") or source.get("commit") or "unknown"
        dirty = " dirty" if source.get("dirty") else ""
        lines.append(f"Source: {source.get('remote_origin') or 'unknown'} @ {commit}{dirty}")
        lines.append(f"Generated: {generated_at}")

    counts = _nested(payload, "metadata", "counts") or _nested(payload, "edition_status", "counts")
    if isinstance(counts, Mapping):
        lines.append(f"Rows: {_format_counts(counts)}")

    verification = _mapping(payload.get("verification_report"))
    if verification:
        status_label = "pass" if verification.get("ok") else "fail"
        lines.append(
            "Artifacts: "
            f"{status_label}, {verification.get('ok_count', 0)}/{verification.get('artifact_count', 0)} ok"
            f", {verification.get('failed_count', 0)} failed"
        )

    audit_summary = _nested(payload, "audit_report", "summary")
    if isinstance(audit_summary, Mapping):
        lines.append(
            "Audit samples: "
            f"{audit_summary.get('error', 0)} errors, "
            f"{audit_summary.get('warning', 0)} warnings, "
            f"{audit_summary.get('info', 0)} info"
        )

    _append_profile_line(lines, "Suspicious weapons", payload.get("suspicious_weapon_summary"))
    _append_profile_line(lines, "Unit profile issues", payload.get("unit_profile_summary"), count_key="issue_total")
    _append_profile_line(lines, "Loadout review rows", payload.get("loadout_summary"))

    coverage = _mapping(payload.get("weapon_coverage_summary"))
    if coverage:
        lines.append(
            "Weapon coverage: "
            f"{coverage.get('no_weapon_total', 0)} no-weapon units / {coverage.get('total', 0)} units"
            f" ({_format_counts(_mapping(coverage.get('by_coverage')))})"
        )

    schema = _mapping(payload.get("schema_summary"))
    if schema:
        lines.append(f"Schema: {schema.get('total', 0)} tables ({_format_counts(_mapping(schema.get('by_status')))})")

    variants = _mapping(payload.get("unit_variant_summary"))
    if variants:
        lines.append(
            "Duplicate names: "
            f"{variants.get('duplicate_names', 0)} names, "
            f"{variants.get('total_rows', 0)} rows, "
            f"max variants {variants.get('max_variant_count', 0)}"
        )

    modifiers = _mapping(payload.get("ability_modifier_summary"))
    if modifiers:
        lines.append(
            "Ability modifiers: "
            f"{modifiers.get('total', 0)} rows"
            f" ({_format_counts(_mapping(modifiers.get('by_type')))})"
        )

    catalogue = _mapping(payload.get("source_catalogue_summary"))
    totals = _mapping(catalogue.get("totals")) if catalogue else {}
    if catalogue:
        lines.append(
            "Source catalogues: "
            f"{catalogue.get('total', 0)} files, "
            f"{totals.get('units', 0)} units, "
            f"{totals.get('weapon_profiles', 0)} weapons, "
            f"{totals.get('suspicious_weapon_profiles', 0)} suspicious weapons"
        )

    review_files = payload.get("review_files")
    if isinstance(review_files, list):
        lines.append(f"Review files: {len(review_files)} available")

    model_files = payload.get("model_files")
    if isinstance(model_files, list) and model_files:
        lines.append(f"ML files: {len(model_files)} available")

    return lines


def _append_profile_line(
    lines: list[str],
    label: str,
    summary: Any,
    *,
    count_key: str = "total",
) -> None:
    mapping = _mapping(summary)
    if not mapping:
        return
    line = f"{label}: {mapping.get(count_key, 0)}"
    severity = _format_counts(_mapping(mapping.get("by_severity")))
    category = _format_counts(_mapping(mapping.get("by_category")))
    details = [detail for detail in [severity, category] if detail]
    if details:
        line += f" ({'; '.join(details)})"
    lines.append(line)


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _append_severity_failures(
    failures: list[str],
    label: str,
    counts: Mapping[str, Any],
    *,
    fail_on_warnings: bool,
    max_warnings: int | None = None,
) -> None:
    errors = _as_int(counts.get("error"))
    if errors:
        failures.append(f"{label} contains {errors} errors")
    warnings = _as_int(counts.get("warning"))
    if fail_on_warnings and warnings:
        failures.append(f"{label} contains {warnings} warnings")
    elif max_warnings is not None and warnings > max_warnings:
        failures.append(f"{label} contains {warnings} warnings, above threshold {max_warnings}")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_counts(counts: Mapping[str, Any]) -> str:
    items = [(str(key), value) for key, value in counts.items()]
    if not items:
        return "none"
    return ", ".join(f"{key} {value}" for key, value in sorted(items))
