from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .features import matchup_feature_row_from_result
from .model import load_model, predict_row
from ..profiles import UnitProfile


def load_advisory_model(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if not path:
        return None
    path = Path(path)
    if not path.exists():
        return None
    return load_model(path)


def model_status(model: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not model:
        return {"available": False}
    validation = model.get("validation") if isinstance(model.get("validation"), dict) else {}
    training_source = _training_source(model)
    return {
        "available": True,
        "model_type": model.get("model_type", "unknown"),
        "feature_set": model.get("feature_set", "custom"),
        "label_source": model.get("label_source", ""),
        "labels": model.get("labels", []),
        "training_rows": model.get("training_rows", 0),
        "validation_rows": model.get("validation_rows", 0),
        "validation_accuracy": validation.get("accuracy"),
        "feature_rows": training_source.get("rows", 0),
        "feature_sha256": training_source.get("sha256", ""),
        "feature_sha256_short": _short_hash(training_source.get("sha256", "")),
    }


def ml_judgement_from_result(
    model: Optional[dict[str, Any]],
    *,
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    result: dict[str, Any],
    edition: str = "10e",
) -> Optional[dict[str, Any]]:
    if not model:
        return None
    feature_row = matchup_feature_row_from_result(attacker, defender, mode, result, edition=edition)
    prediction = predict_row(model, feature_row)
    label = str(prediction["label"])
    confidence = float(prediction["confidence"])
    winner = _winner_name(label, attacker=attacker, defender=defender)
    training_source = _training_source(model)
    return {
        "available": True,
        "title": _title(label, winner, confidence),
        "body": _body(label, winner, confidence, model),
        "winner_label": label,
        "winner": winner or "",
        "confidence": confidence,
        "model_type": model.get("model_type", "unknown"),
        "feature_set": model.get("feature_set", "custom"),
        "label_source": model.get("label_source", ""),
        "training_rows": model.get("training_rows", 0),
        "feature_rows": training_source.get("rows", 0),
        "feature_sha256_short": _short_hash(training_source.get("sha256", "")),
        "validation_accuracy": (model.get("validation") or {}).get("accuracy"),
    }


def _winner_name(label: str, *, attacker: UnitProfile, defender: UnitProfile) -> str:
    if label == "attacker":
        return attacker.name
    if label == "defender":
        return defender.name
    return ""


def _title(label: str, winner: str, confidence: float) -> str:
    if label == "close" or not winner:
        return f"ML advisory: close matchup ({confidence:.0%})"
    return f"ML advisory: {winner} ({confidence:.0%})"


def _body(label: str, winner: str, confidence: float, model: dict[str, Any]) -> str:
    accuracy = (model.get("validation") or {}).get("accuracy")
    accuracy_text = "unknown validation accuracy" if accuracy is None else f"{float(accuracy):.0%} validation accuracy"
    confidence_basis = "probability-based" if model.get("model_type") == "logistic_regression_classifier" else "distance-based"
    if label == "close" or not winner:
        outcome = "The advisory model classifies this as close."
    else:
        outcome = f"The advisory model classifies {winner} as favoured."
    return (
        f"{outcome} Confidence is {confidence_basis} at {confidence:.0%}; model has {accuracy_text}. "
        "Use this as an advisory signal only, not a rules result."
    )


def _training_source(model: dict[str, Any]) -> dict[str, Any]:
    source = model.get("training_source")
    return source if isinstance(source, dict) else {}


def _short_hash(value: object) -> str:
    text = str(value or "")
    return text[:12] if text else ""
