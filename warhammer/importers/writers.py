"""Utility helpers for writing CSV outputs from dataclass rows."""

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable


def write_csv(path: Path, rows: Iterable[object], headers: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
