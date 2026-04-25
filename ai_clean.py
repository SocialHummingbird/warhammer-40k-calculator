#!/usr/bin/env python3
"""AI-assisted data quality review for importer CSV outputs.

The script collects lightweight heuristics (missing values, duplicate names, etc.)
from the CSV exports in a directory and optionally asks the configured OpenAI
model to highlight suspicious entries and suggest follow-up checks.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_KEY_PATHS = [
    Path.home() / ".warhammer_ai_key",
    Path("credentials/ai_key.txt"),
]


def resolve_api_key() -> str:
    env_key = os.environ.get("WARHAMMER_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    path_override = os.environ.get("WARHAMMER_AI_KEY_FILE")
    candidates = []
    if path_override:
        candidates.append(Path(path_override).expanduser())
    candidates.extend(DEFAULT_KEY_PATHS)

    for candidate in candidates:
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        return stripped
        except OSError:
            continue

    raise SystemExit(
        "Provide an API key via WARHAMMER_AI_API_KEY / OPENAI_API_KEY or place it in "
        "~/.warhammer_ai_key (or credentials/ai_key.txt)."
    )


def _safe_print(payload: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(payload.encode(encoding, errors="replace").decode(encoding))


try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _collect_blank_stats(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"blank": 0, "samples": []})
    for idx, row in enumerate(rows, start=2):  # +1 for header, +1 for 1-based row numbers
        for column, raw_value in row.items():
            value = (raw_value or "").strip()
            if not value:
                entry = stats[column]
                entry["blank"] += 1
                if len(entry["samples"]) < 3:
                    sample = {key: row[key] for key in ("name", "unit_id", "weapon_id") if key in row}
                    sample["row"] = idx
                    entry["samples"].append(sample)
    return {column: info for column, info in stats.items() if info["blank"] > 0}


def _collect_duplicates(rows: List[Dict[str, str]], key: str) -> List[str]:
    names = [row.get(key, "").strip() for row in rows if row.get(key)]
    counter = Counter(names)
    return [name for name, count in counter.items() if count > 1]


def analyse_csv(path: Path) -> Dict[str, Any]:
    rows = _load_csv(path)
    info: Dict[str, Any] = {
        "file": path.name,
        "row_count": len(rows),
        "blanks": _collect_blank_stats(rows),
    }
    if path.name == "units.csv":
        info["duplicate_names"] = _collect_duplicates(rows, "name")
    if path.name == "weapons.csv":
        info["duplicate_weapon_ids"] = _collect_duplicates(rows, "weapon_id")
    if path.name == "unit_keywords.csv":
        info["duplicate_mappings"] = _collect_duplicates(rows, "unit_id")
    return info


def build_summary(csv_dir: Path) -> Dict[str, Any]:
    files = [
        csv_dir / "units.csv",
        csv_dir / "weapons.csv",
        csv_dir / "abilities.csv",
        csv_dir / "unit_keywords.csv",
        csv_dir / "keywords.csv",
    ]
    existing = [path for path in files if path.exists()]
    if not existing:
        raise SystemExit(f"No importer CSV files found in {csv_dir}. Run import_bsdata.py first.")
    return {
        "csv_dir": str(csv_dir.resolve()),
        "analysed_files": [analyse_csv(path) for path in existing],
    }


def format_summary(summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"CSV directory: {summary['csv_dir']}")
    for file_info in summary["analysed_files"]:
        lines.append("")
        lines.append(f"File: {file_info['file']} (rows: {file_info['row_count']})")
        blanks: Dict[str, Any] = file_info.get("blanks", {})
        if blanks:
            for column, info in blanks.items():
                samples = ", ".join(
                    f"row {sample['row']} -> { {k: v for k, v in sample.items() if k != 'row'} }"
                    for sample in info["samples"]
                )
                lines.append(
                    f"  - Column '{column}' blank in {info['blank']} rows. Samples: {samples or 'n/a'}"
                )
        else:
            lines.append("  - No blank values detected.")
        for key in ("duplicate_names", "duplicate_weapon_ids", "duplicate_mappings"):
            duplicates = file_info.get(key)
            if duplicates:
                pretty = ", ".join(duplicates[:10])
                more = "" if len(duplicates) <= 10 else " (truncated)"
                label = key.replace("_", " ")
                lines.append(f"  - {label}: {pretty}{more}")
    return "\n".join(lines)


def call_ai(summary_text: str, model: str, api_key: str) -> str:
    if OpenAI is None:  # pragma: no cover - optional dependency
        raise SystemExit("The openai package is not installed. Run `pip install openai`." )
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a data quality assistant for a Warhammer 40K dataset. "
                    "Given a summary of importer CSV stats, identify the most likely data issues, "
                    "explain why they are problematic, and suggest concise remediation steps. "
                    "If the data looks clean, confirm that instead of inventing issues."
                ),
            },
            {
                "role": "user",
                "content": summary_text,
            },
        ],
    )
    # The SDK returns a Responses object whose convenience property output_text
    # collects the assistant message content.
    return response.output_text  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-assisted importer data review")
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=Path("data/latest"),
        help="Directory containing importer CSV exports (default: data/latest)",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="OpenAI model ID to query (default: gpt-5-mini)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print the heuristic summary without calling the AI API",
    )
    args = parser.parse_args()

    summary = build_summary(args.csv_dir)
    summary_text = format_summary(summary)
    print("=== Heuristic summary ===")
    _safe_print(summary_text)

    if args.summary_only:
        return

    api_key = resolve_api_key()

    print("\n=== AI assessment ===")
    ai_report = call_ai(summary_text, args.model, api_key)
    _safe_print(ai_report)


if __name__ == "__main__":
    main()


