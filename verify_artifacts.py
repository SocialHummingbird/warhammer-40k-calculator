#!/usr/bin/env python3
"""Verify generated data artifacts against artifact_manifest.json."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from warhammer.ml.model import MODEL_TYPES
from warhammer.rules import capability_key_drift
from verify_ml_artifacts import verify_ml_artifacts


def verify_artifacts(data_dir: Path) -> dict[str, Any]:
    data_dir = Path(data_dir)
    manifest_path = data_dir / "artifact_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("artifact_manifest.json does not contain an artifacts object")

    results = []
    for filename, expected in sorted(artifacts.items()):
        path = data_dir / filename
        if not isinstance(expected, dict):
            results.append(_result(filename, "invalid_manifest_entry", False))
            continue
        if not path.exists():
            results.append(_result(filename, "missing", False))
            continue
        actual_bytes = path.stat().st_size
        actual_sha = _sha256(path)
        expected_bytes = expected.get("bytes")
        expected_sha = expected.get("sha256")
        ok = actual_bytes == expected_bytes and actual_sha == expected_sha
        status = "ok" if ok else "mismatch"
        results.append(
            {
                "filename": filename,
                "status": status,
                "ok": ok,
                "expected_bytes": expected_bytes,
                "actual_bytes": actual_bytes,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
            }
        )
    linked_results, linked_paths = _verify_linked_ml_artifacts(manifest, base_dir=data_dir)
    results.extend(linked_results)
    model_type_result = _verify_linked_ml_model_type(manifest, linked_paths)
    if model_type_result:
        results.append(model_type_result)
    provenance_result = _verify_linked_ml_provenance(linked_paths)
    if provenance_result:
        results.append(provenance_result)
    capability_result = _verify_ruleset_capabilities(data_dir)
    if capability_result:
        results.append(capability_result)

    ok_count = sum(1 for item in results if item["ok"])
    failed = [item for item in results if not item["ok"]]
    return {
        "data_dir": str(data_dir),
        "manifest": str(manifest_path),
        "artifact_count": len(results),
        "ok_count": ok_count,
        "failed_count": len(failed),
        "ok": not failed,
        "results": results,
    }


def _result(filename: str, status: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {"filename": filename, "status": status, "ok": ok, **extra}


def _verify_linked_ml_artifacts(manifest: dict[str, Any], *, base_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    linked = manifest.get("linked_ml_artifacts")
    if not isinstance(linked, dict):
        return [], {}
    artifacts = linked.get("artifacts")
    if not isinstance(artifacts, dict):
        return [], {}

    results = []
    resolved_paths: dict[str, Path] = {}
    for name, expected in sorted(artifacts.items()):
        label = f"linked_ml_artifacts.{name}"
        if not isinstance(expected, dict):
            results.append(_result(label, "invalid_manifest_entry", False))
            continue
        path_text = str(expected.get("path") or "")
        path = _resolve_manifest_path(path_text, base_dir=base_dir)
        if not path.exists():
            results.append(_result(label, "missing", False, path=path_text))
            continue
        resolved_paths[name] = path
        actual_bytes = path.stat().st_size
        actual_sha = _sha256(path)
        expected_bytes = expected.get("bytes")
        expected_sha = expected.get("sha256")
        ok = actual_bytes == expected_bytes and actual_sha == expected_sha
        results.append(
            {
                "filename": label,
                "status": "ok" if ok else "mismatch",
                "ok": ok,
                "path": path_text,
                "expected_bytes": expected_bytes,
                "actual_bytes": actual_bytes,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
            }
        )
    return results, resolved_paths


def _verify_linked_ml_provenance(paths: dict[str, Path]) -> dict[str, Any] | None:
    feature_path = paths.get("feature_csv")
    model_path = paths.get("model_json")
    if not feature_path or not model_path:
        return None
    try:
        report = verify_ml_artifacts(feature_path, model_path)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        return _result(
            "linked_ml_artifacts.training_provenance",
            "error",
            False,
            error=str(exc),
        )
    return _result(
        "linked_ml_artifacts.training_provenance",
        "ok" if report["ok"] else "mismatch",
        bool(report["ok"]),
        ok_count=report["ok_count"],
        failed_count=report["failed_count"],
    )


def _verify_linked_ml_model_type(manifest: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any] | None:
    linked = manifest.get("linked_ml_artifacts")
    if not isinstance(linked, dict):
        return None
    expected_raw = str(linked.get("model_type") or "").strip()
    model_path = paths.get("model_json")
    if not expected_raw or not model_path:
        return None
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result("linked_ml_artifacts.model_type", "error", False, error=str(exc))
    expected = _expected_model_type(expected_raw)
    actual = str(model.get("model_type") or "")
    ok = actual == expected
    return _result(
        "linked_ml_artifacts.model_type",
        "ok" if ok else "mismatch",
        ok,
        expected=expected,
        actual=actual,
    )


def _verify_ruleset_capabilities(data_dir: Path) -> dict[str, Any] | None:
    status_path = Path(data_dir) / "edition_status.json"
    if not status_path.exists():
        return None
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result("edition_status.rule_capabilities", "error", False, error=str(exc))
    edition = str(status.get("edition") or "").strip()
    capabilities = status.get("rule_capabilities")
    if not isinstance(capabilities, list):
        capabilities = []
    drift = capability_key_drift(edition, capabilities)
    if drift is None:
        return None
    return _result(
        "edition_status.rule_capabilities",
        "ok" if drift["ok"] else "mismatch",
        bool(drift["ok"]),
        edition=edition,
        expected_count=drift["expected_count"],
        actual_count=drift["actual_count"],
        missing_keys=drift["missing_keys"],
        extra_keys=drift["extra_keys"],
    )


def _expected_model_type(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    return MODEL_TYPES.get(key, value)


def _resolve_manifest_path(path_text: str, *, base_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    cwd_path = path.resolve()
    if cwd_path.exists():
        return cwd_path
    data_relative = (Path(base_dir) / path).resolve()
    if data_relative.exists():
        return data_relative
    project_relative = _project_root_from_data_dir(Path(base_dir)) / path
    return project_relative.resolve()


def _project_root_from_data_dir(data_dir: Path) -> Path:
    resolved = Path(data_dir).resolve()
    parts = resolved.parts
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].lower() == "data" and index > 0:
            return Path(*parts[:index])
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify generated artifact files against artifact_manifest.json")
    parser.add_argument("--data-dir", type=Path, default=Path("data/latest"), help="Directory containing artifact_manifest.json")
    parser.add_argument("--json", action="store_true", help="Print full JSON verification results")
    args = parser.parse_args(argv)

    try:
        report = verify_artifacts(args.data_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Verification failed: {exc}")
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Verified {report['ok_count']} of {report['artifact_count']} checks in {report['data_dir']}")
        for item in report["results"]:
            if item["ok"]:
                continue
            print(f"- {item['filename']}: {item['status']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
