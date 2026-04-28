from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata
from urllib.request import urlretrieve


BASE_SIZE_GUIDE_URL = (
    "https://assets.warhammer-community.com/"
    "eng_07-01_warhammer_40000_core_rules_chapter_approved_tournament-companion-"
    "sqc1af88bj-vzxhp9xmid.pdf"
)
BASE_SIZE_GUIDE_SOURCE = "Warhammer 40,000 Chapter Approved Tournament Companion Base Size Guide"
BASE_SIZE_GUIDE_UPDATED = "January 2026"

BASE_SIZE_FIELDNAMES = [
    "source",
    "source_url",
    "source_updated",
    "page",
    "guide_faction",
    "guide_unit_name",
    "guide_model_name",
    "base_size_text",
    "base_type",
    "base_shape",
    "base_width_mm",
    "base_depth_mm",
]

UNIT_FOOTPRINT_FIELDNAMES = [
    "unit_id",
    "faction",
    "unit_name",
    "selection_type",
    "models_min",
    "models_max",
    "footprint_status",
    "base_type",
    "base_shape",
    "base_width_mm",
    "base_depth_mm",
    "guide_faction",
    "guide_unit_name",
    "guide_model_name",
    "source",
    "source_url",
    "source_updated",
    "match_method",
    "match_confidence",
    "review_reason",
]

FOOTPRINT_REVIEW_FIELDNAMES = [
    "review_severity",
    "review_category",
    *UNIT_FOOTPRINT_FIELDNAMES,
]
FOOTPRINT_OVERRIDE_FIELDNAMES = [
    "unit_id",
    "unit_name",
    "faction_contains",
    "base_size_text",
    "base_type",
    "base_shape",
    "base_width_mm",
    "base_depth_mm",
    "guide_faction",
    "guide_unit_name",
    "guide_model_name",
    "source",
    "source_url",
    "source_updated",
    "review_reason",
]
FOOTPRINT_SUGGESTION_FIELDNAMES = [
    "unit_id",
    "faction",
    "unit_name",
    "selection_type",
    "models_min",
    "models_max",
    "suggestion_rank",
    "suggestion_score",
    "suggestion_reason",
    "guide_faction",
    "guide_unit_name",
    "guide_model_name",
    "base_size_text",
    "base_type",
    "base_shape",
    "base_width_mm",
    "base_depth_mm",
    "source_page",
    "source",
    "source_url",
    "source_updated",
]
FOOTPRINT_REJECTION_FIELDNAMES = [
    "unit_id",
    "unit_name",
    "faction_contains",
    "guide_faction",
    "guide_unit_name",
    "guide_model_name",
    "base_size_text",
    "decision",
    "review_reason",
]
FOOTPRINT_OVERRIDE_TEMPLATE_FIELDNAMES = [
    "unit_id",
    "unit_name",
    "faction_contains",
    "selection_type",
    "models_min",
    "models_max",
    "review_category",
    "suggestion_score",
    "suggestion_reason",
    "suggested_guide_faction",
    "suggested_guide_unit_name",
    "suggested_guide_model_name",
    "suggested_base_size_text",
    "suggested_source_page",
    "suggested_source_url",
    "suggested_source_updated",
    "override_base_size_text",
    "override_base_type",
    "override_base_shape",
    "override_base_width_mm",
    "override_base_depth_mm",
    "override_guide_faction",
    "override_guide_unit_name",
    "override_guide_model_name",
    "review_decision",
    "review_notes",
]
FOOTPRINT_REVIEW_QUEUE_FIELDNAMES = [
    "review_rank",
    "review_priority",
    "review_hint",
    *FOOTPRINT_OVERRIDE_TEMPLATE_FIELDNAMES,
]

_ROW_PATTERN = re.compile(
    r"^(?P<unit>.+?)\s+"
    r"(?P<size>"
    r"(?:\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)?mm(?:\s+(?:Oval|Round)\s+Base)?)"
    r"|(?:Small|Large)\s+Flying\s+Base"
    r"|Hull"
    r"|Unique"
    r")$",
    re.IGNORECASE,
)
_SIZE_PATTERN = re.compile(
    r"^(?P<width>\d+(?:\.\d+)?)(?:x(?P<depth>\d+(?:\.\d+)?))?mm"
    r"(?:\s+(?P<label>Oval|Round)\s+Base)?$",
    re.IGNORECASE,
)
_SKIP_LINES = {
    "BASE SIZE GUIDE",
    "UNIT BASE SIZE",
    "CONTENTS",
    "IMPERIAL ARMOUR",
}


@dataclass(frozen=True)
class BaseSizeRecord:
    source: str
    source_url: str
    source_updated: str
    page: int
    guide_faction: str
    guide_unit_name: str
    guide_model_name: str
    base_size_text: str
    base_type: str
    base_shape: str
    base_width_mm: str
    base_depth_mm: str


def download_base_size_pdf(target: Path, *, url: str = BASE_SIZE_GUIDE_URL) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        urlretrieve(url, target)
    return target


def parse_base_size_pdf(path: Path) -> list[BaseSizeRecord]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised only when optional helper is absent
        raise RuntimeError("Install optional helper 'pypdf' to extract the official base-size PDF.") from exc

    reader = PdfReader(str(path))
    page_lines: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        if page_number < 14:
            continue
        text = page.extract_text() or ""
        page_lines.extend((page_number, line) for line in text.splitlines())
    return parse_base_size_lines(page_lines)


def parse_base_size_lines(page_lines: list[tuple[int, str]]) -> list[BaseSizeRecord]:
    records: list[BaseSizeRecord] = []
    current_faction = ""
    for page, raw_line in page_lines:
        line = " ".join(str(raw_line).strip().split())
        if not line or _is_skipped_line(line):
            continue

        match = _ROW_PATTERN.match(line)
        if match and current_faction:
            guide_unit_name, guide_model_name = split_guide_unit_name(match.group("unit"))
            base = parse_base_size_text(match.group("size"))
            records.append(
                BaseSizeRecord(
                    source=BASE_SIZE_GUIDE_SOURCE,
                    source_url=BASE_SIZE_GUIDE_URL,
                    source_updated=BASE_SIZE_GUIDE_UPDATED,
                    page=page,
                    guide_faction=current_faction,
                    guide_unit_name=guide_unit_name,
                    guide_model_name=guide_model_name,
                    base_size_text=match.group("size"),
                    base_type=base["base_type"],
                    base_shape=base["base_shape"],
                    base_width_mm=base["base_width_mm"],
                    base_depth_mm=base["base_depth_mm"],
                )
            )
            continue

        if _looks_like_faction_heading(line):
            current_faction = line
    return records


