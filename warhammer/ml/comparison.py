from __future__ import annotations

from typing import Any, Iterable, Sequence

from .model import MODEL_TYPES, train_model


def compare_model_types(
    rows: Iterable[dict[str, Any]],
    *,
    model_types: Sequence[str],
    validation_fraction: float = 0.2,
    seed: int = 40,
    feature_set: str = "pre_match",
) -> list[dict[str, Any]]:
    """Train candidate advisory models in memory and return comparable metrics."""

    feature_rows = list(rows)
    results = []
    for model_type in model_types:
        try:
            model = train_model(
                feature_rows,
                validation_fraction=validation_fraction,
                seed=seed,
                feature_set=feature_set,
                model_type=model_type,
            )
        except ValueError as exc:
            results.append(
                {
                    "requested_model_type": model_type,
                    "model_type": _model_type_name(model_type),
                    "ok": False,
                    "error": str(exc),
                    "feature_set": feature_set,
                    "training_rows": 0,
                    "validation_rows": 0,
                    "validation_accuracy": None,
                    "validation_correct": 0,
                    "validation_total": 0,
                }
            )
            continue
        validation = model.get("validation") if isinstance(model.get("validation"), dict) else {}
        results.append(
            {
                "requested_model_type": model_type,
                "model_type": model.get("model_type", _model_type_name(model_type)),
                "ok": True,
                "error": "",
                "feature_set": model.get("feature_set", feature_set),
                "training_rows": model.get("training_rows", 0),
                "validation_rows": model.get("validation_rows", 0),
                "validation_accuracy": validation.get("accuracy"),
                "validation_correct": validation.get("correct", 0),
                "validation_total": validation.get("total", 0),
                "labels": model.get("labels", []),
            }
        )
    return sorted(results, key=_sort_key)


def render_comparison_report(results: Sequence[dict[str, Any]]) -> str:
    lines = [
        "# ML Model Comparison",
        "",
        "| Requested | Model | Status | Feature set | Training rows | Validation rows | Accuracy | Correct |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        accuracy = _accuracy_text(row.get("validation_accuracy"))
        status = "ok" if row.get("ok") else f"error: {row.get('error', '')}"
        lines.append(
            "| "
            f"`{row.get('requested_model_type', '')}` | "
            f"`{row.get('model_type', '')}` | "
            f"{status} | "
            f"`{row.get('feature_set', '')}` | "
            f"{_int_text(row.get('training_rows'))} | "
            f"{_int_text(row.get('validation_rows'))} | "
            f"{accuracy} | "
            f"{_int_text(row.get('validation_correct'))}/{_int_text(row.get('validation_total'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    accuracy = row.get("validation_accuracy")
    numeric_accuracy = float(accuracy) if isinstance(accuracy, (int, float)) else -1.0
    return (0 if row.get("ok") else 1, -numeric_accuracy, str(row.get("requested_model_type", "")))


def _model_type_name(model_type: str) -> str:
    key = str(model_type or "").strip().lower().replace("-", "_")
    return MODEL_TYPES.get(key, key or "unknown")


def _accuracy_text(value: object) -> str:
    if value is None or value == "":
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "n/a"


def _int_text(value: object) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"
