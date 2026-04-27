import json

from warhammer.update_finalize import finalize_update_artifacts


def test_finalize_update_artifacts_writes_manifest_exports_html_snapshots_and_mirrors(tmp_path):
    commands = []
    csv_dir = tmp_path / "data" / "10e" / "latest"
    snapshot_dir = tmp_path / "data" / "10e" / "snapshots"
    legacy_latest = tmp_path / "data" / "latest"
    model_path = tmp_path / "models" / "10e" / "matchup_centroid_model.json"
    csv_dir.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    (csv_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    model_path.write_text('{"model_type":"centroid"}\n', encoding="utf-8")

    finalized = finalize_update_artifacts(
        csv_dir=csv_dir,
        source_after={"commit": "abcdef1234567890"},
        ml_artifacts={
            "edition": "10e",
            "feature_set": "pre_match",
            "model_type": "centroid",
            "feature_rows": 10,
            "model_path": model_path,
        },
        skip_html=False,
        skip_snapshot=False,
        snapshot_dir=snapshot_dir,
        legacy_latest_dir=legacy_latest,
        skip_legacy_latest=False,
        project_root=tmp_path,
        command_runner=lambda command, cwd: commands.append((list(command), cwd)),
        python_executable="python",
    )

    manifest = json.loads((csv_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["commit"] == "abcdef1234567890"
    assert manifest["artifacts"]["units.csv"]["bytes"] > 0
    assert manifest["linked_ml_artifacts"]["model_type"] == "centroid"
    assert commands == [
        (
            [
                "python",
                "export_local_html.py",
                "--csv-dir",
                str(csv_dir),
                "--model",
                str(model_path),
            ],
            tmp_path,
        )
    ]
    assert finalized.snapshot_path == snapshot_dir / "abcdef123456"
    assert (finalized.snapshot_path / "artifact_manifest.json").exists()
    assert (legacy_latest / "artifact_manifest.json").exists()
    assert (legacy_latest / "units.csv").exists()


def test_finalize_update_artifacts_respects_skip_flags(tmp_path):
    commands = []
    csv_dir = tmp_path / "latest"
    snapshot_dir = tmp_path / "snapshots"
    legacy_latest = tmp_path / "legacy"
    csv_dir.mkdir()
    (csv_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")

    finalized = finalize_update_artifacts(
        csv_dir=csv_dir,
        source_after={"commit": "abcdef1234567890"},
        ml_artifacts=None,
        skip_html=True,
        skip_snapshot=True,
        snapshot_dir=snapshot_dir,
        legacy_latest_dir=legacy_latest,
        skip_legacy_latest=True,
        project_root=tmp_path,
        command_runner=lambda command, cwd: commands.append((list(command), cwd)),
        python_executable="python",
    )

    assert finalized.snapshot_path is None
    assert commands == []
    assert (csv_dir / "artifact_manifest.json").exists()
    assert not snapshot_dir.exists()
    assert not legacy_latest.exists()
