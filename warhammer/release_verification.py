from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


CommandRunner = Callable[[Sequence[str], Path], int]
MessageSink = Callable[[str], None]


@dataclass(frozen=True)
class ReleaseCheck:
    name: str
    command: list[str]


def build_release_checks(
    *,
    python_executable: str,
    data_dirs: Sequence[Path],
    review_data_dir: Path,
    thresholds: Path | None,
    skip_tests: bool = False,
    skip_review_gate: bool = False,
) -> list[ReleaseCheck]:
    checks: list[ReleaseCheck] = []
    if not skip_tests:
        checks.append(ReleaseCheck("pytest", [python_executable, "-m", "pytest", "-q"]))
    for data_dir in data_dirs:
        checks.append(
            ReleaseCheck(
                f"artifact manifest: {data_dir}",
                [python_executable, "verify_artifacts.py", "--data-dir", str(data_dir)],
            )
        )
    if not skip_review_gate:
        command = [
            python_executable,
            "data_review_summary.py",
            "--data-dir",
            str(review_data_dir),
            "--fail-on-issues",
        ]
        if thresholds:
            command.extend(["--thresholds", str(thresholds)])
        checks.append(ReleaseCheck("data review gate", command))
    return checks


def run_release_checks(
    checks: Sequence[ReleaseCheck],
    *,
    project_root: Path,
    command_runner: CommandRunner | None = None,
    message_sink: MessageSink | None = None,
) -> int:
    runner = command_runner or _run_subprocess
    sink = message_sink or _print_message
    for check in checks:
        sink(f"==> {check.name}")
        result = runner(check.command, project_root)
        if result != 0:
            sink(f"Release verification failed: {check.name}")
            return result
    sink("Release verification passed.")
    return 0


def _print_message(message: str) -> None:
    print(message, flush=True)


def _run_subprocess(command: Sequence[str], cwd: Path) -> int:
    return subprocess.run(list(command), cwd=cwd, check=False).returncode
