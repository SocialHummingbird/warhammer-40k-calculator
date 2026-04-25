#!/usr/bin/env python3
"""Refresh BSData sources and regenerate calculator data artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Sequence

from audit_import import build_audit_report, write_audit_report, write_schema_review
from review_profiles import write_profile_review


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

DATA_ARTIFACTS = (
    "units.csv",
    "weapons.csv",
    "abilities.csv",
    "keywords.csv",
    "unit_keywords.csv",
    "metadata.json",
    "audit_report.json",
    "schema_review.csv",
    "import_diff.json",
    "update_report.md",
    "weapon_profile_review.csv",
    "suspicious_weapon_review.csv",
    "ability_profile_review.csv",
    "ability_modifier_review.csv",
    "unit_variant_review.csv",
    "unit_weapon_coverage_review.csv",
    "loadout_review.csv",
    "source_catalogue_review.csv",
    "profile_review.md",
)

ARTIFACTS = (*DATA_ARTIFACTS, "artifact_manifest.json")


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

    _run(
        [sys.executable, "import_bsdata.py", str(repo_dir), "--output", str(csv_dir), "--edition", args.edition],
        cwd=PROJECT_ROOT,
    )

    after = _load_tables(csv_dir)
    diff = _build_import_diff(before, after, source_before=source_before, source_after=source_after)
    _write_json(csv_dir / "import_diff.json", diff)

    audit_report = build_audit_report(csv_dir)
    write_audit_report(audit_report, csv_dir / "audit_report.json")
    schema_review_rows = write_schema_review(csv_dir)
    profile_review_counts = write_profile_review(csv_dir)
    _write_text(csv_dir / "update_report.md", _build_update_report(diff, audit_report))
    _write_json(csv_dir / "artifact_manifest.json", _build_artifact_manifest(csv_dir, source_after))

    if not args.skip_html:
        _run([sys.executable, "export_local_html.py", "--csv-dir", str(csv_dir)], cwd=PROJECT_ROOT)

    snapshot_path = None
    if not args.skip_snapshot:
        snapshot_path = _write_snapshot(csv_dir, args.snapshot_dir.resolve(), source_after)

    _print_summary(source_before, source_after, diff, audit_report, snapshot_path, profile_review_counts, schema_review_rows)
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
    parser.add_argument("--edition", default="10e", help="Rules edition represented by the imported data")
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


def _build_update_report(diff: dict[str, object], audit_report: dict[str, object]) -> str:
    """Build a human-readable update and audit report."""

    source_after = diff.get("source_after", {})
    source_before = diff.get("source_before", {})
    source_url = _commit_url(source_after)
    commit = str(source_after.get("commit") or "unknown")
    before_commit = str(source_before.get("commit") or "unknown")
    generated_at = str(diff.get("generated_at") or audit_report.get("generated_at") or "")
    audit_summary = audit_report.get("summary", {})
    audit_status = "PASS" if int(audit_summary.get("total", 0) or 0) == 0 else "NEEDS REVIEW"

    lines = [
        "# Warhammer Data Update Report",
        "",
        f"Generated: {generated_at}",
        f"Source: {source_after.get('remote_origin') or 'unknown'}",
        f"Branch: {source_after.get('branch') or 'unknown'}",
        f"Commit: {before_commit} -> {commit}",
        f"Commit date: {source_after.get('commit_date') or 'unknown'}",
        f"Commit subject: {source_after.get('commit_subject') or 'unknown'}",
    ]
    if source_url:
        lines.append(f"Commit URL: {source_url}")
    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"Status: {audit_status}",
            "",
            "| Severity | Samples |",
            "| --- | ---: |",
            f"| Errors | {int(audit_summary.get('error', 0) or 0)} |",
            f"| Warnings | {int(audit_summary.get('warning', 0) or 0)} |",
            f"| Info | {int(audit_summary.get('info', 0) or 0)} |",
            f"| Total | {int(audit_summary.get('total', 0) or 0)} |",
            "",
        ]
    )

    issue_lines = _audit_issue_lines(audit_report)
    if issue_lines:
        lines.extend(["### Audit Issues", "", *issue_lines, ""])
    else:
        lines.extend(["No audit issues were reported.", ""])

    row_counts = audit_report.get("row_counts", {})
    lines.extend(
        [
            "## Current Row Counts",
            "",
            "| Table | Rows |",
            "| --- | ---: |",
        ]
    )
    for table in ("units", "weapons", "abilities", "keywords", "unit_keywords"):
        lines.append(f"| {table} | {int(row_counts.get(table, 0) or 0)} |")

    lines.extend(
        [
            "",
            "## Manual Review Files",
            "",
            "- `profile_review.md`: summary of imported profile counts and largest factions.",
            "- `weapon_profile_review.csv`: every imported weapon profile joined to unit name, faction, source file, points, model counts, parsed averages, and parse status.",
            "- `suspicious_weapon_review.csv`: zero or extreme parsed weapon damage characteristics for manual review.",
            "- `ability_profile_review.csv`: every imported ability profile joined to unit name, faction, and source file where applicable.",
            "- `ability_modifier_review.csv`: derived ability effects that the calculator applies during matchup math.",
            "- `unit_variant_review.csv`: duplicate-name unit rows joined to IDs, faction context, and source file.",
            "- `unit_weapon_coverage_review.csv`: each unit's ranged/melee weapon counts and coverage category.",
            "- `loadout_review.csv`: units with many imported weapon profiles where all-weapons calculations may need loadout selection.",
            "- `source_catalogue_review.csv`: per-catalogue unit, weapon, ability, suspicious, loadout review counts, and exact upstream GitHub file URLs.",
            "- `artifact_manifest.json`: file sizes and SHA-256 hashes for generated data artifacts.",
            "- `schema_review.csv`: required versus actual importer CSV columns for schema auditing.",
        ]
    )

    lines.extend(
        [
            "",
            "## Import Diff",
            "",
            "| Table | Before | After | Delta | Added | Removed | Changed |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    tables = diff.get("tables", {})
    for table in ("units", "weapons", "abilities", "keywords", "unit_keywords"):
        table_diff = tables.get(table, {})
        lines.append(
            f"| {table} | {int(table_diff.get('before_count', 0) or 0)} "
            f"| {int(table_diff.get('after_count', 0) or 0)} "
            f"| {int(table_diff.get('delta', 0) or 0):+d} "
            f"| {int(table_diff.get('added_count', 0) or 0)} "
            f"| {int(table_diff.get('removed_count', 0) or 0)} "
            f"| {int(table_diff.get('changed_count', 0) or 0)} |"
        )

    sample_lines = _diff_sample_lines(diff)
    if sample_lines:
        lines.extend(["", "### Diff Samples", "", *sample_lines])

    lines.append("")
    return "\n".join(lines)


def _commit_url(source: dict[str, object]) -> str:
    remote = str(source.get("remote_origin") or "")
    commit = str(source.get("commit") or "")
    if not remote or not commit:
        return ""
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.split(":", 1)[1]
    if remote.startswith("https://github.com/"):
        return f"{remote}/commit/{commit}"
    return ""


def _audit_issue_lines(audit_report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    sections = audit_report.get("sections", {})
    for section_name in ("schema", "units", "weapons", "abilities", "unit_keywords"):
        section = sections.get(section_name, {})
        for issue in section.get("issues", []):
            samples = ", ".join(str(sample) for sample in issue.get("samples", []))
            lines.append(
                f"- [{str(issue.get('severity', 'info')).upper()}] "
                f"{section_name}: {issue.get('label')} - {samples}"
            )
    return lines


def _diff_sample_lines(diff: dict[str, object]) -> list[str]:
    lines: list[str] = []
    tables = diff.get("tables", {})
    for table in ("units", "weapons", "abilities", "keywords", "unit_keywords"):
        table_diff = tables.get(table, {})
        for key, label in (
            ("added_samples", "Added"),
            ("removed_samples", "Removed"),
            ("changed_samples", "Changed"),
        ):
            samples = [str(sample) for sample in table_diff.get(key, [])]
            if samples:
                lines.append(f"- {table} {label.lower()}: {', '.join(samples)}")
    return lines


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


def _build_artifact_manifest(csv_dir: Path, source_after: dict[str, object]) -> dict[str, object]:
    artifacts = {}
    for filename in DATA_ARTIFACTS:
        path = csv_dir / filename
        if not path.exists():
            continue
        artifacts[filename] = {
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": source_after,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _print_summary(
    source_before: dict[str, object],
    source_after: dict[str, object],
    diff: dict[str, object],
    audit_report: dict[str, object],
    snapshot_path: Optional[Path],
    profile_review_counts: dict[str, int],
    schema_review_rows: int,
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
    print(f"Schema review: {schema_review_rows} table rows")
    print(
        "Profile review: "
        f"{profile_review_counts['weapon_profiles']} weapons, "
        f"{profile_review_counts.get('suspicious_weapon_profiles', 0)} suspicious weapon rows, "
        f"{profile_review_counts['ability_profiles']} abilities, "
        f"{profile_review_counts.get('ability_modifiers', 0)} ability modifier rows, "
        f"{profile_review_counts.get('unit_name_variants', 0)} duplicate-name unit rows, "
        f"{profile_review_counts.get('unit_weapon_coverage_rows', 0)} weapon coverage rows, "
        f"{profile_review_counts.get('loadout_review_rows', 0)} loadout review rows, "
        f"{profile_review_counts.get('source_catalogue_review_rows', 0)} source catalogue rows"
    )
    if snapshot_path:
        print(f"Snapshot: {snapshot_path}")


if __name__ == "__main__":
    raise SystemExit(main())
