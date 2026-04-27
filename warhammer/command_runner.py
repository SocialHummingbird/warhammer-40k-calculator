from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path


def run_command(command: Sequence[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        joined = " ".join(str(part) for part in command)
        raise SystemExit(f"Command failed with exit {completed.returncode}: {joined}")
