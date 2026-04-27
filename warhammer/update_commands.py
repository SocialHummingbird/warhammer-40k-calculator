from __future__ import annotations

import sys
from pathlib import Path


def bsdata_import_command(
    *,
    repo_dir: Path,
    csv_dir: Path,
    edition: str,
    python_executable: str = sys.executable,
) -> list[str]:
    return [
        python_executable,
        "import_bsdata.py",
        str(repo_dir),
        "--output",
        str(csv_dir),
        "--edition",
        edition,
    ]


def local_html_export_command(
    *,
    csv_dir: Path,
    ml_artifacts: dict[str, object] | None = None,
    python_executable: str = sys.executable,
) -> list[str]:
    command = [python_executable, "export_local_html.py", "--csv-dir", str(csv_dir)]
    model_path = _ml_model_path(ml_artifacts)
    if model_path:
        command.extend(["--model", model_path])
    return command


def _ml_model_path(ml_artifacts: dict[str, object] | None) -> str:
    if not ml_artifacts:
        return ""
    model_path = ml_artifacts.get("model_path")
    return str(model_path) if model_path else ""
