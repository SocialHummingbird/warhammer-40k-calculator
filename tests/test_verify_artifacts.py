import json
import hashlib
import csv

from warhammer.ml.model import DEFAULT_FEATURE_COLUMNS, train_from_csv
from warhammer.rules import available_rulesets
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


def test_verify_artifacts_checks_supported_ruleset_capabilities(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    ruleset = available_rulesets()["10e"]
    (tmp_path / "edition_status.json").write_text(
        json.dumps(
            {
                "edition": "10e",
                "rules_available": True,
                "rule_capabilities": [
                    {"key": capability.key, "label": capability.label, "status": capability.status, "notes": []}
                    for capability in ruleset.capabilities
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            },
            "edition_status.json": {
                "bytes": (tmp_path / "edition_status.json").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "edition_status.json").read_bytes()).hexdigest(),
            },
        }
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert report["ok"] is True
    assert statuses["edition_status.rule_capabilities"] == "ok"


def test_verify_artifacts_reports_stale_ruleset_capabilities(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    (tmp_path / "edition_status.json").write_text(
        json.dumps(
            {
                "edition": "10e",
                "rules_available": True,
                "rule_capabilities": [{"key": "hit_rolls", "label": "Hit rolls"}],
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            },
            "edition_status.json": {
                "bytes": (tmp_path / "edition_status.json").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "edition_status.json").read_bytes()).hexdigest(),
            },
        }
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    capability = next(item for item in report["results"] if item["filename"] == "edition_status.rule_capabilities")
    assert report["ok"] is False
    assert capability["status"] == "mismatch"
    assert "wound_rolls" in capability["missing_keys"]


def test_verify_artifacts_checks_linked_ml_artifacts(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    ml_file = tmp_path / "model.json"
    ml_file.write_text('{"model_type":"nearest_centroid_classifier"}\n', encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "edition": "10e",
            "feature_set": "pre_match",
            "model_type": "centroid",
            "feature_rows": 1,
            "artifacts": {
                "model_json": {
                    "path": str(ml_file),
                    "bytes": ml_file.stat().st_size,
                    "sha256": hashlib.sha256(ml_file.read_bytes()).hexdigest(),
                }
            },
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    assert report["ok"] is True
    assert report["artifact_count"] == 3
    assert {item["filename"] for item in report["results"]} == {
        "units.csv",
        "linked_ml_artifacts.model_json",
        "linked_ml_artifacts.model_type",
    }


def test_verify_artifacts_reports_linked_ml_model_type_mismatch(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    ml_file = tmp_path / "model.json"
    ml_file.write_text('{"model_type":"nearest_centroid_classifier"}\n', encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "model_type": "logistic_regression",
            "artifacts": {
                "model_json": {
                    "path": str(ml_file),
                    "bytes": ml_file.stat().st_size,
                    "sha256": hashlib.sha256(ml_file.read_bytes()).hexdigest(),
                }
            },
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert statuses["linked_ml_artifacts.model_type"] == "mismatch"


def test_verify_artifacts_reports_linked_ml_mismatch(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    ml_file = tmp_path / "model.json"
    ml_file.write_text("changed\n", encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "artifacts": {
                "model_json": {
                    "path": str(ml_file),
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
                "model_audit": {
                    "path": str(tmp_path / "missing.md"),
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
            },
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    assert report["ok"] is False
    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert statuses["linked_ml_artifacts.model_json"] == "mismatch"
    assert statuses["linked_ml_artifacts.model_audit"] == "missing"


def test_verify_artifacts_checks_linked_ml_training_provenance(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    features = tmp_path / "features.csv"
    model = tmp_path / "model.json"
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update({"label_source": "deterministic_calculator", "winner_label": "attacker"})
    defender = dict(row)
    defender["winner_label"] = "defender"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label_source", "winner_label", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows([row, defender])
    train_from_csv(features, model, validation_fraction=0, feature_set="pre_match")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "artifacts": {
                "feature_csv": {
                    "path": str(features),
                    "bytes": features.stat().st_size,
                    "sha256": hashlib.sha256(features.read_bytes()).hexdigest(),
                },
                "model_json": {
                    "path": str(model),
                    "bytes": model.stat().st_size,
                    "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                },
            },
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_artifacts(tmp_path)

    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert statuses["linked_ml_artifacts.training_provenance"] == "ok"


def test_verify_artifacts_reports_linked_ml_training_provenance_mismatch(tmp_path):
    (tmp_path / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    features = tmp_path / "features.csv"
    model = tmp_path / "model.json"
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update({"label_source": "deterministic_calculator", "winner_label": "attacker"})
    defender = dict(row)
    defender["winner_label"] = "defender"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label_source", "winner_label", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows([row, defender])
    train_from_csv(features, model, validation_fraction=0, feature_set="pre_match")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (tmp_path / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((tmp_path / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "artifacts": {
                "feature_csv": {
                    "path": str(features),
                    "bytes": features.stat().st_size,
                    "sha256": hashlib.sha256(features.read_bytes()).hexdigest(),
                },
                "model_json": {
                    "path": str(model),
                    "bytes": model.stat().st_size,
                    "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                },
            },
        },
    }
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with features.open("a", encoding="utf-8") as handle:
        handle.write("changed\n")

    report = verify_artifacts(tmp_path)

    statuses = {item["filename"]: item["status"] for item in report["results"]}
    assert statuses["linked_ml_artifacts.feature_csv"] == "mismatch"
    assert statuses["linked_ml_artifacts.training_provenance"] == "mismatch"


def test_verify_artifacts_resolves_project_relative_linked_ml_paths(tmp_path, monkeypatch):
    project_root = tmp_path
    data_dir = project_root / "data" / "10e" / "latest"
    model_dir = project_root / "models" / "10e"
    data_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    (data_dir / "units.csv").write_text("unit_id,name\nu1,Test\n", encoding="utf-8")
    ml_file = model_dir / "model.json"
    ml_file.write_text('{"model_type":"test"}\n', encoding="utf-8")
    manifest = {
        "artifacts": {
            "units.csv": {
                "bytes": (data_dir / "units.csv").stat().st_size,
                "sha256": hashlib.sha256((data_dir / "units.csv").read_bytes()).hexdigest(),
            }
        },
        "linked_ml_artifacts": {
            "artifacts": {
                "model_json": {
                    "path": "models/10e/model.json",
                    "bytes": ml_file.stat().st_size,
                    "sha256": hashlib.sha256(ml_file.read_bytes()).hexdigest(),
                }
            },
        },
    }
    (data_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path / "data")

    report = verify_artifacts(data_dir)

    assert report["ok"] is True
