from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
import random
from typing import Any, Iterable, Sequence

from .model import DEFAULT_LABEL_KEY_COLUMNS


VALID_MATCHUP_LABELS = {"attacker", "defender", "close"}

LABEL_REVIEW_COLUMNS = [
    "edition",
    "mode",
    "attacker_id",
    "defender_id",
    "winner_label",
    "review_notes",
    "deterministic_winner_label",
    "deterministic_confidence",
    "deterministic_edge",
    "attacker_name",
    "attacker_faction",
    "attacker_points",
    "attacker_models",
    "attacker_mode_weapon_count",
    "defender_name",
    "defender_faction",
    "defender_points",
    "defender_models",
    "defender_mode_weapon_count",
    "points_removed_delta",
    "damage_delta",
    "outgoing_points_removed",
    "incoming_points_removed",
    "outgoing_damage",
    "incoming_damage",
]


def build_label_review_rows(
    feature_rows: Iterable[dict[str, Any]],
    *,
    limit: int | None = 200,
    strategy: str = "uncertain",
    seed: int = 40,
) -> list[dict[str, Any]]:
    """Build a human-labelling queue from generated matchup feature rows."""

    rows = [dict(row) for row in feature_rows]
    if strategy == "uncertain":
        rows.sort(key=_uncertainty_key)
    elif strategy == "random":
        rng = random.Random(seed)
        rng.shuffle(rows)
    elif strategy == "sequential":
        pass
    else:
        raise ValueError("strategy must be one of: uncertain, random, sequential")

    if limit is not None and limit >= 0:
        rows = rows[:limit]

    return [_label_review_row(row) for row in rows]


def write_label_review_csv(rows: Iterable[dict[str, Any]], path: Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def validate_label_review_rows(
    label_rows: Iterable[dict[str, Any]],
    *,
    key_columns: Sequence[str] = DEFAULT_LABEL_KEY_COLUMNS,
    valid_labels: set[str] = VALID_MATCHUP_LABELS,
) -> dict[str, Any]:
    rows = [dict(row) for row in label_rows]
    duplicate_keys = 0
    missing_key_rows = 0
    invalid_label_rows = 0
    labelled_rows = 0
    seen_keys: set[tuple[str, ...]] = set()
    label_counts: Counter[str] = Counter()

    for row in rows:
        key = tuple(str(row.get(column) or "").strip() for column in key_columns)
        if not all(key):
            missing_key_rows += 1
        elif key in seen_keys:
            duplicate_keys += 1
        else:
            seen_keys.add(key)

        label = str(row.get("winner_label") or row.get("label") or "").strip().lower()
        if not label:
            continue
        labelled_rows += 1
        label_counts[label] += 1
        if label not in valid_labels:
            invalid_label_rows += 1

    return {
        "rows": len(rows),
        "labelled_rows": labelled_rows,
        "unlabelled_rows": len(rows) - labelled_rows,
        "missing_key_rows": missing_key_rows,
        "duplicate_keys": duplicate_keys,
        "invalid_label_rows": invalid_label_rows,
        "valid": missing_key_rows == 0 and duplicate_keys == 0 and invalid_label_rows == 0,
        "label_counts": dict(sorted(label_counts.items())),
        "key_columns": list(key_columns),
        "valid_labels": sorted(valid_labels),
    }


def _label_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "edition": row.get("edition", ""),
        "mode": row.get("mode", ""),
        "attacker_id": row.get("attacker_id", ""),
        "defender_id": row.get("defender_id", ""),
        "winner_label": "",
        "review_notes": "",
        "deterministic_winner_label": row.get("winner_label", ""),
        "deterministic_confidence": row.get("confidence", ""),
        "deterministic_edge": row.get("edge", ""),
        "attacker_name": row.get("attacker_name", ""),
        "attacker_faction": row.get("attacker_faction", ""),
        "attacker_points": row.get("attacker_points", ""),
        "attacker_models": row.get("attacker_models", ""),
        "attacker_mode_weapon_count": row.get("attacker_mode_weapon_count", ""),
        "defender_name": row.get("defender_name", ""),
        "defender_faction": row.get("defender_faction", ""),
        "defender_points": row.get("defender_points", ""),
        "defender_models": row.get("defender_models", ""),
        "defender_mode_weapon_count": row.get("defender_mode_weapon_count", ""),
        "points_removed_delta": row.get("points_removed_delta", ""),
        "damage_delta": row.get("damage_delta", ""),
        "outgoing_points_removed": row.get("outgoing_points_removed", ""),
        "incoming_points_removed": row.get("incoming_points_removed", ""),
        "outgoing_damage": row.get("outgoing_damage", ""),
        "incoming_damage": row.get("incoming_damage", ""),
    }


def _uncertainty_key(row: dict[str, Any]) -> tuple[float, float, int, str, str, str]:
    label = str(row.get("winner_label") or "")
    confidence = _number(row.get("confidence"))
    edge = abs(_number(row.get("edge")))
    close_first = 0 if label == "close" else 1
    return (
        close_first,
        confidence,
        edge,
        str(row.get("mode") or ""),
        str(row.get("attacker_name") or ""),
        str(row.get("defender_name") or ""),
    )


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
