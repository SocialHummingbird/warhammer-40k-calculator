from datetime import UTC, datetime

from warhammer.artifact_manifest import (
    build_artifact_manifest,
    copy_artifacts,
    linked_ml_artifact_payload,
    portable_manifest_path,
    sha256_file,
    snapshot_name_from_source,
    write_snapshot,
)


def test_build_artifact_manifest_hashes_generated_files(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    (tmp_path / "weapons.csv").write_text("weapon_id,unit_id,name\nw1,u1,Gun\n", encoding="utf-8")
    (tmp_path / "edition_status.json").write_text('{"edition":"10e"}\n', encoding="utf-8")

    manifest = build_artifact_manifest(tmp_path, {"commit": "abc"})

    assert manifest["source"]["commit"] == "abc"
    assert manifest["artifacts"]["units.csv"]["bytes"] > 0
    assert manifest["artifacts"]["edition_status.json"]["bytes"] > 0
    assert manifest["artifacts"]["units.csv"]["sha256"] == sha256_file(tmp_path / "units.csv")
    assert "artifact_manifest.json" not in manifest["artifacts"]
    assert manifest["linked_ml_artifacts"] == {}


def test_build_artifact_manifest_links_ml_artifacts(tmp_path):
    project_root = tmp_path
    data_dir = project_root / "data" / "10e" / "latest"
    model_dir = project_root / "models" / "10e"
    data_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    (data_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    feature_path = project_root / "data" / "ml" / "10e" / "features.csv"
    feature_path.parent.mkdir(parents=True)
    model_path = model_dir / "model.json"
    audit_path = model_dir / "model.md"
    comparison_path = model_dir / "model_comparison.md"
    feature_path.write_text("winner_label\nattacker\n", encoding="utf-8")
    model_path.write_text('{"model_type":"test"}\n', encoding="utf-8")
    audit_path.write_text("# Audit\n", encoding="utf-8")
    comparison_path.write_text("# Comparison\n", encoding="utf-8")

    manifest = build_artifact_manifest(
        data_dir,
        {"commit": "abc"},
        linked_ml_artifacts={
            "edition": "10e",
            "feature_set": "pre_match",
            "feature_rows": 1,
            "feature_path": feature_path,
            "model_path": model_path,
            "audit_path": audit_path,
            "comparison_path": comparison_path,
        },
        project_root=project_root,
    )

    linked = manifest["linked_ml_artifacts"]
    assert linked["edition"] == "10e"
    assert linked["feature_set"] == "pre_match"
    assert linked["feature_rows"] == 1
    assert set(linked["artifacts"]) == {"feature_csv", "model_json", "model_audit", "model_comparison"}
    assert linked["artifacts"]["feature_csv"]["path"] == "data/ml/10e/features.csv"
    assert linked["artifacts"]["model_json"]["path"] == "models/10e/model.json"


def test_linked_ml_artifact_payload_skips_missing_paths(tmp_path):
    payload = linked_ml_artifact_payload(
        {"feature_path": tmp_path / "missing.csv", "model_type": "centroid"},
        base_dir=tmp_path,
        project_root=tmp_path,
    )

    assert payload["model_type"] == "centroid"
    assert payload["artifacts"] == {}


def test_portable_manifest_path_prefers_base_dir_then_project_root(tmp_path):
    data_dir = tmp_path / "data" / "10e" / "latest"
    project_file = tmp_path / "models" / "10e" / "model.json"
    local_file = data_dir / "units.csv"
    project_file.parent.mkdir(parents=True)
    local_file.parent.mkdir(parents=True)
    project_file.write_text("{}", encoding="utf-8")
    local_file.write_text("unit_id\n", encoding="utf-8")

    assert portable_manifest_path(local_file, base_dir=data_dir, project_root=tmp_path) == "units.csv"
    assert portable_manifest_path(project_file, base_dir=data_dir, project_root=tmp_path) == "models/10e/model.json"


def test_copy_artifacts_copies_only_known_existing_files(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    (source_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    (source_dir / "ignored.txt").write_text("ignored\n", encoding="utf-8")

    copy_artifacts(source_dir, target_dir, artifacts=("units.csv", "weapons.csv"))

    assert (target_dir / "units.csv").read_text(encoding="utf-8") == "unit_id,name\nu1,Test\n"
    assert not (target_dir / "weapons.csv").exists()
    assert not (target_dir / "ignored.txt").exists()


def test_write_snapshot_uses_commit_prefix_and_copies_artifacts(tmp_path):
    csv_dir = tmp_path / "latest"
    snapshot_dir = tmp_path / "snapshots"
    csv_dir.mkdir()
    (csv_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")

    target = write_snapshot(csv_dir, snapshot_dir, {"commit": "abcdef1234567890"}, artifacts=("units.csv",))

    assert target == snapshot_dir / "abcdef123456"
    assert (target / "units.csv").read_text(encoding="utf-8") == "unit_id,name\nu1,Test\n"


def test_snapshot_name_from_source_falls_back_to_timestamp():
    timestamp = datetime(2026, 4, 26, 12, 30, 0, tzinfo=UTC)

    assert snapshot_name_from_source({"commit": "unknown"}, timestamp=timestamp) == "20260426T123000Z"
