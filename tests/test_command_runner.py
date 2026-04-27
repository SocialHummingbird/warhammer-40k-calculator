import pytest

import warhammer.command_runner as command_runner


class Completed:
    def __init__(self, returncode):
        self.returncode = returncode


def test_run_command_passes_command_and_cwd(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed(0)

    monkeypatch.setattr(command_runner.subprocess, "run", run)

    command_runner.run_command(["python", "script.py"], cwd=tmp_path)

    assert calls == [(["python", "script.py"], {"cwd": tmp_path, "check": False})]


def test_run_command_raises_system_exit_on_failure(monkeypatch):
    monkeypatch.setattr(command_runner.subprocess, "run", lambda command, **kwargs: Completed(3))

    with pytest.raises(SystemExit, match="Command failed with exit 3: python bad.py"):
        command_runner.run_command(["python", "bad.py"])
