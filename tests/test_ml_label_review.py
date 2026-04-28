import csv
from pathlib import Path
import subprocess
import sys

from warhammer.ml.label_review import build_label_review_rows, validate_label_review_rows, write_label_review_csv


def _feature_row(label, *, confidence, edge, attacker_id="a1", defender_id="d1"):
    return {
        "edition": "10e",
        "mode": "ranged",
        "winner_label": label,
        "confidence": confidence,
        "edge": edge,
        "attacker_id": attacker_id,
        "attacker_name": f"Attacker {attacker_id}",
        "attacker_faction": "Faction A",
        "attacker_points": "100",
        "attacker_models": "5",
        "attacker_mode_weapon_count": "2",
        "defender_id": defender_id,
        "defender_name": f"Defender {defender_id}",
        "defender_faction": "Faction D",
        "defender_points": "90",
        "defender_models": "10",
        "defender_mode_weapon_count": "1",
        "points_removed_delta": "2.5",
        "damage_delta": "1.1",
        "outgoing_points_removed": "10",
        "incoming_points_removed": "7.5",
        "outgoing_damage": "3",
        "incoming_damage": "1.9",
    }


def test_build_label_review_rows_prioritizes_uncertain_rows_and_leaves_label_blank():
    rows = build_label_review_rows(
        [
            _feature_row("attacker", confidence=0.9, edge=80, attacker_id="a2"),
            _feature_row("close", confidence=0.3, edge=1, attacker_id="a1"),
        ],
        limit=1,
    )

    assert len(rows) == 1
    assert rows[0]["attacker_id"] == "a1"
    assert rows[0]["winner_label"] == ""
    assert rows[0]["deterministic_winner_label"] == "close"
    assert rows[0]["attacker_name"] == "Attacker a1"


def test_validate_label_review_rows_reports_invalid_duplicates_and_missing_keys():
    summary = validate_label_review_rows(
        [
            {"edition": "10e", "mode": "ranged", "attacker_id": "a1", "defender_id": "d1", "winner_label": "attacker"},
            {"edition": "10e", "mode": "ranged", "attacker_id": "a1", "defender_id": "d1", "winner_label": "defender"},
            {"edition": "10e", "mode": "melee", "attacker_id": "", "defender_id": "d2", "winner_label": "maybe"},
            {"edition": "10e", "mode": "melee", "attacker_id": "a3", "defender_id": "d3", "winner_label": ""},
        ]
    )

    assert summary["valid"] is False
    assert summary["rows"] == 4
    assert summary["labelled_rows"] == 3
    assert summary["unlabelled_rows"] == 1
    assert summary["duplicate_keys"] == 1
    assert summary["missing_key_rows"] == 1
    assert summary["invalid_label_rows"] == 1
    assert summary["label_counts"]["attacker"] == 1


def test_write_label_review_csv_round_trips_expected_columns(tmp_path):
    output = tmp_path / "labels.csv"
    rows = build_label_review_rows([_feature_row("defender", confidence=0.2, edge=3)])

    assert write_label_review_csv(rows, output) == 1
    with output.open(encoding="utf-8", newline="") as handle:
        loaded = list(csv.DictReader(handle))

    assert loaded[0]["winner_label"] == ""
    assert loaded[0]["deterministic_winner_label"] == "defender"
    assert "review_notes" in loaded[0]


def test_export_ml_label_queue_cli_exports_and_validates(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    features = tmp_path / "features.csv"
    labels = tmp_path / "labels.csv"
    with features.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_feature_row("close", confidence=0.1, edge=0).keys()))
        writer.writeheader()
        writer.writerow(_feature_row("close", confidence=0.1, edge=0))

    export_result = subprocess.run(
        [
            sys.executable,
            "export_ml_label_queue.py",
            "--features",
            str(features),
            "--output",
            str(labels),
            "--limit",
            "1",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if export_result.returncode != 0:
        raise AssertionError(export_result.stderr or export_result.stdout)

    assert labels.exists()
    rows = list(csv.DictReader(labels.open(encoding="utf-8", newline="")))
    rows[0]["winner_label"] = "close"
    with labels.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    validate_result = subprocess.run(
        [sys.executable, "export_ml_label_queue.py", "--validate-labels", str(labels)],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert validate_result.returncode == 0
    assert '"labelled_rows": 1' in validate_result.stdout
