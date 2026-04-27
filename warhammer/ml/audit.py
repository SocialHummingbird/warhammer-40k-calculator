from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from .model import missing_feature_columns


CALCULATOR_OUTPUT_FEATURES = {
    "outgoing_damage",
    "outgoing_unsaved_wounds",
    "outgoing_models_destroyed",
    "outgoing_points_removed",
    "incoming_damage",
    "incoming_unsaved_wounds",
    "incoming_models_destroyed",
    "incoming_points_removed",
    "damage_delta",
    "points_removed_delta",
}


def render_model_audit_report(
    model: dict[str, Any],
    *,
    feature_rows: Iterable[dict[str, Any]] | None = None,
    model_path: Path | None = None,
    feature_path: Path | None = None,
) -> str:
    """Render a compact Markdown audit report for an advisory model."""

    rows = list(feature_rows or [])
    label_column = str(model.get("label_column") or "winner_label")
    labels = [str(label) for label in model.get("labels", [])]
    validation = model.get("validation") if isinstance(model.get("validation"), dict) else {}
    training_source = model.get("training_source") if isinstance(model.get("training_source"), dict) else {}
    feature_columns = [str(column) for column in model.get("feature_columns", [])]
    calculator_features = [column for column in feature_columns if column in CALCULATOR_OUTPUT_FEATURES]
    missing_columns = missing_feature_columns(rows, feature_columns) if rows else []

    lines = [
        "# ML Model Audit",
        "",
        "## Summary",
        f"- Model: `{model.get('model_type', 'unknown')}`",
        f"- Confidence basis: {_confidence_basis(model)}",
        f"- Feature set: `{model.get('feature_set', '') or 'custom'}`",
        f"- Model file: `{model_path}`" if model_path else "- Model file: not specified",
        f"- Feature file: `{feature_path}`" if feature_path else "- Feature file: not specified",
        f"- Saved feature rows: {_int_text(training_source.get('rows'))}",
        f"- Saved feature SHA-256: `{training_source.get('sha256') or 'unknown'}`",
        f"- Created at: `{model.get('created_at', '') or 'unknown'}`",
        f"- Label source: `{model.get('label_source', '') or 'unknown'}`",
        f"- Labels: {', '.join(f'`{label}`' for label in labels) or 'none'}",
        f"- Training rows: {_int_text(model.get('training_rows'))}",
        f"- Validation rows: {_int_text(model.get('validation_rows'))}",
        f"- Validation accuracy: {_accuracy_text(validation.get('accuracy'))}",
        f"- Feature CSV completeness: {_feature_completeness_text(missing_columns, bool(rows))}",
        "",
        "## Interpretation",
        "- This is an advisory model, not the rules engine.",
        "- Labels are generated from deterministic calculator outputs, not real tabletop results.",
        "- Validation accuracy measures agreement with the calculator-derived labels.",
        *_model_interpretation_lines(model),
    ]
    if calculator_features:
        lines.append(
            "- Calculator output metrics are included as features, so this baseline should not be treated as an independent predictor."
        )
    if missing_columns:
        lines.append("- The supplied feature CSV is missing model feature columns; regenerate it before retraining.")

    lines.extend(["", "## Class Balance"])
    if rows:
        lines.extend(_label_count_table("Feature CSV labels", _label_counts(rows, label_column), labels))
    lines.extend(_label_count_table("Training labels", _mapping_counts(model.get("class_counts")), labels))

    lines.extend(["", "## Validation Confusion Matrix"])
    lines.extend(_confusion_table(validation.get("confusion"), labels))

    lines.extend(["", "## Model Parameters"])
    lines.extend(_parameter_summary(model))

    lines.extend(["", "## Feature Columns", f"- Total columns: {len(feature_columns)}"])
    if calculator_features:
        lines.append(f"- Calculator output columns: {', '.join(f'`{column}`' for column in calculator_features)}")
    else:
        lines.append("- Calculator output columns: none")
    lines.append("")
    lines.extend(f"- `{column}`" for column in feature_columns)
    lines.append("")
    return "\n".join(lines)


def write_model_audit_report(
    model: dict[str, Any],
    path: Path,
    *,
    feature_rows: Iterable[dict[str, Any]] | None = None,
    model_path: Path | None = None,
    feature_path: Path | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_model_audit_report(
            model,
            feature_rows=feature_rows,
            model_path=model_path,
            feature_path=feature_path,
        ),
        encoding="utf-8",
    )


