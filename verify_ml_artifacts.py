#!/usr/bin/env python3
"""Verify ML feature/model artifacts agree with saved provenance."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from warhammer.ml.model import feature_csv_provenance, load_model


DEFAULT_FEATURES = Path("data/ml/10e/matchup_training_rows.csv")
DEFAULT_MODEL = Path("models/10e/matchup_centroid_model.json")


def verify_ml_artifacts(feature_path: Path, model_path: Path) -> dict[str, Any]:
    feature_path = Path(feature_path)
    model_path = Path(model_path)
    results = []

    if not feature_path.exists():
        results.append(_result("feature_csv", "missing", False, path=str(feature_path)))
        provenance = {"path": str(feature_path), "bytes": 0, "sha256": "", "rows": 0}
        fieldnames: list[str] = []
    else:
        provenance = feature_csv_provenance(feature_path)
        fieldnames = _csv_fieldnames(feature_path)
        results.append(_result("feature_csv", "ok", True, **provenance))

    if not model_path.exists():
        results.append(_result("model", "missing", False, path=str(model_path)))
        model: dict[str, Any] = {}
    else:
        model = load_model(model_path)
        results.append(_result("model", "ok", True, path=str(model_path)))

    source = model.get("training_source") if isinstance(model.get("training_source"), dict) else {}
    for key in ("bytes", "sha256", "rows"):
        expected = source.get(key)
        actual = provenance.get(key)
        ok = expected == actual
        results.append(
            _result(
                f"training_source.{key}",
                "ok" if ok else "mismatch",
                ok,
                expected=expected,
                actual=actual,
            )
        )

    feature_columns = [str(column) for column in model.get("feature_columns", [])]
    missing_columns = [column for column in feature_columns if column not in fieldnames]
    results.append(
        _result(
            "feature_columns",
            "ok" if not missing_columns else "missing_columns",
            not missing_columns,
            missing_columns=missing_columns,
            expected_count=len(feature_columns),
            actual_count=len(fieldnames),
        )
    )

    failed = [item for item in results if not item["ok"]]
    return {
        "feature_path": str(feature_path),
        "model_path": str(model_path),
        "ok": not failed,
        "ok_count": len(results) - len(failed),
        "failed_count": len(failed),
        "results": results,
    }


def _csv_fieldnames(path: Path) -> list[str]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def _result(name: str, status: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "ok": ok, **extra}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ML feature CSV and model provenance")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Feature CSV used to train the model")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Model JSON to verify")
    parser.add_argument("--json", action="store_true", help="Print full JSON verification results")
    args = parser.parse_args(argv)

    try:
        report = verify_ml_artifacts(args.features, args.model)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ML verification failed: {exc}")
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Verified {report['ok_count']} of {len(report['results'])} ML artifact checks")
        for item in report["results"]:
            if item["ok"]:
                continue
            print(f"- {item['name']}: {item['status']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
