from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path


CommandRunner = Callable[[Sequence[str]], None]


def git_output(repo_dir: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def source_metadata(repo_dir: Path) -> dict[str, object]:
    return {
        "path": str(repo_dir),
        "remote_origin": git_output(repo_dir, "remote", "get-url", "origin"),
        "branch": git_output(repo_dir, "branch", "--show-current"),
        "commit": git_output(repo_dir, "rev-parse", "HEAD"),
        "commit_date": git_output(repo_dir, "log", "-1", "--format=%ci"),
        "commit_subject": git_output(repo_dir, "log", "-1", "--format=%s"),
        "dirty": bool(git_output(repo_dir, "status", "--short")),
    }


def ensure_clean_source(repo_dir: Path) -> None:
    status = git_output(repo_dir, "status", "--short")
    if status:
        raise SystemExit(f"Source checkout has local changes; refusing to update:\n{status}")


def fast_forward_source(repo_dir: Path, *, remote: str, branch: str, command_runner: CommandRunner) -> None:
    ensure_clean_source(repo_dir)
    command_runner(["git", "-C", str(repo_dir), "fetch", remote, branch])
    command_runner(["git", "-C", str(repo_dir), "merge", "--ff-only", f"{remote}/{branch}"])
