import csv

import pytest

from warhammer.ml.model import (
    DEFAULT_FEATURE_COLUMNS,
    PRE_MATCH_FEATURE_COLUMNS,
    apply_label_overrides,
    evaluate_model,
    feature_csv_provenance,
    feature_columns_for_set,
    load_model,
    missing_feature_columns,
    predict_row,
    train_centroid_model,
    train_from_csv,
    train_logistic_regression_model,
)


def _row(label, *, outgoing_damage, incoming_damage):
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update(
        {
            "edition": "10e",
            "mode": "ranged",
            "label_source": "deterministic_calculator",
            "winner_label": label,
            "attacker_id": "attacker-id",
            "defender_id": "defender-id",
            "outgoing_damage": outgoing_damage,
            "incoming_damage": incoming_damage,
            "damage_delta": outgoing_damage - incoming_damage,
            "outgoing_points_removed": outgoing_damage,
            "incoming_points_removed": incoming_damage,
            "points_removed_delta": outgoing_damage - incoming_damage,
        }
    )
    return row


def test_train_centroid_model_predicts_nearest_label():
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("attacker", outgoing_damage=6, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
        _row("defender", outgoing_damage=1, incoming_damage=6),
    ]

    model = train_centroid_model(rows, validation_fraction=0, feature_columns=DEFAULT_FEATURE_COLUMNS)

    assert sorted(model["labels"]) == ["attacker", "defender"]
    assert predict_row(model, _row("attacker", outgoing_damage=7, incoming_damage=1))["label"] == "attacker"
    assert predict_row(model, _row("defender", outgoing_damage=1, incoming_damage=7))["label"] == "defender"


def test_evaluate_model_reports_accuracy_and_confusion():
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
    ]
    model = train_centroid_model(rows, validation_fraction=0)

    report = evaluate_model(model, rows)

    assert report["accuracy"] == pytest.approx(1.0)
    assert report["correct"] == 2
    assert report["confusion"]["attacker"]["attacker"] == 1


def test_train_from_csv_writes_loadable_model(tmp_path):
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("attacker", outgoing_damage=6, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
        _row("defender", outgoing_damage=1, incoming_damage=6),
    ]
    features = tmp_path / "features.csv"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["edition", "mode", "label_source", "winner_label", "attacker_id", "defender_id", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)

    output = tmp_path / "model.json"
    model = train_from_csv(features, output, validation_fraction=0, seed=1)
    loaded = load_model(output)

    assert output.exists()
    assert loaded["model_type"] == "nearest_centroid_classifier"
    assert loaded["labels"] == model["labels"]
    assert loaded["training_source"]["rows"] == 4
    assert loaded["training_source"]["bytes"] == features.stat().st_size
    assert len(loaded["training_source"]["sha256"]) == 64


def test_feature_column_sets_expose_pre_match_columns_without_calculator_outputs():
    columns = feature_columns_for_set("pre_match")

    assert columns == PRE_MATCH_FEATURE_COLUMNS
    assert "attacker_points" in columns
    assert "outgoing_damage" not in columns
    assert "damage_delta" not in columns


def test_train_from_csv_can_write_pre_match_model(tmp_path):
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
    ]
    rows[0]["attacker_points"] = 200
    rows[1]["defender_points"] = 200
    features = tmp_path / "features.csv"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["edition", "mode", "label_source", "winner_label", "attacker_id", "defender_id", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)

    output = tmp_path / "model.json"
    loaded = train_from_csv(features, output, validation_fraction=0, seed=1, feature_set="pre_match")

    assert loaded["feature_set"] == "pre_match"
    assert loaded["feature_columns"] == PRE_MATCH_FEATURE_COLUMNS
    assert "outgoing_damage" not in loaded["feature_columns"]


def test_apply_label_overrides_replaces_matching_labels_only():
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        {**_row("defender", outgoing_damage=1, incoming_damage=5), "defender_id": "other-defender"},
    ]
    labels = [
        {
            "edition": "10e",
            "mode": "ranged",
            "attacker_id": "attacker-id",
            "defender_id": "defender-id",
            "winner_label": "defender",
        },
        {
            "edition": "10e",
            "mode": "ranged",
            "attacker_id": "missing",
            "defender_id": "defender-id",
            "winner_label": "attacker",
        },
    ]

    updated, summary = apply_label_overrides(rows, labels)

    assert updated[0]["winner_label"] == "defender"
    assert updated[0]["label_source"] == "external_labels"
    assert updated[1]["winner_label"] == "defender"
    assert summary["matched_rows"] == 1
    assert summary["override_rows"] == 2
    assert summary["skipped_rows"] == 0


