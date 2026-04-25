#!/usr/bin/env python3
"""Verify generated data artifacts against artifact_manifest.json."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


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


def _result(filename: str, status: str, ok: bool) -> dict[str, Any]:
    return {"filename": filename, "status": status, "ok": ok}


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
        print(f"Verified {report['ok_count']} of {report['artifact_count']} artifacts in {report['data_dir']}")
        for item in report["results"]:
            if item["ok"]:
                continue
            print(f"- {item['filename']}: {item['status']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
