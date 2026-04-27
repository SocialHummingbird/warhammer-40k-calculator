from pathlib import Path

from warhammer.release_verification import ReleaseCheck, build_release_checks, run_release_checks


def test_build_release_checks_includes_tests_artifacts_and_review_gate():
    checks = build_release_checks(
        python_executable="python",
        data_dirs=[Path("data/10e/latest"), Path("data/latest")],
        review_data_dir=Path("data/10e/latest"),
        thresholds=Path("config/review_thresholds_10e.json"),
    )

    assert checks == [
        ReleaseCheck("pytest", ["python", "-m", "pytest", "-q"]),
        ReleaseCheck(
            "artifact manifest: data\\10e\\latest" if "\\" in str(Path("x\\y")) else "artifact manifest: data/10e/latest",
            ["python", "verify_artifacts.py", "--data-dir", str(Path("data/10e/latest"))],
        ),
        ReleaseCheck(
            "artifact manifest: data\\latest" if "\\" in str(Path("x\\y")) else "artifact manifest: data/latest",
            ["python", "verify_artifacts.py", "--data-dir", str(Path("data/latest"))],
        ),
        ReleaseCheck(
            "data review gate",
            [
                "python",
                "data_review_summary.py",
                "--data-dir",
                str(Path("data/10e/latest")),
                "--fail-on-issues",
                "--thresholds",
                str(Path("config/review_thresholds_10e.json")),
            ],
        ),
    ]


def test_build_release_checks_can_skip_tests_and_review_gate():
    checks = build_release_checks(
        python_executable="python",
        data_dirs=[Path("data/latest")],
        review_data_dir=Path("data/latest"),
        thresholds=None,
        skip_tests=True,
        skip_review_gate=True,
    )

    assert checks == [
        ReleaseCheck(
            "artifact manifest: data\\latest" if "\\" in str(Path("x\\y")) else "artifact manifest: data/latest",
            ["python", "verify_artifacts.py", "--data-dir", str(Path("data/latest"))],
        )
    ]


def test_run_release_checks_stops_on_first_failure(tmp_path):
    calls = []
    messages = []

    def runner(command, cwd):
        calls.append((list(command), cwd))
        return 2 if command[0] == "fail" else 0

    result = run_release_checks(
        [
            ReleaseCheck("first", ["ok"]),
            ReleaseCheck("second", ["fail"]),
            ReleaseCheck("third", ["never"]),
        ],
        project_root=tmp_path,
        command_runner=runner,
        message_sink=messages.append,
    )

    assert result == 2
    assert calls == [(["ok"], tmp_path), (["fail"], tmp_path)]
    assert messages[-1] == "Release verification failed: second"