def _label_counts(rows: Sequence[dict[str, Any]], label_column: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        label = str(row.get(label_column) or "").strip()
        if label:
            counts[label] += 1
    return dict(counts)


def _mapping_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts = {}
    for key, raw in value.items():
        try:
            counts[str(key)] = int(raw)
        except (TypeError, ValueError):
            counts[str(key)] = 0
    return counts


def _label_count_table(title: str, counts: dict[str, int], labels: Sequence[str]) -> list[str]:
    ordered_labels = list(labels)
    for label in sorted(counts):
        if label not in ordered_labels:
            ordered_labels.append(label)
    total = sum(counts.values())
    lines = [
        f"### {title}",
        "",
        "| Label | Rows | Share |",
        "| --- | ---: | ---: |",
    ]
    if not ordered_labels:
        lines.append("| none | 0 | n/a |")
    for label in ordered_labels:
        count = counts.get(label, 0)
        share = "n/a" if not total else f"{count / total:.1%}"
        lines.append(f"| `{label}` | {count} | {share} |")
    lines.append(f"| **Total** | **{total}** | **100.0%** |" if total else "| **Total** | **0** | **n/a** |")
    return lines


def _confusion_table(value: object, labels: Sequence[str]) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["No validation confusion matrix is available."]
    expected_labels = list(labels)
    for label in sorted(str(key) for key in value):
        if label not in expected_labels:
            expected_labels.append(label)
    predicted_labels = list(expected_labels)
    for row in value.values():
        if isinstance(row, dict):
            for label in sorted(str(key) for key in row):
                if label not in predicted_labels:
                    predicted_labels.append(label)

    header = "| Expected \\ Predicted | " + " | ".join(f"`{label}`" for label in predicted_labels) + " |"
    separator = "| --- |" + "|".join(" ---: " for _ in predicted_labels) + "|"
    lines = [header, separator]
    for expected in expected_labels:
        row = value.get(expected, {}) if isinstance(value.get(expected), dict) else {}
        cells = [str(int(row.get(predicted, 0) or 0)) for predicted in predicted_labels]
        lines.append(f"| `{expected}` | " + " | ".join(cells) + " |")
    return lines


def _accuracy_text(value: object) -> str:
    if value is None or value == "":
        return "n/a"


def _confidence_basis(model: dict[str, Any]) -> str:
    model_type = str(model.get("model_type") or "")
    if model_type == "logistic_regression_classifier":
        return "probability-based"
    if model_type == "nearest_centroid_classifier":
        return "distance-based"
    return "unknown"


def _model_interpretation_lines(model: dict[str, Any]) -> list[str]:
    model_type = str(model.get("model_type") or "")
    if model_type == "logistic_regression_classifier":
        return [
            "- Logistic regression stores coefficients and intercepts in JSON; scikit-learn is only needed for training, not for prediction.",
            "- Confidence is the predicted class probability from the saved linear model.",
        ]
    if model_type == "nearest_centroid_classifier":
        return [
            "- Nearest-centroid classification is dependency-free and compares each matchup to saved class centroids.",
            "- Confidence is based on the gap between the nearest and next-nearest class distance.",
        ]
    return ["- Model family is not recognised by the audit renderer."]


def _parameter_summary(model: dict[str, Any]) -> list[str]:
    model_type = str(model.get("model_type") or "")
    if model_type == "logistic_regression_classifier":
        coefficients = model.get("coefficients")
        intercepts = model.get("intercepts")
        coefficient_rows = len(coefficients) if isinstance(coefficients, list) else 0
        coefficient_columns = len(coefficients[0]) if coefficient_rows and isinstance(coefficients[0], list) else 0
        intercept_count = len(intercepts) if isinstance(intercepts, list) else 0
        return [
            f"- Coefficient rows: {coefficient_rows}",
            f"- Coefficients per row: {coefficient_columns}",
            f"- Intercepts: {intercept_count}",
        ]
    if model_type == "nearest_centroid_classifier":
        centroids = model.get("centroids")
        centroid_count = len(centroids) if isinstance(centroids, dict) else 0
        centroid_width = 0
        if isinstance(centroids, dict) and centroids:
            first = next(iter(centroids.values()))
            centroid_width = len(first) if isinstance(first, list) else 0
        return [
            f"- Centroids: {centroid_count}",
            f"- Features per centroid: {centroid_width}",
        ]
    return ["- No recognised parameter summary is available."]
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "n/a"


def _int_text(value: object) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"


def _feature_completeness_text(missing_columns: Sequence[str], rows_supplied: bool) -> str:
    if not rows_supplied:
        return "not checked"
    if not missing_columns:
        return "ok"
    preview = ", ".join(missing_columns[:8])
    suffix = "" if len(missing_columns) <= 8 else f", ... ({len(missing_columns)} total)"
    return f"missing {preview}{suffix}"
