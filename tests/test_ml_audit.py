from warhammer.ml.audit import CALCULATOR_OUTPUT_FEATURES, render_model_audit_report, write_model_audit_report


def _model():
    return {
        "model_type": "nearest_centroid_classifier",
        "feature_set": "full",
        "label_source": "deterministic_calculator",
        "created_at": "2026-04-25T12:00:00Z",
        "training_source": {"rows": 3, "sha256": "abc123", "bytes": 123, "path": "features.csv"},
        "feature_columns": ["attacker_points", "outgoing_damage", "damage_delta"],
        "label_column": "winner_label",
        "labels": ["attacker", "defender"],
        "class_counts": {"attacker": 3, "defender": 1},
        "training_rows": 4,
        "validation_rows": 2,
        "validation": {
            "accuracy": 0.5,
            "correct": 1,
            "total": 2,
            "confusion": {"attacker": {"attacker": 1}, "defender": {"attacker": 1}},
        },
    }


def test_render_model_audit_report_flags_synthetic_labels_and_calculator_features():
    rows = [
        {"winner_label": "attacker", "attacker_points": 1, "outgoing_damage": 2, "damage_delta": 1},
        {"winner_label": "attacker", "attacker_points": 1, "outgoing_damage": 2, "damage_delta": 1},
        {"winner_label": "defender", "attacker_points": 1, "outgoing_damage": 2, "damage_delta": 1},
    ]

    report = render_model_audit_report(_model(), feature_rows=rows)

    assert "Labels are generated from deterministic calculator outputs" in report
    assert "Confidence basis: distance-based" in report
    assert "Nearest-centroid classification is dependency-free" in report
    assert "Centroids: 0" in report
    assert "Feature set: `full`" in report
    assert "Saved feature rows: 3" in report
    assert "Saved feature SHA-256: `abc123`" in report
    assert "Feature CSV completeness: ok" in report
    assert "Calculator output metrics are included as features" in report
    assert "| `attacker` | 2 | 66.7% |" in report
    assert "| `defender` | 1 | 33.3% |" in report
    assert "| Expected \\ Predicted | `attacker` | `defender` |" in report
    assert "`outgoing_damage`" in report
    assert "outgoing_damage" in CALCULATOR_OUTPUT_FEATURES


def test_render_model_audit_report_describes_logistic_regression_parameters():
    model = _model()
    model.update(
        {
            "model_type": "logistic_regression_classifier",
            "coefficients": [[0.1, -0.2, 0.3], [-0.1, 0.2, -0.3]],
            "intercepts": [0.0, 0.1],
        }
    )

    report = render_model_audit_report(model)

    assert "Confidence basis: probability-based" in report
    assert "scikit-learn is only needed for training" in report
    assert "Coefficient rows: 2" in report
    assert "Coefficients per row: 3" in report
    assert "Intercepts: 2" in report


def test_write_model_audit_report_creates_parent_directory(tmp_path):
    output = tmp_path / "reports" / "model.md"

    write_model_audit_report(_model(), output)

    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("# ML Model Audit")


def test_render_model_audit_report_flags_missing_feature_columns():
    report = render_model_audit_report(_model(), feature_rows=[{"winner_label": "attacker", "attacker_points": 1}])

    assert "Feature CSV completeness: missing" in report
    assert "regenerate it before retraining" in report
