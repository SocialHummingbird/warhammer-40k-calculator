from pathlib import Path
import json
import subprocess
import sys

import warhammer.update_pipeline as update_pipeline
from warhammer.update_finalize import FinalizedArtifacts
from warhammer.update_reports import GeneratedReports


def test_run_update_orchestrates_refresh_pipeline(monkeypatch, tmp_path):
    calls = []
    commands = []
    data_dir = tmp_path / "data" / "10e" / "latest"
    repo_dir = tmp_path / "data" / "wh40k-10e"
    data_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    table_snapshots = iter([{"units": {}}, {"units": {"u1": {"unit_id": "u1"}}}])
    source_snapshots = iter([{"commit": "old"}, {"commit": "new"}])
    reports = GeneratedReports(
        audit_report={"summary": {"error": 0, "warning": 0, "info": 0}},
        schema_review_rows=5,
        profile_review_counts={"weapon_profiles": 1, "ability_profiles": 2},
        edition_status={"edition": "10e"},
    )
    finalized = FinalizedArtifacts(snapshot_path=tmp_path / "data" / "10e" / "snapshots" / "new")

    monkeypatch.setattr(update_pipeline, "load_tables", lambda csv_dir: next(table_snapshots))
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir_arg: next(source_snapshots))
    monkeypatch.setattr(update_pipeline, "fast_forward_source", lambda repo_dir_arg, remote, branch, command_runner: calls.append(("fast_forward", repo_dir_arg, remote, branch)))
    monkeypatch.setattr(update_pipeline, "build_import_diff", lambda before, after, source_before, source_after: {"tables": {}, "source_before": source_before, "source_after": source_after})
    monkeypatch.setattr(update_pipeline, "write_json_file", lambda path, payload: calls.append(("write_json", path, payload)))
    monkeypatch.setattr(update_pipeline, "write_generated_reports", lambda **kwargs: calls.append(("reports", kwargs)) or reports)
    monkeypatch.setattr(update_pipeline, "refresh_ml_artifacts", lambda **kwargs: calls.append(("ml", kwargs)) or {"model_path": tmp_path / "models" / "model.json"})
    monkeypatch.setattr(update_pipeline, "finalize_update_artifacts", lambda **kwargs: calls.append(("finalize", kwargs)) or finalized)
    monkeypatch.setattr(update_pipeline, "print_update_summary", lambda *args: calls.append(("summary", args)))

    result = update_pipeline.run_update(
        ["--skip-fetch"],
        project_root=tmp_path,
        python_executable="python",
        command_runner=lambda command, cwd=None: commands.append((list(command), cwd)),
        message_sink=lambda message: calls.append(("message", message)),
    )

    assert result == 0
    assert commands == [
        (
            [
                "python",
                "import_bsdata.py",
                str(repo_dir.resolve()),
                "--output",
                str(data_dir.resolve()),
                "--edition",
                "10e",
            ],
            tmp_path,
        )
    ]
    assert not any(call[0] == "fast_forward" for call in calls)
    assert calls[0][0] == "write_json"
    assert calls[0][1] == data_dir.resolve() / "import_diff.json"
    report_call = next(call for call in calls if call[0] == "reports")
    assert report_call[1]["csv_dir"] == data_dir.resolve()
    assert report_call[1]["source_after"] == {"commit": "new"}
    ml_call = next(call for call in calls if call[0] == "ml")
    assert ml_call[1]["ml_root"] == tmp_path / "data" / "ml"
    assert ml_call[1]["model_root"] == tmp_path / "models"
    assert ml_call[1]["label_overrides_path"] is None
    assert ml_call[1]["label_key_columns"] == ["edition", "mode", "attacker_id", "defender_id"]
    finalize_call = next(call for call in calls if call[0] == "finalize")
    assert finalize_call[1]["ml_artifacts"]["model_path"] == tmp_path / "models" / "model.json"
    assert finalize_call[1]["snapshot_dir"] == tmp_path / "data" / "10e" / "snapshots"
    summary_call = calls[-1]
    assert summary_call[0] == "summary"
    assert summary_call[1][0] == {"commit": "old"}
    assert summary_call[1][4] == finalized.snapshot_path


