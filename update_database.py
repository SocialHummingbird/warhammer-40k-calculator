#!/usr/bin/env python3
"""Refresh BSData sources and regenerate calculator data artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Sequence

from audit_import import build_audit_report, write_audit_report


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_DIR = PROJECT_ROOT / "data" / "wh40k-10e"
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots"

TABLES = {
    "units": ("units.csv", "unit_id"),
    "weapons": ("weapons.csv", "weapon_id"),
    "abilities": ("abilities.csv", "ability_id"),
    "keywords": ("keywords.csv", "keyword_id"),
    "unit_keywords": ("unit_keywords.csv", ("unit_id", "keyword_id")),
}

ARTIFACTS = (
    "units.csv",
    "weapons.csv",
    "abilities.csv",
    "keywords.csv",
    "unit_keywords.csv",
    "metadata.json",
    "audit_report.json",
    "import_diff.json",
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    repo_dir = args.repo_dir.resolve()
    csv_dir = args.csv_dir.resolve()

    before = _load_tables(csv_dir)
    source_before = _git_metadata(repo_dir)

    if not args.skip_fetch:
        _ensure_clean_source(repo_dir)
        _run(["git", "-C", str(repo_dir), "fetch", args.remote, args.branch])
        _run(["git", "-C", str(repo_dir), "merge", "--ff-only", f"{args.remote}/{args.branch}"])

    source_after = _git_metadata(repo_dir)

    _run([sys.executable, "import_bsdata.py", str(repo_dir), "--output", str(csv_dir)], cwd=PROJECT_ROOT)

    after = _load_tables(csv_dir)
    diff = _build_import_diff(before, after, source_before=source_before, source_after=source_after)
    _write_json(csv_dir / "import_diff.json", diff)

    audit_report = build_audit_report(csv_dir)
    write_audit_report(audit_report, csv_dir / "audit_report.json")

    if not args.skip_html:
        _run([sys.executable, "export_local_html.py", "--csv-dir", str(csv_dir)], cwd=PROJECT_ROOT)

    snapshot_path = None
    if not args.skip_snapshot:
        snapshot_path = _write_snapshot(csv_dir, args.snapshot_dir.resolve(), source_after)

    _print_summary(source_before, source_after, diff, audit_report, snapshot_path)
    return 0


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update BSData source, regenerate CSVs, audit, diff, and local HTML")
    parser.add_argument("--repo-dir", type=Path, default=DEFAULT_REPO_DIR, help="Local BSData Git checkout")
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR, help="Output directory for generated CSVs")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR, help="Directory for versioned snapshots")
    parser.add_argument("--remote", default="origin", help="Git remote to fetch from")
    parser.add_argument("--branch", default="main", help="Git branch to fast-forward")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch or merge the BSData checkout")
    parser.add_argument("--skip-html", action="store_true", help="Do not regenerate the standalone local HTML")
    parser.add_argument("--skip-snapshot", action="store_true", help="Do not copy generated data into data/snapshots")
    return parser.parse_args(argv)


def _ensure_clean_source(repo_dir: Path) -> None:
    status = _git(repo_dir, "status", "--short")
    if status:
        raise SystemExit(f"Source checkout has local changes; refusing to update:\n{status}")


def _git_metadata(repo_dir: Path) -> dict[str, object]:
    return {
        "path": str(repo_dir),
        "remote_origin": _git(repo_dir, "remote", "get-url", "origin"),
        "branch": _git(repo_dir, "branch", "--show-current"),
        "commit": _git(repo_dir, "rev-parse", "HEAD"),
        "commit_date": _git(repo_dir, "log", "-1", "--format=%ci"),
        "commit_subject": _git(repo_dir, "log", "-1", "--format=%s"),
        "dirty": bool(_git(repo_dir, "status", "--short")),
    }


def _git(repo_dir: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _run(command: Sequence[str], *, cwd: Optional[Path] = None) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        joined = " ".join(str(part) for part in command)
        raise SystemExit(f"Command failed with exit {completed.returncode}: {joined}")


def _load_tables(csv_dir: Path) -> dict[str, dict[str, dict[str, str]]]:
    tables: dict[str, dict[str, dict[str, str]]] = {}
    for table, (filename, key_fields) in TABLES.items():
        rows = _read_csv(csv_dir / filename)
        keyed_rows: dict[str, dict[str, str]] = {}
        key_counts: dict[str, int] = {}
        for index, row in enumerate(rows, start=1):
            base_key = _row_key(row, key_fields) or f"<row-{index}>"
            key_counts[base_key] = key_counts.get(base_key, 0) + 1
            key = base_key if key_counts[base_key] == 1 else f"{base_key}#{key_counts[base_key]}"
            keyed_rows[key] = row
        tables[table] = keyed_rows
    return tables


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _row_key(row: Dict[str, str], key_fields: str | tuple[str, ...]) -> str:
    if isinstance(key_fields, str):
        return (row.get(key_fields) or "").strip()
    return ":".join((row.get(field) or "").strip() for field in key_fields)


def _build_import_diff(
    before: dict[str, dict[str, dict[str, str]]],
    after: dict[str, dict[str, dict[str, str]]],
    *,
    source_before: dict[str, object],
    source_after: dict[str, object],
) -> dict[str, object]:
    tables = {}
    for table in TABLES:
        before_rows = before.get(table, {})
        after_rows = after.get(table, {})
        before_ids = set(before_rows)
        after_ids = set(after_rows)
        added = sorted(after_ids - before_ids)
        removed = sorted(before_ids - after_ids)
        changed = sorted(row_id for row_id in before_ids & after_ids if before_rows[row_id] != after_rows[row_id])
        tables[table] = {
            "before_count": len(before_rows),
            "after_count": len(after_rows),
            "delta": len(after_rows) - len(before_rows),
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "added_samples": added[:20],
            "removed_samples": removed[:20],
            "changed_samples": changed[:20],
        }

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_before": source_before,
        "source_after": source_after,
        "tables": tables,
    }


def _write_snapshot(csv_dir: Path, snapshot_dir: Path, source_after: dict[str, object]) -> Path:
    commit = str(source_after.get("commit") or "unknown")
    snapshot_name = commit[:12] if commit and commit != "unknown" else datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = snapshot_dir / snapshot_name
    target.mkdir(parents=True, exist_ok=True)
    for artifact in ARTIFACTS:
        source = csv_dir / artifact
        if source.exists():
            shutil.copy2(source, target / artifact)
    return target


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _print_summary(
    source_before: dict[str, object],
    source_after: dict[str, object],
    diff: dict[str, object],
    audit_report: dict[str, object],
    snapshot_path: Optional[Path],
) -> None:
    print("Database update complete.")
    print(f"Source: {source_after.get('remote_origin')}")
    print(f"Commit: {source_before.get('commit')} -> {source_after.get('commit')}")
    print(f"Subject: {source_after.get('commit_subject')}")
    print("Rows:")
    for table, table_diff in diff["tables"].items():
        print(
            f"  {table}: {table_diff['before_count']} -> {table_diff['after_count']} "
            f"({table_diff['delta']:+d}), changed {table_diff['changed_count']}"
        )
    summary = audit_report["summary"]
    print(f"Audit samples: {summary['error']} errors, {summary['warning']} warnings, {summary['info']} info")
    if snapshot_path:
        print(f"Snapshot: {snapshot_path}")


if __name__ == "__main__":
    raise SystemExit(main())
