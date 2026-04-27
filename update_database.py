#!/usr/bin/env python3
"""Refresh BSData sources and regenerate calculator data artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from warhammer.update_pipeline import run_update


PROJECT_ROOT = Path(__file__).resolve().parent


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run_update(argv, project_root=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