def test_run_update_seeds_missing_csv_dir_from_legacy_and_honours_skip_flags(monkeypatch, tmp_path):
    calls = []
    commands = []
    data_dir = tmp_path / "data" / "10e" / "latest"
    legacy_dir = tmp_path / "data" / "latest"
    repo_dir = tmp_path / "data" / "wh40k-10e"
    legacy_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    table_snapshots = iter([{"units": {}}, {"units": {}}])
    source_snapshots = iter([{"commit": "old"}, {"commit": "new"}])
    reports = GeneratedReports(
        audit_report={"summary": {"error": 0, "warning": 0, "info": 0}},
        schema_review_rows=0,
        profile_review_counts={"weapon_profiles": 0, "ability_profiles": 0},
        edition_status={"edition": "10e"},
    )
    finalized = FinalizedArtifacts(snapshot_path=None)

    monkeypatch.setattr(update_pipeline, "copy_artifacts", lambda source, target: calls.append(("copy", source, target)))
    monkeypatch.setattr(update_pipeline, "load_tables", lambda csv_dir: next(table_snapshots))
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir_arg: next(source_snapshots))
    monkeypatch.setattr(update_pipeline, "fast_forward_source", lambda *args, **kwargs: calls.append(("fast_forward", args, kwargs)))
    monkeypatch.setattr(update_pipeline, "build_import_diff", lambda before, after, source_before, source_after: {"tables": {}})
    monkeypatch.setattr(update_pipeline, "write_json_file", lambda path, payload: calls.append(("write_json", path, payload)))
    monkeypatch.setattr(update_pipeline, "write_generated_reports", lambda **kwargs: calls.append(("reports", kwargs)) or reports)
    monkeypatch.setattr(update_pipeline, "refresh_ml_artifacts", lambda **kwargs: calls.append(("ml", kwargs)))
    monkeypatch.setattr(update_pipeline, "finalize_update_artifacts", lambda **kwargs: calls.append(("finalize", kwargs)) or finalized)
    monkeypatch.setattr(update_pipeline, "print_update_summary", lambda *args: calls.append(("summary", args)))

    result = update_pipeline.run_update(
        [
            "--skip-fetch",
            "--skip-ml",
            "--skip-html",
            "--skip-snapshot",
            "--skip-legacy-latest",
        ],
        project_root=tmp_path,
        python_executable="python",
        command_runner=lambda command, cwd=None: commands.append((list(command), cwd)),
    )

    assert result == 0
    assert ("copy", legacy_dir.resolve(), data_dir.resolve()) in calls
    assert not any(call[0] == "fast_forward" for call in calls)
    assert not any(call[0] == "ml" for call in calls)
    finalize_call = next(call for call in calls if call[0] == "finalize")
    assert finalize_call[1]["ml_artifacts"] is None
    assert finalize_call[1]["skip_html"] is True
    assert finalize_call[1]["skip_snapshot"] is True
    assert finalize_call[1]["skip_legacy_latest"] is True
    assert finalize_call[1]["legacy_latest_dir"] == legacy_dir.resolve()
    assert commands == [
        (
            [
                "python",
                "import_bsdata.py",
                str(repo_dir.resolve()),
                "--output",
                str(data_dir.resolve()),
                "--edition",
                "10e",
            ],
            tmp_path,
        )
    ]


