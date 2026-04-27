from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Sequence


TABLES: dict[str, tuple[str, str | tuple[str, ...]]] = {
    "units": ("units.csv", "unit_id"),
    "weapons": ("weapons.csv", "weapon_id"),
    "abilities": ("abilities.csv", "ability_id"),
    "keywords": ("keywords.csv", "keyword_id"),
    "unit_keywords": ("unit_keywords.csv", ("unit_id", "keyword_id")),
}


def load_tables(
    csv_dir: Path,
    *,
    tables: dict[str, tuple[str, str | tuple[str, ...]]] = TABLES,
) -> dict[str, dict[str, dict[str, str]]]:
    loaded: dict[str, dict[str, dict[str, str]]] = {}
    for table, (filename, key_fields) in tables.items():
        rows = read_csv_rows(Path(csv_dir) / filename)
        keyed_rows: dict[str, dict[str, str]] = {}
        key_counts: dict[str, int] = {}
        for index, row in enumerate(rows, start=1):
            base_key = row_key(row, key_fields) or f"<row-{index}>"
            key_counts[base_key] = key_counts.get(base_key, 0) + 1
            key = base_key if key_counts[base_key] == 1 else f"{base_key}#{key_counts[base_key]}"
            keyed_rows[key] = row
        loaded[table] = keyed_rows
    return loaded


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_key(row: Dict[str, str], key_fields: str | tuple[str, ...]) -> str:
    if isinstance(key_fields, str):
        return (row.get(key_fields) or "").strip()
    return ":".join((row.get(field) or "").strip() for field in key_fields)


def build_import_diff(
    before: dict[str, dict[str, dict[str, str]]],
    after: dict[str, dict[str, dict[str, str]]],
    *,
    source_before: dict[str, object],
    source_after: dict[str, object],
    table_names: Sequence[str] = tuple(TABLES),
) -> dict[str, object]:
    tables = {}
    for table in table_names:
        before_rows = before.get(table, {})
        after_rows = after.get(table, {})
        before_ids = set(before_rows)
        after_ids = set(after_rows)
        added = sorted(after_ids - before_ids)
        removed = sorted(before_ids - after_ids)
        changed = sorted(row_id for row_id in before_ids & after_ids if before_rows[row_id] != after_rows[row_id])
        tables[table] = {
            "before_count": len(before_rows),
            "after_count": len(after_rows),
            "delta": len(after_rows) - len(before_rows),
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "added_samples": added[:20],
            "removed_samples": removed[:20],
            "changed_samples": changed[:20],
        }

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_before": source_before,
        "source_after": source_after,
        "tables": tables,
    }


def csv_data_row_count(path: Path) -> int:
    if not Path(path).exists():
        return 0
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)
