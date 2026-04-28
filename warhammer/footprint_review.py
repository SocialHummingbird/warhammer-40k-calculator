from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from warhammer.base_sizes import summarize_footprint_override_template


def render_footprint_review_report(data_dir: Path, *, high_score_threshold: float = 0.8, row_limit: int = 30) -> str:
    data_dir = Path(data_dir)
    review_rows = _read_csv(data_dir / "unit_footprint_review.csv")
    suggestion_rows = _read_csv(data_dir / "unit_footprint_suggestions.csv")
    override_rows = _read_csv(data_dir / "unit_footprint_overrides.csv")
    rejection_rows = _read_csv(data_dir / "unit_footprint_rejections.csv")
    override_template_rows = _read_csv(data_dir / "unit_footprint_override_template.csv")
    review_queue_rows = _read_csv(data_dir / "unit_footprint_review_queue.csv")
    footprint_rows = _read_csv(data_dir / "unit_footprints.csv")
    template_summary = summarize_footprint_override_template(override_template_rows, override_rows)
    template_counts = template_summary["counts"]

    high_suggestions = [
        row
        for row in suggestion_rows
        if _csv_int(row.get("suggestion_rank", "")) == 1 and _csv_float(row.get("suggestion_score", "")) >= high_score_threshold
    ]
    high_suggestions.sort(
        key=lambda row: (
            -_csv_float(row.get("suggestion_score", "")),
            row.get("faction", "").casefold(),
            row.get("unit_name", "").casefold(),
        )
    )

    lines = [
        "# Unit Footprint Review",
        "",
        "This report summarizes official base-size matching for Battlefield blob sizing. Suggestions are review aids only; only rows promoted into `unit_footprint_overrides.csv` affect generated footprints.",
        "",
        "## Summary",
        "",
        f"- Footprint rows: {len(footprint_rows)}",
        f"- Review rows: {len(review_rows)}",
        f"- Manual overrides: {len(override_rows)}",
        f"- Rejected suggestions: {len(rejection_rows)}",
        f"- Override template rows: {len(override_template_rows)}",
        f"- Prioritized review queue rows: {len(review_queue_rows)}",
        f"- Suggestion rows: {len(suggestion_rows)}",
        f"- High-confidence rank-1 suggestions (score >= {high_score_threshold:.2f}): {len(high_suggestions)}",
        "",
        "## Footprint Status",
        "",
        *_count_lines(footprint_rows, "footprint_status"),
        "",
        "## Review Categories",
        "",
        *_count_lines(review_rows, "review_category"),
        "",
        "## Non-Numeric Footprint Estimates",
        "",
        "These official guide rows name a base type instead of numeric dimensions. Battlefield mode uses conservative derived footprints for planning display.",
        "",
        *_count_lines(
            [row for row in review_rows if row.get("review_category") == "non_numeric_base"],
            "base_type",
        ),
        "",
        "## Review Severity",
        "",
        *_count_lines(review_rows, "review_severity"),
        "",
        "## High-Confidence Suggestions",
        "",
    ]
    if high_suggestions:
        lines.extend(
            [
                "| Score | Unit | Faction | Suggested guide row | Base | Unit ID |",
                "| --- | --- | --- | --- | --- | --- |",
                *[_suggestion_line(row) for row in high_suggestions[:row_limit]],
            ]
        )
        if len(high_suggestions) > row_limit:
            lines.append(f"- {len(high_suggestions) - row_limit} additional high-confidence suggestions omitted from this report sample.")
    else:
        lines.append("No high-confidence suggestions remain at this threshold.")
    lines.extend(
        [
        "",
        "## Override Template Review Status",
        "",
            f"- Suggestion-ready rows: {template_counts['accept_suggestion_ready']}",
            f"- Manual override-ready rows: {template_counts['override_ready']}",
            f"- Invalid reviewed rows: {template_counts['invalid']}",
            f"- Blank rows: {template_counts['blank']}",
            f"- Rejected/skipped rows: {template_counts['rejected']}",
            f"- Already overridden rows: {template_counts['already_overridden']}",
            "",
            "## Prioritized Manual Review Queue",
            "",
            *_count_lines(review_queue_rows, "review_priority"),
            "",
            *_review_queue_table(review_queue_rows, row_limit=row_limit),
            "",
            "## Largest Unmatched Factions",
            "",
            *_count_lines(
                [row for row in review_rows if row.get("review_category") == "unmatched_unit"],
                "faction",
                limit=15,
            ),
            "",
            "## Override Workflow",
            "",
            "For generated suggestions, dry-run reviewed candidates first:",
            "",
            "```powershell",
            "python accept_footprint_suggestions.py --min-score 0.8",
            "```",
            "",
            "Promote or reject only reviewed suggestions by unit id:",
            "",
            "```powershell",
            "python accept_footprint_suggestions.py --min-score 0.8 --unit-id <unit-id> --apply",
            "python reject_footprint_suggestions.py --min-score 0.8 --unit-id <unit-id> --apply",
            "```",
            "",
            "For unmatched units, review `unit_footprint_override_template.csv`. Set `review_decision` to `accept_suggestion` for the prefilled official-guide suggestion, or `override` after filling the `override_*` fields.",
            "",
            "Use the prioritized queue when you want a smaller manual batch. It sorts safer/high-value review rows first, but it does not apply any suggestion automatically:",
            "",
            "```powershell",
            "python plan_footprint_review.py --limit 50 --output data\\10e\\latest\\unit_footprint_review_queue.csv",
            "python plan_footprint_review.py --priority high --output data\\10e\\latest\\unit_footprint_review_queue_high.csv",
            "```",
            "",
            "```powershell",
            "python promote_footprint_override_template.py --template data\\10e\\latest\\unit_footprint_override_template.csv",
            "python promote_footprint_override_template.py --template data\\10e\\latest\\unit_footprint_override_template.csv --apply",
            "python promote_footprint_override_template.py --queue data\\10e\\latest\\unit_footprint_review_queue.csv",
            "python promote_footprint_override_template.py --queue data\\10e\\latest\\unit_footprint_review_queue.csv --apply",
            "python promote_footprint_override_template.py --queue data\\10e\\latest\\unit_footprint_review_queue.csv --record-rejections --apply",
            "```",
            "",
            "Regenerate generated data after changing overrides or rejections:",
            "",
            "```powershell",
            "python update_database.py --skip-fetch --skip-ml",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_footprint_review_report(
    data_dir: Path,
    output: Path | None = None,
    *,
    high_score_threshold: float = 0.8,
    row_limit: int = 30,
) -> Path:
    output = Path(output) if output else Path(data_dir) / "unit_footprint_review.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_footprint_review_report(
            data_dir,
            high_score_threshold=high_score_threshold,
            row_limit=row_limit,
        ),
        encoding="utf-8",
    )
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _count_lines(rows: Iterable[dict[str, str]], key: str, *, limit: int | None = None) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        value = (row.get(key) or "unknown").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ["- None"]
    items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        items = items[:limit]
    return [f"- {label}: {count}" for label, count in items]


