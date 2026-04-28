from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable, Sequence


DEFAULT_FEATURE_COLUMNS = [
    "attacker_points",
    "attacker_models",
    "attacker_toughness",
    "attacker_save",
    "attacker_invulnerable_save",
    "attacker_wounds",
    "attacker_keywords_count",
    "attacker_weapon_count",
    "attacker_mode_weapon_count",
    "attacker_points_per_model",
    "attacker_mode_avg_attacks",
    "attacker_mode_max_attacks",
    "attacker_mode_avg_skill",
    "attacker_mode_avg_strength",
    "attacker_mode_max_strength",
    "attacker_mode_avg_ap",
    "attacker_mode_best_ap",
    "attacker_mode_avg_damage",
    "attacker_mode_max_damage",
    "attacker_mode_keyword_count",
    "attacker_mode_special_rule_count",
    "defender_points",
    "defender_models",
    "defender_toughness",
    "defender_save",
    "defender_invulnerable_save",
    "defender_wounds",
    "defender_keywords_count",
    "defender_weapon_count",
    "defender_mode_weapon_count",
    "defender_points_per_model",
    "defender_mode_avg_attacks",
    "defender_mode_max_attacks",
    "defender_mode_avg_skill",
    "defender_mode_avg_strength",
    "defender_mode_max_strength",
    "defender_mode_avg_ap",
    "defender_mode_best_ap",
    "defender_mode_avg_damage",
    "defender_mode_max_damage",
    "defender_mode_keyword_count",
    "defender_mode_special_rule_count",
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
]

CALCULATOR_OUTPUT_FEATURE_COLUMNS = [
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
]

PRE_MATCH_FEATURE_COLUMNS = [
    column for column in DEFAULT_FEATURE_COLUMNS if column not in set(CALCULATOR_OUTPUT_FEATURE_COLUMNS)
]

FEATURE_COLUMN_SETS = {
    "full": DEFAULT_FEATURE_COLUMNS,
    "pre_match": PRE_MATCH_FEATURE_COLUMNS,
}

MODEL_TYPES = {
    "centroid": "nearest_centroid_classifier",
    "nearest_centroid": "nearest_centroid_classifier",
    "logistic_regression": "logistic_regression_classifier",
}

DEFAULT_LABEL_KEY_COLUMNS = ["edition", "mode", "attacker_id", "defender_id"]


