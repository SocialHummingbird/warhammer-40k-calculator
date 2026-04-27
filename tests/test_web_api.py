from __future__ import annotations

import pytest

from warhammer import web_api
from warhammer.profiles import UnitProfile
from warhammer.web_state import EditionDataset


def _unit(name: str, *, unit_id: str, faction: str = "", keywords: list[str] | None = None) -> UnitProfile:
    return UnitProfile.from_dict(
        {
            "unit_id": unit_id,
            "name": name,
            "faction": faction,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "keywords": keywords or [],
            "weapons": [
                {
                    "name": "Test Weapon",
                    "type": "ranged",
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                }
            ],
        }
    )


class _State:
    def __init__(self, tmp_path):
        self.rules_edition = "10e"
        self.source = str(tmp_path)
        self.metadata = {"generated_at": "2026-04-26T00:00:00Z", "rules_edition": "10e"}
        self.model_dir = tmp_path / "models" / "10e"
        self.model_dir.mkdir(parents=True)
        self.dataset = EditionDataset(
            edition="10e",
            data_dir=tmp_path,
            source=str(tmp_path),
            units={
                "alpha": _unit("Alpha", unit_id="u1", faction="Faction A", keywords=["Infantry"]),
                "beta": _unit("Beta", unit_id="u2", faction="Faction B", keywords=["Vehicle"]),
            },
            metadata=self.metadata,
        )
        self.units = self.dataset.units
        self.available_editions = [{"edition": "10e", "status": "active"}]

    def dataset_for_edition(self, edition=None):
        if edition not in {None, "", "10e"}:
            raise ValueError("unknown edition")
        return self.dataset

    def ml_model_dir_for_edition(self, edition=None):
        return self.model_dir

    def ml_model_path_for_edition(self, edition=None):
        return self.model_dir / "matchup_centroid_model.json"

    def ml_model_status(self):
        return {"10e": {"available": False}}


def test_health_payload_summarizes_loaded_state(tmp_path):
    payload = web_api.health_payload(_State(tmp_path))

    assert payload["ok"] is True
    assert payload["units"] == 2
    assert payload["source_info"]["rules_edition"] == "10e"
    assert payload["available_editions"] == [{"edition": "10e", "status": "active"}]
    assert payload["rulesets"]["10e"]["capability_count"] >= 10
    assert {item["key"] for item in payload["rulesets"]["10e"]["capabilities"]} >= {
        "hit_rolls",
        "wound_rolls",
        "save_resolution",
        "model_removal",
    }
    assert payload["ml_models"] == {"10e": {"available": False}}


def test_units_payload_applies_query_filter_and_factions(tmp_path):
    payload = web_api.units_payload_from_query({"q": ["vehicle"], "limit": ["1"]}, state=_State(tmp_path))

    assert [unit["name"] for unit in payload["units"]] == ["Beta"]
    assert payload["factions"] == ["Faction A", "Faction B"]
    assert payload["edition"] == "10e"


def test_unit_payload_uses_unit_id_and_reports_missing_unit(tmp_path):
    state = _State(tmp_path)

    assert web_api.unit_payload_from_query({"id": ["u2"], "name": ["ignored"]}, state=state)["unit"]["name"] == "Beta"
    with pytest.raises(web_api.WebApiNotFound, match="Unknown unit"):
        web_api.unit_payload_from_query({"name": ["Missing"]}, state=state)


def test_review_file_download_validates_requested_filename(tmp_path):
    state = _State(tmp_path)
    (tmp_path / "profile_review.md").write_text("# Review\n", encoding="utf-8")

    path, content_type = web_api.review_file_download("/api/review-files/10e/profile_review.md", state=state)

    assert path == tmp_path / "profile_review.md"
    assert content_type.startswith("text/markdown")
    with pytest.raises(web_api.WebApiNotFound, match="Unknown review file"):
        web_api.review_file_download("/api/review-files/10e/not_allowed.txt", state=state)


def test_model_file_download_validates_requested_filename(tmp_path):
    state = _State(tmp_path)
    (state.model_dir / "matchup_centroid_model.json").write_text("{}", encoding="utf-8")

    path, content_type = web_api.model_file_download(
        "/api/ml-model-files/10e/matchup_centroid_model.json",
        state=state,
    )

    assert path == state.model_dir / "matchup_centroid_model.json"
    assert content_type.startswith("application/json")
    with pytest.raises(web_api.WebApiNotFound, match="Unknown ML model file"):
        web_api.model_file_download("/api/ml-model-files/10e/model.pkl", state=state)


def test_model_file_download_allows_selected_custom_model(tmp_path):
    state = _State(tmp_path)
    selected = state.model_dir / "custom_model.json"
    selected.write_text("{}", encoding="utf-8")
    state.ml_model_path_for_edition = lambda edition=None: selected

    path, content_type = web_api.model_file_download(
        "/api/ml-model-files/10e/custom_model.json",
        state=state,
    )

    assert path == selected
    assert content_type.startswith("application/json")