def _suggestion_line(row: dict[str, str]) -> str:
    return (
        f"| {row.get('suggestion_score', '')} "
        f"| {_md_cell(row.get('unit_name', ''))} "
        f"| {_md_cell(row.get('faction', ''))} "
        f"| {_md_cell(row.get('guide_unit_name', ''))} "
        f"| {_md_cell(row.get('base_size_text', '') or row.get('base_type', ''))} "
        f"| `{row.get('unit_id', '')}` |"
    )


def _review_queue_table(rows: list[dict[str, str]], *, row_limit: int) -> list[str]:
    if not rows:
        return ["No prioritized queue rows are available."]
    selected = rows[:row_limit]
    lines = [
        "| Rank | Priority | Unit | Faction | Suggestion | Base | Page | Suggested action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *[_review_queue_line(row) for row in selected],
    ]
    if len(rows) > row_limit:
        lines.append(f"- {len(rows) - row_limit} additional queue rows omitted from this report sample.")
    return lines


def _review_queue_line(row: dict[str, str]) -> str:
    suggestion = row.get("suggested_guide_unit_name", "")
    base = row.get("suggested_base_size_text", "")
    page = row.get("suggested_source_page", "")
    action = _queue_action_hint(row)
    return (
        f"| {row.get('review_rank', '')} "
        f"| {_md_cell(row.get('review_priority', ''))} "
        f"| {_md_cell(row.get('unit_name', ''))} "
        f"| {_md_cell(row.get('faction_contains', ''))} "
        f"| {_md_cell(suggestion or 'research required')} "
        f"| {_md_cell(base or 'unknown')} "
        f"| {_md_cell(page or 'unknown')} "
        f"| {_md_cell(action)} |"
    )


def _queue_action_hint(row: dict[str, str]) -> str:
    priority = row.get("review_priority", "")
    suggestion = row.get("suggested_guide_unit_name", "")
    if not suggestion:
        return "research base and fill override fields"
    if priority == "review_suggestion_high":
        return "verify same datasheet, then accept/reject/override"
    return "compare source names before accepting"


def _md_cell(value: str) -> str:
    return str(value or "").replace("|", "\\|")


def _csv_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _csv_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