def test_train_from_csv_records_external_label_override_metadata(tmp_path):
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        {**_row("defender", outgoing_damage=1, incoming_damage=5), "defender_id": "other-defender"},
    ]
    features = tmp_path / "features.csv"
    fieldnames = [
        "edition",
        "mode",
        "label_source",
        "winner_label",
        "attacker_id",
        "defender_id",
        *DEFAULT_FEATURE_COLUMNS,
    ]
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    labels = tmp_path / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["edition", "mode", "attacker_id", "defender_id", "winner_label"])
        writer.writeheader()
        writer.writerow(
            {
                "edition": "10e",
                "mode": "ranged",
                "attacker_id": "attacker-id",
                "defender_id": "defender-id",
                "winner_label": "defender",
            }
        )

    model = train_from_csv(features, tmp_path / "model.json", validation_fraction=0, seed=1, label_overrides_path=labels)

    assert model["label_overrides"]["source"]["rows"] == 1
    assert model["label_overrides"]["summary"]["matched_rows"] == 1
    assert model["label_overrides"]["summary"]["key_columns"] == ["edition", "mode", "attacker_id", "defender_id"]
    assert model["label_source"] == ""


def test_train_logistic_regression_model_predicts_labels():
    pytest.importorskip("sklearn")
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("attacker", outgoing_damage=6, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
        _row("defender", outgoing_damage=1, incoming_damage=6),
    ]

    model = train_logistic_regression_model(rows, validation_fraction=0, feature_columns=DEFAULT_FEATURE_COLUMNS)

    assert model["model_type"] == "logistic_regression_classifier"
    assert model["labels"] == ["attacker", "defender"]
    prediction = predict_row(model, _row("attacker", outgoing_damage=7, incoming_damage=1))
    assert prediction["label"] == "attacker"
    assert prediction["confidence"] > 0.5
    assert set(prediction["probabilities"]) == {"attacker", "defender"}


def test_train_from_csv_can_write_logistic_regression_model(tmp_path):
    pytest.importorskip("sklearn")
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("attacker", outgoing_damage=6, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
        _row("defender", outgoing_damage=1, incoming_damage=6),
    ]
    features = tmp_path / "features.csv"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["edition", "mode", "label_source", "winner_label", "attacker_id", "defender_id", *DEFAULT_FEATURE_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)

    output = tmp_path / "model.json"
    loaded = train_from_csv(
        features,
        output,
        validation_fraction=0,
        seed=1,
        model_type="logistic_regression",
    )

    assert loaded["model_type"] == "logistic_regression_classifier"
    assert load_model(output)["model_type"] == "logistic_regression_classifier"


def test_missing_feature_columns_reports_schema_gaps():
    rows = [{"winner_label": "attacker", "attacker_points": 100}]

    missing = missing_feature_columns(rows, ["attacker_points", "defender_points"])

    assert missing == ["defender_points"]


def test_train_centroid_model_rejects_rows_missing_requested_feature_columns():
    rows = [
        {"winner_label": "attacker", "label_source": "deterministic_calculator", "attacker_points": 100},
        {"winner_label": "defender", "label_source": "deterministic_calculator", "attacker_points": 50},
    ]

    with pytest.raises(ValueError, match="missing required columns"):
        train_centroid_model(rows, validation_fraction=0, feature_set="pre_match")


def test_feature_csv_provenance_records_path_hash_and_row_count(tmp_path):
    path = tmp_path / "features.csv"
    path.write_text("winner_label,attacker_points\nattacker,100\n", encoding="utf-8")

    provenance = feature_csv_provenance(path)

    assert provenance["path"] == str(path)
    assert provenance["bytes"] == path.stat().st_size
    assert len(provenance["sha256"]) == 64
    assert provenance["rows"] == 1