def read_feature_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_label_override_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def apply_label_overrides(
    feature_rows: Iterable[dict[str, Any]],
    label_rows: Iterable[dict[str, Any]],
    *,
    key_columns: Sequence[str] = DEFAULT_LABEL_KEY_COLUMNS,
    label_column: str = "winner_label",
    override_label_column: str | None = None,
    label_source: str = "external_labels",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [dict(row) for row in feature_rows]
    overrides: dict[tuple[str, ...], str] = {}
    duplicate_keys = 0
    skipped_rows = 0
    source_column = "label_source"
    override_label_column = override_label_column or label_column

    for label_row in label_rows:
        key = _label_key(label_row, key_columns)
        label = str(label_row.get(override_label_column) or label_row.get("label") or "").strip()
        if not all(key) or not label:
            skipped_rows += 1
            continue
        if key in overrides:
            duplicate_keys += 1
        overrides[key] = label

    matched_rows = 0
    for row in rows:
        key = _label_key(row, key_columns)
        if key in overrides:
            row[label_column] = overrides[key]
            row[source_column] = label_source
            matched_rows += 1

    return rows, {
        "key_columns": list(key_columns),
        "label_column": label_column,
        "override_label_column": override_label_column,
        "label_source": label_source,
        "override_rows": len(overrides),
        "matched_rows": matched_rows,
        "skipped_rows": skipped_rows,
        "duplicate_keys": duplicate_keys,
    }


def feature_columns_for_set(name: str) -> list[str]:
    try:
        return list(FEATURE_COLUMN_SETS[name])
    except KeyError as exc:
        choices = ", ".join(sorted(FEATURE_COLUMN_SETS))
        raise ValueError(f"Unknown feature set {name!r}; expected one of: {choices}") from exc


def missing_feature_columns(rows: Iterable[dict[str, Any]], feature_columns: Sequence[str]) -> list[str]:
    available: set[str] = set()
    for row in rows:
        available.update(str(key) for key in row)
    return [column for column in feature_columns if column not in available]


def train_from_csv(
    input_path: Path,
    output_path: Path,
    *,
    validation_fraction: float = 0.2,
    seed: int = 40,
    feature_columns: Sequence[str] | None = None,
    feature_set: str = "full",
    label_column: str = "winner_label",
    model_type: str = "centroid",
    label_overrides_path: Path | None = None,
    label_key_columns: Sequence[str] = DEFAULT_LABEL_KEY_COLUMNS,
) -> dict[str, Any]:
    input_path = Path(input_path)
    rows = read_feature_csv(input_path)
    label_override_summary = None
    if label_overrides_path is not None:
        label_rows = read_label_override_csv(Path(label_overrides_path))
        rows, label_override_summary = apply_label_overrides(
            rows,
            label_rows,
            key_columns=label_key_columns,
            label_column=label_column,
        )
    model = train_model(
        rows,
        validation_fraction=validation_fraction,
        seed=seed,
        feature_columns=feature_columns,
        feature_set=feature_set,
        label_column=label_column,
        model_type=model_type,
    )
    model["training_source"] = feature_csv_provenance(input_path, rows=rows)
    if label_overrides_path is not None:
        model["label_overrides"] = {
            "source": feature_csv_provenance(Path(label_overrides_path), rows=read_label_override_csv(Path(label_overrides_path))),
            "summary": label_override_summary,
        }
    write_model(model, output_path)
    return model


def feature_csv_provenance(path: Path, *, rows: Sequence[dict[str, Any]] | None = None) -> dict[str, Any]:
    path = Path(path)
    return {
        "path": str(path),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": _sha256(path) if path.exists() else "",
        "rows": len(rows) if rows is not None else _csv_data_row_count(path),
    }


def train_model(
    rows: Iterable[dict[str, Any]],
    *,
    validation_fraction: float = 0.2,
    seed: int = 40,
    feature_columns: Sequence[str] | None = None,
    feature_set: str = "full",
    label_column: str = "winner_label",
    model_type: str = "centroid",
) -> dict[str, Any]:
    normalized_type = _normalize_model_type(model_type)
    if normalized_type == "nearest_centroid_classifier":
        return train_centroid_model(
            rows,
            validation_fraction=validation_fraction,
            seed=seed,
            feature_columns=feature_columns,
            feature_set=feature_set,
            label_column=label_column,
        )
    if normalized_type == "logistic_regression_classifier":
        return train_logistic_regression_model(
            rows,
            validation_fraction=validation_fraction,
            seed=seed,
            feature_columns=feature_columns,
            feature_set=feature_set,
            label_column=label_column,
        )
    raise ValueError(f"Unsupported model type {model_type!r}")


def train_centroid_model(
    rows: Iterable[dict[str, Any]],
    *,
    validation_fraction: float = 0.2,
    seed: int = 40,
    feature_columns: Sequence[str] | None = None,
    feature_set: str = "full",
    label_column: str = "winner_label",
) -> dict[str, Any]:
    prepared = _prepare_training_rows(
        rows,
        validation_fraction=validation_fraction,
        seed=seed,
        feature_columns=feature_columns,
        feature_set=feature_set,
        label_column=label_column,
    )
    feature_columns = prepared["feature_columns"]
    usable_rows = prepared["usable_rows"]
    training_rows = prepared["training_rows"]
    validation_rows = prepared["validation_rows"]
    stats = _feature_stats(training_rows, feature_columns)
    centroids, class_counts = _class_centroids(training_rows, feature_columns, label_column, stats)
    model = {
        "model_type": "nearest_centroid_classifier",
        "feature_set": feature_set,
        "label_source": _common_value(usable_rows, "label_source"),
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "feature_columns": list(feature_columns),
        "label_column": label_column,
        "labels": sorted(centroids),
        "class_counts": class_counts,
        "feature_stats": stats,
        "centroids": centroids,
        "training_rows": len(training_rows),
        "validation_rows": len(validation_rows),
        "validation": evaluate_model(
            {
                "feature_columns": list(feature_columns),
                "feature_stats": stats,
                "centroids": centroids,
                "label_column": label_column,
            },
            validation_rows,
        ),
    }
    return model


def train_logistic_regression_model(
    rows: Iterable[dict[str, Any]],
    *,
    validation_fraction: float = 0.2,
    seed: int = 40,
    feature_columns: Sequence[str] | None = None,
    feature_set: str = "full",
    label_column: str = "winner_label",
) -> dict[str, Any]:
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise ValueError(
            "The logistic_regression model type requires scikit-learn. "
            "Install scikit-learn or use --model-type centroid."
        ) from exc

    prepared = _prepare_training_rows(
        rows,
        validation_fraction=validation_fraction,
        seed=seed,
        feature_columns=feature_columns,
        feature_set=feature_set,
        label_column=label_column,
    )
    feature_columns = prepared["feature_columns"]
    usable_rows = prepared["usable_rows"]
    training_rows = prepared["training_rows"]
    validation_rows = prepared["validation_rows"]
    labels = sorted({str(row.get(label_column) or "").strip() for row in training_rows if str(row.get(label_column) or "").strip()})
    if len(labels) < 2:
        raise ValueError("Logistic regression requires at least two labelled classes")

    stats = _feature_stats(training_rows, feature_columns)
    x_train = [_normalised_values(row, feature_columns, stats) for row in training_rows]
    y_train = [str(row.get(label_column) or "").strip() for row in training_rows]
    classifier = LogisticRegression(max_iter=1000, random_state=seed)
    classifier.fit(x_train, y_train)
    class_counts = _class_counts(training_rows, label_column)
    model = {
        "model_type": "logistic_regression_classifier",
        "feature_set": feature_set,
        "label_source": _common_value(usable_rows, "label_source"),
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "feature_columns": list(feature_columns),
        "label_column": label_column,
        "labels": [str(label) for label in classifier.classes_],
        "class_counts": class_counts,
        "feature_stats": stats,
        "coefficients": classifier.coef_.tolist(),
        "intercepts": classifier.intercept_.tolist(),
        "training_rows": len(training_rows),
        "validation_rows": len(validation_rows),
        "validation": evaluate_model(
            {
                "model_type": "logistic_regression_classifier",
                "feature_columns": list(feature_columns),
                "feature_stats": stats,
                "labels": [str(label) for label in classifier.classes_],
                "coefficients": classifier.coef_.tolist(),
                "intercepts": classifier.intercept_.tolist(),
                "label_column": label_column,
            },
            validation_rows,
        ),
    }
    return model


def predict_row(model: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    feature_columns = list(model["feature_columns"])
    stats = model["feature_stats"]
    values = _normalised_values(row, feature_columns, stats)
    if model.get("model_type") == "logistic_regression_classifier":
        probabilities = _logistic_probabilities(model, values)
        label, confidence = max(probabilities.items(), key=lambda item: item[1])
        return {
            "label": label,
            "confidence": confidence,
            "probabilities": probabilities,
        }
    distances = {
        label: _distance(values, centroid)
        for label, centroid in model["centroids"].items()
    }
    label, distance = min(distances.items(), key=lambda item: item[1])
    ordered_distances = sorted(distances.values())
    confidence = 1.0
    if len(ordered_distances) >= 2 and ordered_distances[1] > 0:
        confidence = max(0.0, min(1.0, (ordered_distances[1] - ordered_distances[0]) / ordered_distances[1]))
    return {
        "label": label,
        "confidence": confidence,
        "distance": distance,
        "distances": distances,
    }


def evaluate_model(model: dict[str, Any], rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    label_column = model.get("label_column", "winner_label")
    total = 0
    correct = 0
    confusion: dict[str, dict[str, int]] = {}
    for row in rows:
        expected = str(row.get(label_column) or "").strip()
        if not expected:
            continue
        predicted = str(predict_row(model, row)["label"])
        confusion.setdefault(expected, {})
        confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1
        total += 1
        if predicted == expected:
            correct += 1
    return {
        "accuracy": correct / total if total else None,
        "correct": correct,
        "total": total,
        "confusion": confusion,
    }


def write_model(model: dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2), encoding="utf-8")


def load_model(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_data_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _label_key(row: dict[str, Any], key_columns: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(row.get(column) or "").strip().lower() for column in key_columns)


def _validation_count(row_count: int, validation_fraction: float) -> int:
    if row_count < 2 or validation_fraction <= 0:
        return 0
    return max(1, int(round(row_count * validation_fraction)))


def _prepare_training_rows(
    rows: Iterable[dict[str, Any]],
    *,
    validation_fraction: float,
    seed: int,
    feature_columns: Sequence[str] | None,
    feature_set: str,
    label_column: str,
) -> dict[str, Any]:
    selected_columns = list(feature_columns) if feature_columns is not None else feature_columns_for_set(feature_set)
    usable_rows = [row for row in rows if str(row.get(label_column) or "").strip()]
    if not usable_rows:
        raise ValueError("No labelled feature rows were provided")
    missing_columns = missing_feature_columns(usable_rows, selected_columns)
    if missing_columns:
        preview = ", ".join(missing_columns[:8])
        suffix = "" if len(missing_columns) <= 8 else f", ... ({len(missing_columns)} total)"
        raise ValueError(
            f"Feature rows are missing required columns for feature set {feature_set!r}: {preview}{suffix}. "
            "Regenerate the feature CSV with export_ml_features.py."
        )

    shuffled = list(usable_rows)
    random.Random(seed).shuffle(shuffled)
    validation_fraction = max(0.0, min(0.8, float(validation_fraction)))
    validation_count = _validation_count(len(shuffled), validation_fraction)
    validation_rows = shuffled[:validation_count]
    training_rows = shuffled[validation_count:] or shuffled
    if validation_fraction > 0 and not validation_rows and len(shuffled) > 1:
        validation_rows = shuffled[-1:]
        training_rows = shuffled[:-1]
    return {
        "feature_columns": selected_columns,
        "usable_rows": usable_rows,
        "training_rows": training_rows,
        "validation_rows": validation_rows,
    }


def _feature_stats(rows: Sequence[dict[str, Any]], feature_columns: Sequence[str]) -> dict[str, dict[str, float]]:
    stats = {}
    for column in feature_columns:
        values = [_number(row.get(column)) for row in rows]
        mean = sum(values) / len(values) if values else 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
        std = math.sqrt(variance) or 1.0
        stats[column] = {"mean": mean, "std": std}
    return stats


def _class_centroids(
    rows: Sequence[dict[str, Any]],
    feature_columns: Sequence[str],
    label_column: str,
    stats: dict[str, dict[str, float]],
) -> tuple[dict[str, list[float]], dict[str, int]]:
    totals: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(label_column) or "").strip()
        if not label:
            continue
        values = _normalised_values(row, feature_columns, stats)
        totals.setdefault(label, [0.0 for _ in feature_columns])
        counts[label] = counts.get(label, 0) + 1
        for index, value in enumerate(values):
            totals[label][index] += value
    centroids = {
        label: [value / counts[label] for value in values]
        for label, values in totals.items()
        if counts.get(label)
    }
    return centroids, counts


def _class_counts(rows: Sequence[dict[str, Any]], label_column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(label_column) or "").strip()
        if label:
            counts[label] = counts.get(label, 0) + 1
    return counts


def _normalised_values(
    row: dict[str, Any],
    feature_columns: Sequence[str],
    stats: dict[str, dict[str, float]],
) -> list[float]:
    values = []
    for column in feature_columns:
        raw = _number(row.get(column))
        column_stats = stats[column]
        values.append((raw - column_stats["mean"]) / (column_stats["std"] or 1.0))
    return values


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _logistic_probabilities(model: dict[str, Any], values: Sequence[float]) -> dict[str, float]:
    labels = [str(label) for label in model.get("labels", [])]
    coefficients = model.get("coefficients", [])
    intercepts = model.get("intercepts", [])
    if len(labels) == 2 and len(coefficients) == 1:
        logit = _linear_score(values, coefficients[0], _number(intercepts[0] if intercepts else 0))
        positive = 1.0 / (1.0 + math.exp(-_clip_logit(logit)))
        return {labels[0]: 1.0 - positive, labels[1]: positive}
    scores = [
        _linear_score(values, coefficients[index], _number(intercepts[index] if index < len(intercepts) else 0))
        for index in range(len(labels))
    ]
    return dict(zip(labels, _softmax(scores), strict=False))


def _linear_score(values: Sequence[float], coefficients: Sequence[float], intercept: float) -> float:
    return sum(value * float(coefficient) for value, coefficient in zip(values, coefficients)) + intercept


def _softmax(scores: Sequence[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    exponents = [math.exp(_clip_logit(score - max_score)) for score in scores]
    total = sum(exponents) or 1.0
    return [value / total for value in exponents]


def _clip_logit(value: float) -> float:
    return max(-60.0, min(60.0, float(value)))


def _number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _common_value(rows: Sequence[dict[str, Any]], column: str) -> str:
    values = {str(row.get(column) or "").strip() for row in rows}
    values.discard("")
    return next(iter(values)) if len(values) == 1 else ""


def _normalize_model_type(model_type: str) -> str:
    key = str(model_type or "centroid").strip().lower().replace("-", "_")
    try:
        return MODEL_TYPES[key]
    except KeyError as exc:
        choices = ", ".join(sorted(MODEL_TYPES))
        raise ValueError(f"Unknown model type {model_type!r}; expected one of: {choices}") from exc
