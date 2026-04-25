import json
import hashlib

from verify_artifacts import verify_artifacts


def test_verify_artifacts_accepts_matching_manifest(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        }
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    assert report["ok"] is True
    assert report["ok_count"] == 1
    assert report["failed_count"] == 0


def test_verify_artifacts_reports_mismatch(tmp_path):
    (tmp_path / "units.csv").write_text("changed\n", encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": 1,
                "sha256": "0" * 64,
            },
            "missing.csv": {
                "bytes": 1,
                "sha256": "0" * 64,
            },
        }
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    assert report["ok"] is False
    assert report["failed_count"] == 2
    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert statuses["units.csv"] == "mismatch"
    assert statuses["missing.csv"] == "missing"
