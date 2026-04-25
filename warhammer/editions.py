from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .data_review import load_json_file, source_info_from_metadata
from .rules import available_rulesets, get_ruleset


def rules_edition_from_metadata(metadata: Optional[Dict[str, Any]], *, default: str = "10e") -> str:
    if not metadata:
        return default
    value = str(metadata.get("rules_edition") or default).strip() or default
    get_ruleset(value)
    return value


def supported_rules_editions_from_metadata(metadata: Optional[Dict[str, Any]]) -> list[str]:
    raw = metadata.get("supported_rules_editions") if metadata else None
    values = [str(value).strip() for value in raw] if isinstance(raw, list) else []
    values = [value for value in values if value]
    if not values:
        values = sorted(available_rulesets())
    supported = [value for value in values if value in available_rulesets()]
    return supported or sorted(available_rulesets())


def available_edition_rows(
    datasets: Dict[str, Any],
    *,
    active_edition: str,
    discovered_rows: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, Any]]:
    rows = []
    for edition, dataset in datasets.items():
        rows.append(
            edition_data_info(
                edition=edition,
                data_dir=dataset.data_dir,
                metadata=dataset.metadata or {},
                active_edition=active_edition,
                loaded=True,
            )
        )
    loaded_editions = {str(row["edition"]) for row in rows}
    for row in discovered_rows or []:
        if str(row.get("edition")) not in loaded_editions:
            rows.append(row)
    return sorted(rows, key=lambda row: (str(row["edition"]).casefold(), str(row["path"]).casefold()))


def discover_edition_data_dirs(
    data_root: Path,
    *,
    active_data_dir: Optional[Path] = None,
    default_edition: str = "10e",
) -> list[Dict[str, Any]]:
    discovered: list[Dict[str, Any]] = []
    if data_root.exists():
        for child in sorted(data_root.iterdir(), key=lambda path: path.name.casefold()):
            latest = child / "latest"
            if not child.is_dir() or not latest.is_dir():
                continue
            metadata = load_json_file(latest / "metadata.json") or {}
            edition = str(metadata.get("rules_edition") or child.name).strip() or child.name
            discovered.append(
                edition_data_info(
                    edition=edition,
                    data_dir=latest,
                    metadata=metadata,
                    active_data_dir=active_data_dir,
                )
            )

    if active_data_dir and not any(same_path(Path(row["path"]), active_data_dir) for row in discovered):
        metadata = load_json_file(active_data_dir / "metadata.json") or {}
        discovered.append(
            edition_data_info(
                edition=str(metadata.get("rules_edition") or default_edition),
                data_dir=active_data_dir,
                metadata=metadata,
                active_data_dir=active_data_dir,
            )
        )

    return sorted(discovered, key=lambda row: (str(row["edition"]).casefold(), str(row["path"]).casefold()))


def edition_data_info(
    *,
    edition: str,
    data_dir: Optional[Path],
    metadata: Dict[str, Any],
    active_data_dir: Optional[Path] = None,
    active_edition: Optional[str] = None,
    loaded: bool = False,
) -> Dict[str, Any]:
    counts = metadata.get("counts") if isinstance(metadata.get("counts"), dict) else {}
    source_info = source_info_from_metadata(metadata)
    rules_available = edition in available_rulesets()
    active = (
        edition == active_edition
        if active_edition is not None
        else (same_path(data_dir, active_data_dir) if data_dir and active_data_dir else False)
    )
    return {
        "edition": edition,
        "label": edition_label(edition),
        "path": str(data_dir) if data_dir else "",
        "active": active,
        "loaded": loaded,
        "units": int(counts.get("units", 0) or 0),
        "commit": source_info.get("commit", ""),
        "commit_short": source_info.get("commit_short", ""),
        "generated_at": source_info.get("generated_at", ""),
        "rules_available": rules_available,
        "status": "blocked" if not rules_available else ("loaded" if loaded else "available"),
        "unavailable_reason": "" if rules_available else "Ruleset not implemented",
    }


def edition_label(edition: str) -> str:
    if edition == "10e":
        return "10th Edition"
    if edition == "11e":
        return "11th Edition"
    return edition.upper()


def same_path(left: Path, right: Optional[Path]) -> bool:
    if right is None:
        return False
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right
