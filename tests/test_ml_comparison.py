from warhammer.ml.comparison import compare_model_types, render_comparison_report
from warhammer.ml.model import DEFAULT_FEATURE_COLUMNS


def _row(label, *, outgoing_damage, incoming_damage):
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update(
        {
            "label_source": "deterministic_calculator",
            "winner_label": label,
            "outgoing_damage": outgoing_damage,
            "incoming_damage": incoming_damage,
            "damage_delta": outgoing_damage - incoming_damage,
            "outgoing_points_removed": outgoing_damage,
            "incoming_points_removed": incoming_damage,
            "points_removed_delta": outgoing_damage - incoming_damage,
        }
    )
    return row


def test_compare_model_types_reports_sorted_validation_metrics():
    rows = [
        _row("attacker", outgoing_damage=5, incoming_damage=1),
        _row("attacker", outgoing_damage=6, incoming_damage=1),
        _row("defender", outgoing_damage=1, incoming_damage=5),
        _row("defender", outgoing_damage=1, incoming_damage=6),
    ]

    results = compare_model_types(
        rows,
        model_types=["centroid"],
        validation_fraction=0,
        feature_set="full",
    )

    assert results == [
        {
            "requested_model_type": "centroid",
            "model_type": "nearest_centroid_classifier",
            "ok": True,
            "error": "",
            "feature_set": "full",
            "training_rows": 4,
            "validation_rows": 0,
            "validation_accuracy": None,
            "validation_correct": 0,
            "validation_total": 0,
            "labels": ["attacker", "defender"],
        }
    ]


def test_compare_model_types_captures_training_errors():
    results = compare_model_types(
        [{"winner_label": "attacker", "attacker_points": 1}],
        model_types=["centroid"],
        validation_fraction=0,
        feature_set="pre_match",
    )

    assert results[0]["ok"] is False
    assert "missing required columns" in results[0]["error"]


def test_render_comparison_report_outputs_markdown_table():
    report = render_comparison_report(
        [
            {
                "requested_model_type": "centroid",
                "model_type": "nearest_centroid_classifier",
                "ok": True,
                "feature_set": "pre_match",
                "training_rows": 8,
                "validation_rows": 2,
                "validation_accuracy": 0.5,
                "validation_correct": 1,
                "validation_total": 2,
            }
        ]
    )

    assert report.startswith("# ML Model Comparison")
    assert "`nearest_centroid_classifier`" in report
    assert "0.500" in report