def test_run_update_writes_real_reports_and_manifest_from_tiny_import(monkeypatch, tmp_path):
    source_snapshots = iter(
        [
            {"remote_origin": "origin", "branch": "main", "commit": "old", "commit_date": "", "commit_subject": "Old"},
            {"remote_origin": "origin", "branch": "main", "commit": "new", "commit_date": "", "commit_subject": "New"},
        ]
    )
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir: next(source_snapshots))

    def fake_import(command, cwd=None):
        assert command[1] == "import_bsdata.py"
        output = Path(command[command.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "units.csv").write_text(
            "unit_id,faction,name,toughness,save,invulnerable_save,wounds,move,leadership,objective_control,points,models_min,models_max,feel_no_pain,damage_cap,selection_type,source_file\n"
            "u1,Test,Target,4,3+,,2,6,6+,2,100,1,1,,,unit,Test.cat\n",
            encoding="utf-8",
        )
        (output / "weapons.csv").write_text(
            "weapon_id,unit_id,name,weapon_type,attacks,skill,strength,ap,damage,keywords,hit_modifier,wound_modifier,reroll_hits,reroll_wounds,lethal_hits,sustained_hits,devastating_wounds,source_file\n"
            "w1,u1,Bolt rifle,ranged,2,3+,4,-1,1,Assault,,,,,,,,Test.cat\n",
            encoding="utf-8",
        )
        (output / "abilities.csv").write_text("ability_id,source_type,source_id,name,text,source_file\n", encoding="utf-8")
        (output / "keywords.csv").write_text("keyword_id,keyword,description\n", encoding="utf-8")
        (output / "unit_keywords.csv").write_text("unit_id,keyword_id\n", encoding="utf-8")
        (output / "metadata.json").write_text(
            json.dumps({"rules_edition": "10e", "counts": {"units": 1, "weapons": 1}}),
            encoding="utf-8",
        )

    result = update_pipeline.run_update(
        [
            "--skip-fetch",
            "--skip-ml",
            "--skip-html",
            "--skip-snapshot",
            "--skip-legacy-latest",
        ],
        project_root=tmp_path,
        python_executable="python",
        command_runner=fake_import,
    )

    data_dir = tmp_path / "data" / "10e" / "latest"
    assert result == 0
    assert (data_dir / "import_diff.json").exists()
    assert (data_dir / "audit_report.json").exists()
    assert (data_dir / "schema_review.csv").exists()
    assert (data_dir / "edition_status.json").exists()
    assert (data_dir / "edition_readiness.md").exists()
    assert (data_dir / "update_report.md").exists()
    assert (data_dir / "profile_review.md").exists()
    assert (data_dir / "artifact_manifest.json").exists()

    edition_status = json.loads((data_dir / "edition_status.json").read_text(encoding="utf-8"))
    manifest = json.loads((data_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert edition_status["status"] == "ready"
    assert edition_status["counts"]["units"] == 1
    assert manifest["source"]["commit"] == "new"
    assert manifest["linked_ml_artifacts"] == {}
    assert "artifact_manifest.json" not in manifest["artifacts"]


def test_run_update_can_gate_generated_data_review(monkeypatch, tmp_path):
    calls = []
    commands = []
    data_dir = tmp_path / "data" / "10e" / "latest"
    repo_dir = tmp_path / "data" / "wh40k-10e"
    data_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    table_snapshots = iter([{"units": {}}, {"units": {}}])
    source_snapshots = iter([{"commit": "old"}, {"commit": "new"}])
    reports = GeneratedReports(
        audit_report={"summary": {"error": 0, "warning": 0, "info": 0}},
        schema_review_rows=0,
        profile_review_counts={"weapon_profiles": 0, "ability_profiles": 0},
        edition_status={"edition": "10e"},
    )
    finalized = FinalizedArtifacts(snapshot_path=None)

    monkeypatch.setattr(update_pipeline, "load_tables", lambda csv_dir: next(table_snapshots))
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir_arg: next(source_snapshots))
    monkeypatch.setattr(update_pipeline, "build_import_diff", lambda before, after, source_before, source_after: {"tables": {}})
    monkeypatch.setattr(update_pipeline, "write_json_file", lambda path, payload: None)
    monkeypatch.setattr(update_pipeline, "write_generated_reports", lambda **kwargs: calls.append(("reports", kwargs)) or reports)
    monkeypatch.setattr(update_pipeline, "refresh_ml_artifacts", lambda **kwargs: None)
    monkeypatch.setattr(update_pipeline, "finalize_update_artifacts", lambda **kwargs: finalized)
    monkeypatch.setattr(update_pipeline, "print_update_summary", lambda *args: None)
    monkeypatch.setattr(
        update_pipeline,
        "data_review_payload",
        lambda data_dir_arg, **kwargs: calls.append(("payload", data_dir_arg, kwargs)) or {"edition": "10e"},
    )
    monkeypatch.setattr(
        update_pipeline,
        "build_data_review_gate_failures",
        lambda payload, fail_on_warnings, thresholds=None: calls.append(("gate", payload, fail_on_warnings, thresholds)) or [],
    )

    result = update_pipeline.run_update(
        ["--skip-fetch", "--skip-ml", "--skip-html", "--skip-snapshot", "--skip-legacy-latest", "--fail-on-review-issues"],
        project_root=tmp_path,
        python_executable="python",
        command_runner=lambda command, cwd=None: commands.append((list(command), cwd)),
        message_sink=lambda message: calls.append(("message", message)),
    )

    assert result == 0
    payload_call = next(call for call in calls if call[0] == "payload")
    assert payload_call[1] == data_dir.resolve()
    assert payload_call[2]["edition"] == "10e"
    assert payload_call[2]["model_dir"] == tmp_path / "models" / "10e"
    assert ("gate", {"edition": "10e"}, False, {}) in calls
    assert ("message", "Data review gate passed.") in calls
    assert not any(call == ("message", "Review gate thresholds:") for call in calls)


def test_run_update_returns_nonzero_when_data_review_gate_fails(monkeypatch, tmp_path):
    calls = []
    data_dir = tmp_path / "data" / "10e" / "latest"
    repo_dir = tmp_path / "data" / "wh40k-10e"
    thresholds_path = tmp_path / "review_thresholds.json"
    thresholds_path.write_text('{"suspicious_weapon_warnings": 17, "loadout_warnings": 120}', encoding="utf-8")
    data_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    table_snapshots = iter([{"units": {}}, {"units": {}}])
    source_snapshots = iter([{"commit": "old"}, {"commit": "new"}])
    reports = GeneratedReports(
        audit_report={"summary": {"error": 0, "warning": 0, "info": 0}},
        schema_review_rows=0,
        profile_review_counts={"weapon_profiles": 0, "ability_profiles": 0},
        edition_status={"edition": "10e"},
    )
    finalized = FinalizedArtifacts(snapshot_path=None)

    monkeypatch.setattr(update_pipeline, "load_tables", lambda csv_dir: next(table_snapshots))
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir_arg: next(source_snapshots))
    monkeypatch.setattr(update_pipeline, "build_import_diff", lambda before, after, source_before, source_after: {"tables": {}})
    monkeypatch.setattr(update_pipeline, "write_json_file", lambda path, payload: None)
    monkeypatch.setattr(update_pipeline, "write_generated_reports", lambda **kwargs: calls.append(("reports", kwargs)) or reports)
    monkeypatch.setattr(update_pipeline, "refresh_ml_artifacts", lambda **kwargs: None)
    monkeypatch.setattr(update_pipeline, "finalize_update_artifacts", lambda **kwargs: finalized)
    monkeypatch.setattr(update_pipeline, "print_update_summary", lambda *args: None)
    monkeypatch.setattr(update_pipeline, "data_review_payload", lambda data_dir_arg, **kwargs: {})
    monkeypatch.setattr(
        update_pipeline,
        "build_data_review_gate_failures",
        lambda payload, fail_on_warnings, thresholds=None: calls.append(("gate", fail_on_warnings, thresholds))
        or ["schema review has 1 fail rows"],
    )

    result = update_pipeline.run_update(
        [
            "--skip-fetch",
            "--skip-ml",
            "--skip-html",
            "--skip-snapshot",
            "--skip-legacy-latest",
            "--fail-on-review-issues",
            "--review-fail-on-warnings",
            "--review-thresholds",
            str(thresholds_path),
            "--max-loadout-warnings",
            "120",
        ],
        project_root=tmp_path,
        python_executable="python",
        command_runner=lambda command, cwd=None: None,
        message_sink=lambda message: calls.append(("message", message)),
    )

    assert result == 1
    report_call = next(call for call in calls if call[0] == "reports")
    assert report_call[1]["review_thresholds"] == {"loadout_warnings": 120, "suspicious_weapon_warnings": 17}
    assert ("gate", True, {"loadout_warnings": 120, "suspicious_weapon_warnings": 17}) in calls
    assert ("message", "Review gate thresholds:") in calls
    assert ("message", "- loadout warnings: 120") in calls
    assert ("message", "- suspicious weapon warnings: 17") in calls
    assert ("message", "Data review gate failed:") in calls
    assert ("message", "- schema review has 1 fail rows") in calls


def test_run_update_can_write_current_review_thresholds(monkeypatch, tmp_path):
    calls = []
    data_dir = tmp_path / "data" / "10e" / "latest"
    repo_dir = tmp_path / "data" / "wh40k-10e"
    output_thresholds = tmp_path / "accepted_thresholds.json"
    data_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    table_snapshots = iter([{"units": {}}, {"units": {}}])
    source_snapshots = iter([{"commit": "old"}, {"commit": "new"}])
    reports = GeneratedReports(
        audit_report={"summary": {"error": 0, "warning": 0, "info": 0}},
        schema_review_rows=0,
        profile_review_counts={"weapon_profiles": 0, "ability_profiles": 0},
        edition_status={"edition": "10e"},
    )
    finalized = FinalizedArtifacts(snapshot_path=None)
    payload = {
        "audit_report": {"summary": {"warning": 1}},
        "suspicious_weapon_summary": {"by_severity": {"warning": 2}},
        "unit_profile_summary": {"by_severity": {"warning": 3}},
        "loadout_summary": {"by_severity": {"warning": 4}},
        "weapon_coverage_summary": {"no_weapon_total": 5},
    }

    monkeypatch.setattr(update_pipeline, "load_tables", lambda csv_dir: next(table_snapshots))
    monkeypatch.setattr(update_pipeline, "source_metadata", lambda repo_dir_arg: next(source_snapshots))
    monkeypatch.setattr(update_pipeline, "build_import_diff", lambda before, after, source_before, source_after: {"tables": {}})
    monkeypatch.setattr(update_pipeline, "write_json_file", lambda path, payload_arg: calls.append(("write_json", path, payload_arg)))
    monkeypatch.setattr(update_pipeline, "write_generated_reports", lambda **kwargs: reports)
    monkeypatch.setattr(update_pipeline, "refresh_ml_artifacts", lambda **kwargs: None)
    monkeypatch.setattr(update_pipeline, "finalize_update_artifacts", lambda **kwargs: finalized)
    monkeypatch.setattr(update_pipeline, "print_update_summary", lambda *args: None)
    monkeypatch.setattr(update_pipeline, "data_review_payload", lambda data_dir_arg, **kwargs: payload)

    result = update_pipeline.run_update(
        [
            "--skip-fetch",
            "--skip-ml",
            "--skip-html",
            "--skip-snapshot",
            "--skip-legacy-latest",
            "--write-review-thresholds",
            str(output_thresholds),
        ],
        project_root=tmp_path,
        python_executable="python",
        command_runner=lambda command, cwd=None: None,
        message_sink=lambda message: calls.append(("message", message)),
    )

    assert result == 0
    assert ("write_json", output_thresholds.resolve(), {
        "audit_warnings": 1,
        "suspicious_weapon_warnings": 2,
        "unit_profile_warnings": 3,
        "loadout_warnings": 4,
        "no_weapon_units": 5,
    }) in calls
    assert ("message", f"Wrote review thresholds to {output_thresholds.resolve()}") in calls


def test_update_database_main_delegates_to_pipeline(monkeypatch):
    import update_database

    observed = {}

    def fake_run_update(argv, project_root):
        observed["args"] = (argv, project_root)
        return 7

    monkeypatch.setattr(update_database, "run_update", fake_run_update)

    assert update_database.main(["--skip-fetch"]) == 7
    assert observed["args"] == (["--skip-fetch"], update_database.PROJECT_ROOT)


def test_update_database_script_help_exposes_update_flags():
    project_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, "update_database.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Update BSData source, regenerate CSVs, audit, diff, and local HTML" in completed.stdout
    assert "--ml-model-type" in completed.stdout
    assert "--ml-labels" in completed.stdout
    assert "--ml-label-key-columns" in completed.stdout
    assert "--skip-legacy-latest" in completed.stdout
    assert "--fail-on-review-issues" in completed.stdout
    assert "--review-thresholds" in completed.stdout
    assert "--write-review-thresholds" in completed.stdout
    assert "--max-loadout-warnings" in completed.stdout
    assert "--edition" in completed.stdout
