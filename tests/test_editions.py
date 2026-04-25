from dataclasses import dataclass
from pathlib import Path

import pytest

from warhammer.editions import (
    available_edition_rows,
    discover_edition_data_dirs,
    edition_label,
    rules_edition_from_metadata,
    supported_rules_editions_from_metadata,
)


@dataclass
class _Dataset:
    data_dir: Path
    metadata: dict


def test_discover_edition_data_dirs_lists_available_latest_folders(tmp_path):
    latest = tmp_path / "10e" / "latest"
    latest.mkdir(parents=True)
    (latest / "metadata.json").write_text(
        """
{
  "generated_at": "2026-04-25T12:00:00Z",
  "rules_edition": "10e",
  "counts": {"units": 12},
  "source_revisions": [{"commit": "abcdef123456"}]
}
""".strip(),
        encoding="utf-8",
    )

    rows = discover_edition_data_dirs(tmp_path, active_data_dir=latest)

    assert rows == [
        {
            "edition": "10e",
            "label": "10th Edition",
            "path": str(latest),
            "active": True,
            "loaded": False,
            "units": 12,
            "commit": "abcdef123456",
            "commit_short": "abcdef123456",
            "generated_at": "2026-04-25T12:00:00Z",
            "rules_available": True,
            "status": "available",
            "unavailable_reason": "",
        }
    ]


def test_discover_edition_data_dirs_reports_blocked_unimplemented_ruleset(tmp_path):
    latest = tmp_path / "11e" / "latest"
    latest.mkdir(parents=True)
    (latest / "metadata.json").write_text(
        """
{
  "generated_at": "2026-04-25T12:00:00Z",
  "rules_edition": "11e",
  "counts": {"units": 3}
}
""".strip(),
        encoding="utf-8",
    )

    rows = discover_edition_data_dirs(tmp_path)

    assert rows[0]["edition"] == "11e"
    assert rows[0]["label"] == "11th Edition"
    assert rows[0]["rules_available"] is False
    assert rows[0]["status"] == "blocked"
    assert rows[0]["unavailable_reason"] == "Ruleset not implemented"


def test_available_edition_rows_preserve_blocked_discovered_editions(tmp_path):
    dataset = _Dataset(
        data_dir=tmp_path / "10e" / "latest",
        metadata={"rules_edition": "10e", "counts": {"units": 1}},
    )
    blocked = {
        "edition": "11e",
        "label": "11th Edition",
        "path": str(tmp_path / "11e" / "latest"),
        "active": False,
        "loaded": False,
        "units": 3,
        "commit": "",
        "commit_short": "",
        "generated_at": "",
        "rules_available": False,
        "status": "blocked",
        "unavailable_reason": "Ruleset not implemented",
    }

    rows = available_edition_rows({"10e": dataset}, active_edition="10e", discovered_rows=[blocked])

    assert [row["edition"] for row in rows] == ["10e", "11e"]
    loaded = next(row for row in rows if row["edition"] == "10e")
    assert loaded["loaded"] is True
    assert loaded["status"] == "loaded"
    assert next(row for row in rows if row["edition"] == "11e")["status"] == "blocked"


def test_rules_edition_helpers_validate_supported_rulesets():
    assert rules_edition_from_metadata(None) == "10e"
    assert rules_edition_from_metadata({"rules_edition": "10e"}) == "10e"
    with pytest.raises(ValueError, match="Unsupported rules edition"):
        rules_edition_from_metadata({"rules_edition": "11e"})

    assert supported_rules_editions_from_metadata(None) == ["10e"]
    assert supported_rules_editions_from_metadata({"supported_rules_editions": ["10e", "11e"]}) == ["10e"]


def test_edition_label_formats_known_and_unknown_editions():
    assert edition_label("10e") == "10th Edition"
    assert edition_label("11e") == "11th Edition"
    assert edition_label("heresy") == "HERESY"