def parse_base_size_text(text: str) -> dict[str, str]:
    cleaned = " ".join(str(text).strip().split())
    size_match = _SIZE_PATTERN.match(cleaned)
    if size_match:
        width = size_match.group("width")
        depth = size_match.group("depth") or width
        label = (size_match.group("label") or "").casefold()
        base_shape = "oval" if label == "oval" or depth != width else "round"
        return {
            "base_type": base_shape,
            "base_shape": base_shape,
            "base_width_mm": width,
            "base_depth_mm": depth,
        }
    lowered = cleaned.casefold()
    if lowered == "hull":
        return {"base_type": "hull", "base_shape": "hull", "base_width_mm": "", "base_depth_mm": ""}
    if lowered == "unique":
        return {"base_type": "unique", "base_shape": "unique", "base_width_mm": "", "base_depth_mm": ""}
    if lowered in {"small flying base", "large flying base"}:
        base_type = lowered.replace(" ", "_")
        return {"base_type": base_type, "base_shape": "flying", "base_width_mm": "", "base_depth_mm": ""}
    return {"base_type": "unknown", "base_shape": "unknown", "base_width_mm": "", "base_depth_mm": ""}


def split_guide_unit_name(name: str) -> tuple[str, str]:
    if ":" not in name:
        return name.strip(), ""
    unit_name, model_name = name.split(":", 1)
    return unit_name.strip(), model_name.strip()


