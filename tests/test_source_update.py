import pytest

import warhammer.source_update as source_update


class Completed:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout


def test_git_output_returns_stripped_stdout(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed(0, "abc123\n")

    monkeypatch.setattr(source_update.subprocess, "run", run)

    assert source_update.git_output(tmp_path, "rev-parse", "HEAD") == "abc123"
    assert calls[0][0] == ["git", "-C", str(tmp_path), "rev-parse", "HEAD"]
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True


def test_git_output_returns_empty_string_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(source_update.subprocess, "run", lambda command, **kwargs: Completed(1, "fatal\n"))

    assert source_update.git_output(tmp_path, "branch", "--show-current") == ""


def test_source_metadata_collects_source_fields(monkeypatch, tmp_path):
    values = {
        ("remote", "get-url", "origin"): "https://github.com/BSData/wh40k-10e.git",
        ("branch", "--show-current"): "main",
        ("rev-parse", "HEAD"): "abcdef",
        ("log", "-1", "--format=%ci"): "2026-04-26 12:00:00 +0100",
        ("log", "-1", "--format=%s"): "Update data",
        ("status", "--short"): " M Orks.cat",
    }
    monkeypatch.setattr(source_update, "git_output", lambda repo_dir, *args: values[args])

    metadata = source_update.source_metadata(tmp_path)

    assert metadata == {
        "path": str(tmp_path),
        "remote_origin": "https://github.com/BSData/wh40k-10e.git",
        "branch": "main",
        "commit": "abcdef",
        "commit_date": "2026-04-26 12:00:00 +0100",
        "commit_subject": "Update data",
        "dirty": True,
    }


def test_ensure_clean_source_rejects_dirty_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(source_update, "git_output", lambda repo_dir, *args: " M Orks.cat")

    with pytest.raises(SystemExit, match="Source checkout has local changes"):
        source_update.ensure_clean_source(tmp_path)


def test_fast_forward_source_checks_clean_then_fetches_and_merges(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(source_update, "git_output", lambda repo_dir, *args: "")

    source_update.fast_forward_source(
        tmp_path,
        remote="origin",
        branch="main",
        command_runner=commands.append,
    )

    assert commands == [
        ["git", "-C", str(tmp_path), "fetch", "origin", "main"],
        ["git", "-C", str(tmp_path), "merge", "--ff-only", "origin/main"],
    ]
