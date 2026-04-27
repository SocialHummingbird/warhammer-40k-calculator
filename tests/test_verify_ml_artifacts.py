import csv

from warhammer.ml.model import DEFAULT_FEATURE_COLUMNS, train_from_csv
from verify_ml_artifacts import verify_ml_artifacts


def _row(label):
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update({"label_source": "deterministic_calculator", "winner_label": label})
    return row


def _write_features(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label_source", "winner_label", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)


def test_verify_ml_artifacts_accepts_matching_feature_and_model(tmp_path):
    features = tmp_path / "features.csv"
    model = tmp_path / "model.json"
    _write_features(features, [_row("attacker"), _row("defender")])
    train_from_csv(features, model, validation_fraction=0, feature_set="pre_match")

    report = verify_ml_artifacts(features, model)

    assert report["ok"] is True
    assert report["failed_count"] == 0


def test_verify_ml_artifacts_detects_stale_feature_csv(tmp_path):
    features = tmp_path / "features.csv"
    model = tmp_path / "model.json"
    _write_features(features, [_row("attacker"), _row("defender")])
    train_from_csv(features, model, validation_fraction=0, feature_set="pre_match")
    with features.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label_source", "winner_label", *DEFAULT_FEATURE_COLUMNS])
        writer.writerow(_row("attacker"))

    report = verify_ml_artifacts(features, model)

    assert report["ok"] is False
    statuses = {item["name"]: item["status"] for item in report["results"]}
    assert statuses["training_source.rows"] == "mismatch"
    assert statuses["training_source.sha256"] == "mismatch"


def test_verify_ml_artifacts_detects_model_columns_missing_from_csv(tmp_path):
    features = tmp_path / "features.csv"
    model = tmp_path / "model.json"
    _write_features(features, [_row("attacker"), _row("defender")])
    trained = train_from_csv(features, model, validation_fraction=0, feature_set="pre_match")
    reduced = tmp_path / "reduced.csv"
    reduced.write_text("winner_label,attacker_points\nattacker,100\n", encoding="utf-8")

    report = verify_ml_artifacts(reduced, model)

    assert report["ok"] is False
    feature_check = next(item for item in report["results"] if item["name"] == "feature_columns")
    assert feature_check["status"] == "missing_columns"
    assert "attacker_mode_avg_attacks" in feature_check["missing_columns"]
