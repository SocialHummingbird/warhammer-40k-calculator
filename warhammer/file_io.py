from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, object]:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json_file(path: Path, payload: object, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=indent), encoding="utf-8")


def write_text_file(path: Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