def write_base_size_guide_csv(records: list[BaseSizeRecord], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASE_SIZE_FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def load_base_size_guide_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def generate_unit_footprint_artifacts(
    *,
    units_csv: Path,
    base_size_csv: Path,
    unit_footprints_csv: Path,
    review_csv: Path,
    overrides_csv: Path | None = None,
    rejections_csv: Path | None = None,
    suggestions_csv: Path | None = None,
    override_template_csv: Path | None = None,
    review_queue_csv: Path | None = None,
) -> dict[str, int]:
    unit_rows = _read_csv(units_csv)
    base_rows = load_base_size_guide_csv(base_size_csv)
    override_rows = load_footprint_overrides_csv(overrides_csv) if overrides_csv and Path(overrides_csv).exists() else []
    rejection_rows = load_footprint_rejections_csv(rejections_csv) if rejections_csv and Path(rejections_csv).exists() else []
    footprints, review_rows = match_unit_footprints(unit_rows, base_rows, override_rows=override_rows)
    suggestions = build_footprint_suggestions(unit_rows, base_rows, footprints, rejection_rows=rejection_rows)
    _write_dict_csv(unit_footprints_csv, UNIT_FOOTPRINT_FIELDNAMES, footprints)
    _write_dict_csv(review_csv, FOOTPRINT_REVIEW_FIELDNAMES, review_rows)
    if suggestions_csv is not None:
        _write_dict_csv(suggestions_csv, FOOTPRINT_SUGGESTION_FIELDNAMES, suggestions)
    override_template_rows = build_footprint_override_template(review_rows, suggestions)
    if override_template_csv is not None:
        _write_dict_csv(override_template_csv, FOOTPRINT_OVERRIDE_TEMPLATE_FIELDNAMES, override_template_rows)
    review_queue_rows = build_footprint_review_queue(override_template_rows)
    if review_queue_csv is not None:
        _write_dict_csv(review_queue_csv, FOOTPRINT_REVIEW_QUEUE_FIELDNAMES, review_queue_rows)
    return {
        "units": len(unit_rows),
        "guide_rows": len(base_rows),
        "overrides": len(override_rows),
        "rejections": len(rejection_rows),
        "footprints": len(footprints),
        "review_rows": len(review_rows),
        "suggestions": len(suggestions),
        "override_template_rows": len(override_template_rows),
        "review_queue_rows": len(review_queue_rows),
    }


def build_footprint_override_template(
    review_rows: list[dict[str, str]],
    suggestions: list[dict[str, str]],
) -> list[dict[str, str]]:
    top_suggestion_by_unit: dict[str, dict[str, str]] = {}
    for suggestion in sorted(
        suggestions,
        key=lambda row: (
            _csv_int(row.get("suggestion_rank", "999")),
            -(_float_or_none(row.get("suggestion_score", "")) or 0.0),
        ),
    ):
        top_suggestion_by_unit.setdefault(suggestion.get("unit_id", ""), suggestion)
    rows: list[dict[str, str]] = []
    for review in review_rows:
        if review.get("review_category") != "unmatched_unit":
            continue
        suggestion = top_suggestion_by_unit.get(review.get("unit_id", "")) or {}
        rows.append(
            {
                "unit_id": review.get("unit_id", ""),
                "unit_name": review.get("unit_name", ""),
                "faction_contains": review.get("faction", ""),
                "selection_type": review.get("selection_type", ""),
                "models_min": review.get("models_min", ""),
                "models_max": review.get("models_max", ""),
                "review_category": review.get("review_category", ""),
                "suggestion_score": suggestion.get("suggestion_score", ""),
                "suggestion_reason": suggestion.get("suggestion_reason", ""),
                "suggested_guide_faction": suggestion.get("guide_faction", ""),
                "suggested_guide_unit_name": suggestion.get("guide_unit_name", ""),
                "suggested_guide_model_name": suggestion.get("guide_model_name", ""),
                "suggested_base_size_text": suggestion.get("base_size_text", ""),
                "suggested_source_page": suggestion.get("source_page", ""),
                "suggested_source_url": suggestion.get("source_url", ""),
                "suggested_source_updated": suggestion.get("source_updated", ""),
                "override_base_size_text": "",
                "override_base_type": "",
                "override_base_shape": "",
                "override_base_width_mm": "",
                "override_base_depth_mm": "",
                "override_guide_faction": "",
                "override_guide_unit_name": "",
                "override_guide_model_name": "",
                "review_decision": "",
                "review_notes": "",
            }
        )
    return rows


def build_footprint_review_queue(
    template_rows: list[dict[str, str]],
    *,
    include_decided: bool = False,
    faction_contains: str = "",
    priorities: set[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    faction_filter = normalize_faction(faction_contains)
    wanted_priorities = {
        normalized
        for priority in (priorities or set())
        if (normalized := normalize_footprint_review_priority(priority))
    }
    candidates = []
    for row in template_rows:
        if not include_decided and normalize_review_decision(row.get("review_decision", "")):
            continue
        if faction_filter and faction_filter not in normalize_faction(row.get("faction_contains", "")):
            continue
        if wanted_priorities and footprint_review_priority_label(row) not in wanted_priorities:
            continue
        candidates.append(row)

    sorted_rows = sorted(candidates, key=_footprint_review_queue_key)
    if limit is not None:
        sorted_rows = sorted_rows[:limit]

    queue: list[dict[str, str]] = []
    for index, row in enumerate(sorted_rows, start=1):
        score = _float_or_none(row.get("suggestion_score", ""))
        queued = {field: row.get(field, "") for field in FOOTPRINT_OVERRIDE_TEMPLATE_FIELDNAMES}
        queued.update(
            {
                "review_rank": str(index),
                "review_priority": footprint_review_priority_label(row),
                "review_hint": footprint_review_hint(row),
                **queued,
            }
        )
        if score is not None:
            queued["suggestion_score"] = f"{score:.2f}"
        queue.append(queued)
    return queue


def footprint_review_priority_label(row: dict[str, str]) -> str:
    score = _float_or_none(row.get("suggestion_score", ""))
    if score is None:
        return "no_suggestion"
    if score >= 0.75:
        return "review_suggestion_high"
    if score >= 0.65:
        return "review_suggestion_medium"
    return "review_suggestion_low"


def normalize_footprint_review_priority(value: str) -> str:
    cleaned = normalize_unit_name(value).replace(" ", "_").replace("-", "_")
    aliases = {
        "high": "review_suggestion_high",
        "suggestion_high": "review_suggestion_high",
        "review_suggestion_high": "review_suggestion_high",
        "medium": "review_suggestion_medium",
        "med": "review_suggestion_medium",
        "suggestion_medium": "review_suggestion_medium",
        "review_suggestion_medium": "review_suggestion_medium",
        "low": "review_suggestion_low",
        "suggestion_low": "review_suggestion_low",
        "review_suggestion_low": "review_suggestion_low",
        "none": "no_suggestion",
        "unknown": "no_suggestion",
        "no_suggestion": "no_suggestion",
        "no_suggestions": "no_suggestion",
    }
    return aliases.get(cleaned, cleaned)


def footprint_review_hint(row: dict[str, str]) -> str:
    score = _float_or_none(row.get("suggestion_score", ""))
    suggested_unit = str(row.get("suggested_guide_unit_name", "")).strip()
    suggested_base = str(row.get("suggested_base_size_text", "")).strip()
    if score is not None and suggested_unit and suggested_base:
        return (
            f"Check whether this imported unit is the same datasheet as '{suggested_unit}'. "
            f"If yes, set review_decision=accept_suggestion; otherwise fill override_* fields or leave blank."
        )
    return "Research the official base size, then set review_decision=override and fill override_* fields."


def _footprint_review_queue_key(row: dict[str, str]) -> tuple[int, float, int, str, str]:
    score = _float_or_none(row.get("suggestion_score", ""))
    if score is None:
        score_bucket = 3
        score_value = 0.0
    elif score >= 0.75:
        score_bucket = 0
        score_value = score
    elif score >= 0.65:
        score_bucket = 1
        score_value = score
    else:
        score_bucket = 2
        score_value = score
    model_count = max(_csv_int(row.get("models_max", "")), _csv_int(row.get("models_min", "")))
    return (
        score_bucket,
        -score_value,
        -model_count,
        row.get("faction_contains", "").casefold(),
        row.get("unit_name", "").casefold(),
    )


def match_unit_footprints(
    unit_rows: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    *,
    override_rows: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    guide_index: dict[str, list[dict[str, str]]] = {}
    for row in base_rows:
        for key in unit_name_keys(row.get("guide_unit_name", "")):
            guide_index.setdefault(key, []).append(row)

    overrides = list(override_rows or [])
    footprints: list[dict[str, str]] = []
    reviews: list[dict[str, str]] = []
    for unit in unit_rows:
        override = matching_override(unit, overrides)
        if override:
            footprint = footprint_row_from_override(unit, override)
            footprints.append(footprint)
            continue
        candidates = []
        seen_candidates: set[tuple[str, str, str, str]] = set()
        for key in unit_name_keys(unit.get("name", "")):
            for candidate in guide_index.get(key, []):
                candidate_key = (
                    candidate.get("guide_faction", ""),
                    candidate.get("guide_unit_name", ""),
                    candidate.get("guide_model_name", ""),
                    candidate.get("base_size_text", ""),
                )
                if candidate_key in seen_candidates:
                    continue
                seen_candidates.add(candidate_key)
                candidates.append(candidate)
        compatible = [row for row in candidates if faction_compatible(row.get("guide_faction", ""), unit.get("faction", ""))]
        selected = compatible or candidates
        footprint = footprint_row_for_unit(unit, selected, faction_matched=bool(compatible))
        footprints.append(footprint)
        severity, category = review_status_for_footprint(footprint, selected, faction_matched=bool(compatible))
        if severity != "ok":
            reviews.append(
                {
                    "review_severity": severity,
                    "review_category": category,
                    **footprint,
                }
            )
    return footprints, reviews


def build_footprint_suggestions(
    unit_rows: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    footprints: list[dict[str, str]],
    *,
    max_per_unit: int = 3,
    min_score: float = 0.56,
    rejection_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    footprint_by_id = {row.get("unit_id", ""): row for row in footprints}
    rejections = list(rejection_rows or [])
    suggestions: list[dict[str, str]] = []
    for unit in unit_rows:
        footprint = footprint_by_id.get(unit.get("unit_id", ""))
        if not footprint or footprint.get("footprint_status") != "unmatched":
            continue
        scored = candidate_scores_for_unit(unit, base_rows)
        selected = [item for item in scored if item[0] >= min_score][:max_per_unit]
        for rank, (score, reason, guide) in enumerate(selected, start=1):
            suggestion_probe = {
                "unit_id": unit.get("unit_id", ""),
                "unit_name": unit.get("name", ""),
                "faction": unit.get("faction", ""),
                "guide_faction": guide.get("guide_faction", ""),
                "guide_unit_name": guide.get("guide_unit_name", ""),
                "guide_model_name": guide.get("guide_model_name", ""),
                "base_size_text": guide.get("base_size_text", ""),
            }
            if matching_rejection(suggestion_probe, rejections):
                continue
            suggestions.append(
                {
                    "unit_id": unit.get("unit_id", ""),
                    "faction": unit.get("faction", ""),
                    "unit_name": unit.get("name", ""),
                    "selection_type": unit.get("selection_type", ""),
                    "models_min": unit.get("models_min", ""),
                    "models_max": unit.get("models_max", ""),
                    "suggestion_rank": str(rank),
                    "suggestion_score": f"{score:.2f}",
                    "suggestion_reason": reason,
                    "guide_faction": guide.get("guide_faction", ""),
                    "guide_unit_name": guide.get("guide_unit_name", ""),
                    "guide_model_name": guide.get("guide_model_name", ""),
                    "base_size_text": guide.get("base_size_text", ""),
                    "base_type": guide.get("base_type", ""),
                    "base_shape": guide.get("base_shape", ""),
                    "base_width_mm": guide.get("base_width_mm", ""),
                    "base_depth_mm": guide.get("base_depth_mm", ""),
                    "source_page": guide.get("page", ""),
                    "source": guide.get("source") or BASE_SIZE_GUIDE_SOURCE,
                    "source_url": guide.get("source_url") or BASE_SIZE_GUIDE_URL,
                    "source_updated": guide.get("source_updated") or BASE_SIZE_GUIDE_UPDATED,
                }
            )
    return suggestions


def candidate_scores_for_unit(unit: dict[str, str], base_rows: list[dict[str, str]]) -> list[tuple[float, str, dict[str, str]]]:
    unit_key = normalize_unit_name(unit.get("name", ""))
    if not unit_key:
        return []
    compatible_rows = [row for row in base_rows if faction_compatible(row.get("guide_faction", ""), unit.get("faction", ""))]
    candidate_rows = compatible_rows or base_rows
    scored: list[tuple[float, str, dict[str, str]]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in candidate_rows:
        candidate_key = (
            row.get("guide_faction", ""),
            row.get("guide_unit_name", ""),
            row.get("guide_model_name", ""),
        )
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        guide_key = normalize_unit_name(row.get("guide_unit_name", ""))
        if not guide_key:
            continue
        ratio = SequenceMatcher(None, unit_key, guide_key).ratio()
        overlap = token_overlap(unit_key, guide_key)
        score = ratio * 0.75 + overlap * 0.25
        if faction_compatible(row.get("guide_faction", ""), unit.get("faction", "")):
            score += 0.08
        score = min(score, 1.0)
        reason = f"name similarity {ratio:.2f}; token overlap {overlap:.2f}"
        if faction_compatible(row.get("guide_faction", ""), unit.get("faction", "")):
            reason += "; faction compatible"
        scored.append((score, reason, row))
    return sorted(scored, key=lambda item: (-item[0], item[2].get("guide_faction", ""), item[2].get("guide_unit_name", "")))


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def load_footprint_overrides_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_footprint_suggestions_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_footprint_rejections_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_footprint_override_template_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_footprint_overrides_csv(rows: list[dict[str, str]], path: Path) -> None:
    _write_dict_csv(path, FOOTPRINT_OVERRIDE_FIELDNAMES, rows)


def write_footprint_rejections_csv(rows: list[dict[str, str]], path: Path) -> None:
    _write_dict_csv(path, FOOTPRINT_REJECTION_FIELDNAMES, rows)


def write_footprint_review_queue_csv(rows: list[dict[str, str]], path: Path) -> None:
    _write_dict_csv(path, FOOTPRINT_REVIEW_QUEUE_FIELDNAMES, rows)


def accepted_override_rows_from_suggestions(
    suggestions: list[dict[str, str]],
    existing_overrides: list[dict[str, str]],
    *,
    unit_ids: set[str] | None = None,
    min_score: float = 0.9,
    rank: int = 1,
    limit: int | None = None,
) -> list[dict[str, str]]:
    existing_ids = {str(row.get("unit_id", "")).strip() for row in existing_overrides if row.get("unit_id")}
    selected: list[dict[str, str]] = []
    for suggestion in suggestions:
        unit_id = str(suggestion.get("unit_id", "")).strip()
        if not unit_id or unit_id in existing_ids:
            continue
        if unit_ids is not None and unit_id not in unit_ids:
            continue
        try:
            suggestion_rank = int(str(suggestion.get("suggestion_rank", "")).strip() or "0")
            suggestion_score = float(str(suggestion.get("suggestion_score", "")).strip() or "0")
        except ValueError:
            continue
        if suggestion_rank != rank or suggestion_score < min_score:
            continue
        selected.append(override_row_from_suggestion(suggestion))
        existing_ids.add(unit_id)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def override_row_from_suggestion(suggestion: dict[str, str]) -> dict[str, str]:
    source_page = str(suggestion.get("source_page", "")).strip()
    reason_parts = [
        (
            "Accepted footprint suggestion "
            f"rank {suggestion.get('suggestion_rank', '')}, score {suggestion.get('suggestion_score', '')}"
        ).strip(),
        suggestion.get("suggestion_reason", ""),
    ]
    if source_page:
        reason_parts.append(f"guide page {source_page}")
    return {
        "unit_id": suggestion.get("unit_id", ""),
        "unit_name": suggestion.get("unit_name", ""),
        "faction_contains": suggestion.get("faction", ""),
        "base_size_text": suggestion.get("base_size_text", ""),
        "base_type": suggestion.get("base_type", ""),
        "base_shape": suggestion.get("base_shape", ""),
        "base_width_mm": suggestion.get("base_width_mm", ""),
        "base_depth_mm": suggestion.get("base_depth_mm", ""),
        "guide_faction": suggestion.get("guide_faction", ""),
        "guide_unit_name": suggestion.get("guide_unit_name", ""),
        "guide_model_name": suggestion.get("guide_model_name", ""),
        "source": suggestion.get("source") or BASE_SIZE_GUIDE_SOURCE,
        "source_url": suggestion.get("source_url") or BASE_SIZE_GUIDE_URL,
        "source_updated": suggestion.get("source_updated") or BASE_SIZE_GUIDE_UPDATED,
        "review_reason": ": ".join(
            [reason_parts[0], "; ".join(str(part).strip() for part in reason_parts[1:] if str(part).strip())]
        ).strip(": "),
    }


def accepted_override_rows_from_template(
    template_rows: list[dict[str, str]],
    existing_overrides: list[dict[str, str]],
    *,
    unit_ids: set[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    existing_ids = {str(row.get("unit_id", "")).strip() for row in existing_overrides if row.get("unit_id")}
    selected: list[dict[str, str]] = []
    for row in template_rows:
        unit_id = str(row.get("unit_id", "")).strip()
        if not unit_id or unit_id in existing_ids:
            continue
        if unit_ids is not None and unit_id not in unit_ids:
            continue
        decision = normalize_review_decision(row.get("review_decision", ""))
        if decision not in {"accept_suggestion", "override"}:
            continue
        override = override_row_from_template(row, decision=decision)
        if not override:
            continue
        selected.append(override)
        existing_ids.add(unit_id)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def summarize_footprint_override_template(
    template_rows: list[dict[str, str]],
    existing_overrides: list[dict[str, str]] | None = None,
    *,
    unit_ids: set[str] | None = None,
) -> dict[str, object]:
    existing_ids = {
        str(row.get("unit_id", "")).strip()
        for row in (existing_overrides or [])
        if row.get("unit_id")
    }
    counts = {
        "total": 0,
        "blank": 0,
        "accept_suggestion_ready": 0,
        "override_ready": 0,
        "rejected": 0,
        "already_overridden": 0,
        "outside_filter": 0,
        "invalid": 0,
    }
    issues: list[dict[str, str]] = []
    for row in template_rows:
        counts["total"] += 1
        unit_id = str(row.get("unit_id", "")).strip()
        if unit_ids is not None and unit_id not in unit_ids:
            counts["outside_filter"] += 1
            continue
        status, reason = validate_footprint_override_template_row(row, existing_ids=existing_ids)
        counts[status] = counts.get(status, 0) + 1
        if status == "invalid":
            issues.append(
                {
                    "unit_id": unit_id,
                    "unit_name": row.get("unit_name", ""),
                    "review_decision": row.get("review_decision", ""),
                    "reason": reason,
                }
            )
    return {"counts": counts, "issues": issues}


def validate_footprint_override_template_row(
    row: dict[str, str],
    *,
    existing_ids: set[str] | None = None,
) -> tuple[str, str]:
    unit_id = str(row.get("unit_id", "")).strip()
    if existing_ids and unit_id in existing_ids:
        return "already_overridden", "Unit id already exists in manual overrides."
    raw_decision = str(row.get("review_decision", "")).strip()
    decision = normalize_review_decision(raw_decision)
    if not decision:
        return "blank", "No review decision set."
    if decision == "reject":
        return "rejected", "Template row marked rejected or skipped."
    if decision == "accept_suggestion":
        missing = [
            field
            for field in ("suggested_guide_unit_name", "suggested_base_size_text")
            if not str(row.get(field, "")).strip()
        ]
        if missing:
            return "invalid", f"accept_suggestion is missing {', '.join(missing)}."
        return "accept_suggestion_ready", "Suggestion row is ready to promote."
    if decision == "override":
        base_size_text = str(row.get("override_base_size_text", "")).strip()
        base_type = str(row.get("override_base_type", "")).strip()
        base_shape = str(row.get("override_base_shape", "")).strip()
        if not base_size_text and not (base_type and base_shape):
            return "invalid", "override requires override_base_size_text or override_base_type plus override_base_shape."
        parsed = parse_base_size_text(base_size_text) if base_size_text else {}
        if base_size_text and parsed.get("base_type") == "unknown" and not (base_type and base_shape):
            return "invalid", f"override_base_size_text is not a recognized base-size format: {base_size_text}."
        return "override_ready", "Manual override row is ready to promote."
    return "invalid", f"Unknown review_decision: {raw_decision}."


def override_row_from_template(row: dict[str, str], *, decision: str | None = None) -> dict[str, str] | None:
    resolved_decision = normalize_review_decision(decision or row.get("review_decision", ""))
    if resolved_decision == "accept_suggestion":
        base_size_text = str(row.get("suggested_base_size_text", "")).strip()
        guide_faction = str(row.get("suggested_guide_faction", "")).strip()
        guide_unit_name = str(row.get("suggested_guide_unit_name", "")).strip()
        guide_model_name = str(row.get("suggested_guide_model_name", "")).strip()
        source_url = str(row.get("suggested_source_url", "")).strip() or BASE_SIZE_GUIDE_URL
        source_updated = str(row.get("suggested_source_updated", "")).strip() or BASE_SIZE_GUIDE_UPDATED
        source_page = str(row.get("suggested_source_page", "")).strip()
        reason_prefix = "Accepted footprint override-template suggestion"
    elif resolved_decision == "override":
        base_size_text = str(row.get("override_base_size_text", "")).strip()
        guide_faction = str(row.get("override_guide_faction", "")).strip()
        guide_unit_name = str(row.get("override_guide_unit_name", "")).strip()
        guide_model_name = str(row.get("override_guide_model_name", "")).strip()
        source_url = BASE_SIZE_GUIDE_URL
        source_updated = BASE_SIZE_GUIDE_UPDATED
        source_page = ""
        reason_prefix = "Accepted manual footprint override-template row"
    else:
        return None

    parsed = parse_base_size_text(base_size_text) if base_size_text else {}
    base_type = str(row.get("override_base_type", "")).strip() or parsed.get("base_type", "")
    base_shape = str(row.get("override_base_shape", "")).strip() or parsed.get("base_shape", "")
    base_width = str(row.get("override_base_width_mm", "")).strip() or parsed.get("base_width_mm", "")
    base_depth = str(row.get("override_base_depth_mm", "")).strip() or parsed.get("base_depth_mm", "")
    if not base_size_text and not (base_type and base_shape):
        return None

    notes = str(row.get("review_notes", "")).strip()
    suggestion_score = str(row.get("suggestion_score", "")).strip()
    suggestion_reason = str(row.get("suggestion_reason", "")).strip()
    reason_parts = [reason_prefix]
    if suggestion_score:
        reason_parts.append(f"template score {suggestion_score}")
    if suggestion_reason:
        reason_parts.append(suggestion_reason)
    if source_page:
        reason_parts.append(f"guide page {source_page}")
    if notes:
        reason_parts.append(notes)

    return {
        "unit_id": row.get("unit_id", ""),
        "unit_name": row.get("unit_name", ""),
        "faction_contains": row.get("faction_contains", ""),
        "base_size_text": base_size_text,
        "base_type": base_type,
        "base_shape": base_shape,
        "base_width_mm": base_width,
        "base_depth_mm": base_depth,
        "guide_faction": guide_faction,
        "guide_unit_name": guide_unit_name or row.get("unit_name", ""),
        "guide_model_name": guide_model_name,
        "source": BASE_SIZE_GUIDE_SOURCE,
        "source_url": source_url,
        "source_updated": source_updated,
        "review_reason": ": ".join([reason_parts[0], "; ".join(reason_parts[1:])]) if len(reason_parts) > 1 else reason_parts[0],
    }


def normalize_review_decision(value: str) -> str:
    cleaned = normalize_unit_name(value).replace(" ", "_").replace("-", "_")
    if cleaned in {"accept_suggestion", "accept_suggested", "suggestion", "suggested", "use_suggestion"}:
        return "accept_suggestion"
    if cleaned in {"override", "manual", "manual_override", "accept_override", "accepted", "accept", "approve", "approved"}:
        return "override"
    if cleaned in {"reject", "rejected", "skip", "ignored", "ignore", "no", "n"}:
        return "reject"
    return cleaned


def rejected_rows_from_suggestions(
    suggestions: list[dict[str, str]],
    existing_rejections: list[dict[str, str]],
    *,
    unit_ids: set[str] | None = None,
    min_score: float = 0.8,
    rank: int = 1,
    reason: str = "Reviewed and not accepted as a safe official base-size match.",
    limit: int | None = None,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for suggestion in suggestions:
        unit_id = str(suggestion.get("unit_id", "")).strip()
        if not unit_id:
            continue
        if unit_ids is not None and unit_id not in unit_ids:
            continue
        if matching_rejection(suggestion, existing_rejections):
            continue
        try:
            suggestion_rank = int(str(suggestion.get("suggestion_rank", "")).strip() or "0")
            suggestion_score = float(str(suggestion.get("suggestion_score", "")).strip() or "0")
        except ValueError:
            continue
        if suggestion_rank != rank or suggestion_score < min_score:
            continue
        selected.append(rejection_row_from_suggestion(suggestion, reason=reason))
        if limit is not None and len(selected) >= limit:
            break
    return selected


def rejected_rows_from_template(
    template_rows: list[dict[str, str]],
    existing_rejections: list[dict[str, str]],
    *,
    unit_ids: set[str] | None = None,
    reason: str = "Reviewed and not accepted as a safe official base-size match.",
    limit: int | None = None,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in template_rows:
        unit_id = str(row.get("unit_id", "")).strip()
        if not unit_id:
            continue
        if unit_ids is not None and unit_id not in unit_ids:
            continue
        if normalize_review_decision(row.get("review_decision", "")) != "reject":
            continue
        rejection = rejection_row_from_template(row, reason=reason)
        if not rejection:
            continue
        if matching_rejection(_template_row_as_suggestion(row), existing_rejections):
            continue
        selected.append(rejection)
        existing_rejections.append(rejection)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def rejection_row_from_suggestion(suggestion: dict[str, str], *, reason: str) -> dict[str, str]:
    source_page = str(suggestion.get("source_page", "")).strip()
    reason_parts = [reason]
    if source_page:
        reason_parts.append(f"guide page {source_page}")
    return {
        "unit_id": suggestion.get("unit_id", ""),
        "unit_name": suggestion.get("unit_name", ""),
        "faction_contains": suggestion.get("faction", ""),
        "guide_faction": suggestion.get("guide_faction", ""),
        "guide_unit_name": suggestion.get("guide_unit_name", ""),
        "guide_model_name": suggestion.get("guide_model_name", ""),
        "base_size_text": suggestion.get("base_size_text", ""),
        "decision": "rejected",
        "review_reason": "; ".join(part for part in reason_parts if str(part).strip()),
    }


def rejection_row_from_template(row: dict[str, str], *, reason: str) -> dict[str, str] | None:
    guide_unit_name = str(row.get("suggested_guide_unit_name", "")).strip()
    base_size_text = str(row.get("suggested_base_size_text", "")).strip()
    if not guide_unit_name and not base_size_text:
        return None
    source_page = str(row.get("suggested_source_page", "")).strip()
    notes = str(row.get("review_notes", "")).strip()
    reason_parts = [reason]
    if source_page:
        reason_parts.append(f"guide page {source_page}")
    if notes:
        reason_parts.append(notes)
    return {
        "unit_id": row.get("unit_id", ""),
        "unit_name": row.get("unit_name", ""),
        "faction_contains": row.get("faction_contains", ""),
        "guide_faction": row.get("suggested_guide_faction", ""),
        "guide_unit_name": guide_unit_name,
        "guide_model_name": row.get("suggested_guide_model_name", ""),
        "base_size_text": base_size_text,
        "decision": "rejected",
        "review_reason": "; ".join(part for part in reason_parts if str(part).strip()),
    }


def _template_row_as_suggestion(row: dict[str, str]) -> dict[str, str]:
    return {
        "unit_id": row.get("unit_id", ""),
        "unit_name": row.get("unit_name", ""),
        "faction": row.get("faction_contains", ""),
        "guide_faction": row.get("suggested_guide_faction", ""),
        "guide_unit_name": row.get("suggested_guide_unit_name", ""),
        "guide_model_name": row.get("suggested_guide_model_name", ""),
        "base_size_text": row.get("suggested_base_size_text", ""),
    }


def matching_rejection(suggestion: dict[str, str], rejections: list[dict[str, str]]) -> dict[str, str] | None:
    unit_id = str(suggestion.get("unit_id", "")).strip()
    unit_name_keys_for_unit = unit_name_keys(suggestion.get("unit_name", ""))
    imported_faction = normalize_faction(suggestion.get("faction", ""))
    for rejection in rejections:
        rejected_id = str(rejection.get("unit_id", "")).strip()
        if rejected_id and rejected_id != unit_id:
            continue
        rejected_name = str(rejection.get("unit_name", "")).strip()
        if rejected_name and not (unit_name_keys(rejected_name) & unit_name_keys_for_unit):
            continue
        faction_contains = normalize_faction(rejection.get("faction_contains", ""))
        if faction_contains and faction_contains not in imported_faction:
            continue
        if not _optional_rejection_field_matches(rejection, suggestion, "guide_faction"):
            continue
        if not _optional_rejection_field_matches(rejection, suggestion, "guide_unit_name"):
            continue
        if not _optional_rejection_field_matches(rejection, suggestion, "guide_model_name"):
            continue
        if not _optional_rejection_field_matches(rejection, suggestion, "base_size_text"):
            continue
        if rejected_id or rejected_name:
            return rejection
    return None


def _optional_rejection_field_matches(rejection: dict[str, str], suggestion: dict[str, str], field: str) -> bool:
    rejected_value = str(rejection.get(field, "")).strip()
    if not rejected_value:
        return True
    return normalize_unit_name(rejected_value) == normalize_unit_name(suggestion.get(field, ""))


def matching_override(unit: dict[str, str], overrides: list[dict[str, str]]) -> dict[str, str] | None:
    unit_id = str(unit.get("unit_id", "")).strip()
    unit_name_keys_for_unit = unit_name_keys(unit.get("name", ""))
    imported_faction = normalize_faction(unit.get("faction", ""))
    for override in overrides:
        override_id = str(override.get("unit_id", "")).strip()
        if override_id and override_id != unit_id:
            continue
        override_name = str(override.get("unit_name", "")).strip()
        if override_name and not (unit_name_keys(override_name) & unit_name_keys_for_unit):
            continue
        faction_contains = normalize_faction(override.get("faction_contains", ""))
        if faction_contains and faction_contains not in imported_faction:
            continue
        if override_id or override_name:
            return override
    return None


def footprint_row_from_override(unit: dict[str, str], override: dict[str, str]) -> dict[str, str]:
    parsed = parse_base_size_text(override.get("base_size_text", "")) if override.get("base_size_text") else {}
    base_type = override.get("base_type") or parsed.get("base_type", "")
    base_shape = override.get("base_shape") or parsed.get("base_shape", "")
    base_width = override.get("base_width_mm") or parsed.get("base_width_mm", "")
    base_depth = override.get("base_depth_mm") or parsed.get("base_depth_mm", "")
    return {
        "unit_id": unit.get("unit_id", ""),
        "faction": unit.get("faction", ""),
        "unit_name": unit.get("name", ""),
        "selection_type": unit.get("selection_type", ""),
        "models_min": unit.get("models_min", ""),
        "models_max": unit.get("models_max", ""),
        "footprint_status": "override",
        "base_type": base_type,
        "base_shape": base_shape,
        "base_width_mm": base_width,
        "base_depth_mm": base_depth,
        "guide_faction": override.get("guide_faction", ""),
        "guide_unit_name": override.get("guide_unit_name") or override.get("unit_name", ""),
        "guide_model_name": override.get("guide_model_name", ""),
        "source": override.get("source") or BASE_SIZE_GUIDE_SOURCE,
        "source_url": override.get("source_url") or BASE_SIZE_GUIDE_URL,
        "source_updated": override.get("source_updated") or BASE_SIZE_GUIDE_UPDATED,
        "match_method": "manual_override",
        "match_confidence": "1.00",
        "review_reason": override.get("review_reason", ""),
    }


def footprint_row_for_unit(
    unit: dict[str, str],
    matches: list[dict[str, str]],
    *,
    faction_matched: bool,
) -> dict[str, str]:
    base = {
        "unit_id": unit.get("unit_id", ""),
        "faction": unit.get("faction", ""),
        "unit_name": unit.get("name", ""),
        "selection_type": unit.get("selection_type", ""),
        "models_min": unit.get("models_min", ""),
        "models_max": unit.get("models_max", ""),
        "footprint_status": "",
        "base_type": "",
        "base_shape": "",
        "base_width_mm": "",
        "base_depth_mm": "",
        "guide_faction": "",
        "guide_unit_name": "",
        "guide_model_name": "",
        "source": BASE_SIZE_GUIDE_SOURCE,
        "source_url": BASE_SIZE_GUIDE_URL,
        "source_updated": BASE_SIZE_GUIDE_UPDATED,
        "match_method": "",
        "match_confidence": "",
        "review_reason": "",
    }
    if not matches:
        return {
            **base,
            "footprint_status": "unmatched",
            "match_method": "none",
            "match_confidence": "0.00",
            "review_reason": "No official base-size guide row matched this imported unit name.",
        }

    merged = merge_base_rows(matches)
    reasons: list[str] = []
    if len(matches) > 1:
        reasons.append("Multiple official base rows matched; largest numeric base was selected for blob sizing.")
    if not faction_matched:
        reasons.append("Matched by unit name only; faction did not match the official guide heading.")
    status = "matched" if len(matches) == 1 and faction_matched else "review"
    confidence = "1.00" if status == "matched" else ("0.70" if faction_matched else "0.45")
    return {
        **base,
        "footprint_status": status,
        "base_type": merged["base_type"],
        "base_shape": merged["base_shape"],
        "base_width_mm": merged["base_width_mm"],
        "base_depth_mm": merged["base_depth_mm"],
        "guide_faction": "; ".join(sorted({row.get("guide_faction", "") for row in matches if row.get("guide_faction")})),
        "guide_unit_name": "; ".join(sorted({row.get("guide_unit_name", "") for row in matches if row.get("guide_unit_name")})),
        "guide_model_name": "; ".join(sorted({row.get("guide_model_name", "") for row in matches if row.get("guide_model_name")})),
        "match_method": "exact_name_faction" if faction_matched else "exact_name",
        "match_confidence": confidence,
        "review_reason": "; ".join(reasons),
    }


def merge_base_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    numeric = [row for row in rows if _float_or_none(row.get("base_width_mm", "")) is not None]
    if numeric:
        selected = max(
            numeric,
            key=lambda row: (
                _float_or_none(row.get("base_width_mm", "")) or 0.0,
                _float_or_none(row.get("base_depth_mm", "")) or 0.0,
            ),
        )
    else:
        selected = rows[0]
    return {
        "base_type": selected.get("base_type", ""),
        "base_shape": selected.get("base_shape", ""),
        "base_width_mm": selected.get("base_width_mm", ""),
        "base_depth_mm": selected.get("base_depth_mm", ""),
    }


def review_status_for_footprint(
    footprint: dict[str, str],
    matches: list[dict[str, str]],
    *,
    faction_matched: bool,
) -> tuple[str, str]:
    if not matches:
        return "warning", "unmatched_unit"
    if len(matches) > 1:
        return "info", "mixed_or_multi_base_unit"
    if not faction_matched:
        return "warning", "faction_mismatch"
    if footprint.get("base_type") in {"hull", "unique", "small_flying_base", "large_flying_base"}:
        return "info", "non_numeric_base"
    return "ok", "matched"


def normalize_unit_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = text.replace("\u2018", "").replace("\u2019", "").replace("'", "").replace("`", "")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    text = re.sub(r"\b(the|with|and|squad|unit)\b", " ", text)
    text = text.replace("armour", "armor")
    return " ".join(text.split())


def unit_name_keys(value: str) -> set[str]:
    key = normalize_unit_name(value)
    if not key:
        return set()
    keys = {key, singularize_name_key(key)}
    tokens = key.split()
    if tokens and tokens[-1].endswith("s") and len(tokens[-1]) > 3:
        keys.add(" ".join([*tokens[:-1], tokens[-1][:-1]]))
    return {item for item in keys if item}


def singularize_name_key(value: str) -> str:
    tokens = []
    for token in str(value or "").split():
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            tokens.append(token[:-1])
        else:
            tokens.append(token)
    return " ".join(tokens)


def normalize_faction(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.replace("\u2018", "").replace("\u2019", "").replace("'", "").replace("`", "")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    text = text.replace("armour", "armor")
    return " ".join(text.split())


def faction_compatible(guide_faction: str, imported_faction: str) -> bool:
    guide = normalize_faction(guide_faction)
    imported = normalize_faction(imported_faction)
    if not guide or not imported:
        return False
    if "aeldari library" in imported and guide in {"aeldari", "drukhari"}:
        return True
    if "chaos space marines" in imported and guide in {
        "chaos space marines",
        "death guard",
        "emperor s children",
        "emperors children",
        "thousand sons",
        "world eaters",
    }:
        return True
    if "agents of the imperium" in imported and guide == "deathwatch":
        return True
    if imported == "library titans" and guide == "adeptus titanicus":
        return True
    if guide == "space marines":
        return "adeptus astartes" in imported or ("space marines" in imported and "chaos" not in imported)
    aliases = {
        "astra militarum": ("astra militarum",),
        "adepta sororitas": ("adepta sororitas",),
        "adeptus custodes": ("adeptus custodes",),
        "adeptus mechanicus": ("adeptus mechanicus",),
        "imperial agents": ("agents of the imperium", "imperial agents"),
        "imperial knights": ("imperial knights",),
        "chaos daemons": ("daemons",),
        "daemons": ("daemons",),
        "chaos knights": ("chaos knights",),
        "chaos space marines": ("chaos space marines",),
        "death guard": ("death guard",),
        "emperor s children": ("emperors children", "emperor s children"),
        "thousand sons": ("thousand sons",),
        "world eaters": ("world eaters",),
        "aeldari": ("aeldari",),
        "drukhari": ("drukhari",),
        "genestealer cults": ("genestealer cults",),
        "leagues of votann": ("leagues of votann",),
        "necrons": ("necrons",),
        "orks": ("orks",),
        "t au empire": ("tau empire", "t au empire"),
        "tyranids": ("tyranids",),
        "grey knights": ("grey knights",),
        "deathwatch": ("deathwatch",),
    }
    for alias in aliases.get(guide, (guide,)):
        if alias and alias in imported:
            return True
    return guide in imported or imported in guide


def _is_skipped_line(line: str) -> bool:
    upper = line.upper()
    return (
        upper in _SKIP_LINES
        or upper.startswith("LAST UPDATED")
        or upper.startswith("WELCOME TO")
        or upper.startswith("IF YOU HAVE")
        or upper.startswith("\u00a9")
        or bool(re.fullmatch(r"\d+", line))
    )


def _looks_like_faction_heading(line: str) -> bool:
    upper = line.upper()
    return upper == line and len(line) > 2 and not _ROW_PATTERN.match(line)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_dict_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
