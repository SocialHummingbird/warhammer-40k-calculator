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
            "points": 100,
            "models_min": 5,
            "models_max": 5,
            "objective_control": 2,
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
    assert payload["units"][0]["objective_control"] == 2
    assert payload["factions"] == ["Faction A", "Faction B"]
    assert payload["edition"] == "10e"


def test_unit_payload_uses_unit_id_and_reports_missing_unit(tmp_path):
    state = _State(tmp_path)

    payload = web_api.unit_payload_from_query({"id": ["u2"], "name": ["ignored"]}, state=state)

    assert payload["unit"]["name"] == "Beta"
    assert payload["unit"]["objective_control"] == 2
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


def test_battlefield_templates_payload_exposes_presets():
    payload = web_api.battlefield_templates_payload()

    assert [template["id"] for template in payload["templates"]] == ["strike_force_44x60", "onslaught_44x90"]
    assert payload["rules"]["preset"] == "tactical_mvp_v1"


def test_battlefield_validate_army_payload_uses_loaded_dataset(tmp_path):
    payload = web_api.battlefield_validate_army_payload(
        {"edition": "10e", "army": {"side": "red", "units": [{"unit_id": "u1", "count": 2}]}},
        state=_State(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["edition"] == "10e"
    assert payload["points"] == 200


def test_battlefield_ai_plan_payload_returns_state_and_actions(tmp_path):
    payload = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "limit": 2,
        },
        state=_State(tmp_path),
    )

    assert payload["edition"] == "10e"
    assert payload["state"]["map"]["id"] == "strike_force_44x60"
    assert payload["actions"]


def test_battlefield_new_state_payload_accepts_imported_map(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "limit": 1,
        },
        state=state,
    )
    battle_map = plan["state"]["map"]
    battle_map["id"] = "imported-map"
    battle_map["width"] = 50

    payload = web_api.battlefield_new_state_payload(
        {
            "edition": "10e",
            "map": battle_map,
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
        },
        state=state,
    )

    assert payload["edition"] == "10e"
    assert payload["state"]["map"]["id"] == "imported-map"
    assert payload["state"]["map"]["width"] == 50
    assert {unit["side"] for unit in payload["state"]["units"]} == {"red", "blue"}


def test_battlefield_new_state_payload_rejects_invalid_imported_map(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "limit": 1,
        },
        state=state,
    )
    battle_map = plan["state"]["map"]
    battle_map["terrain"][0]["x"] = battle_map["width"] + 5

    with pytest.raises(ValueError, match="Terrain feature"):
        web_api.battlefield_new_state_payload(
            {
                "edition": "10e",
                "map": battle_map,
                "armies": [
                    {"side": "red", "units": [{"unit_id": "u1"}]},
                    {"side": "blue", "units": [{"unit_id": "u2"}]},
                ],
            },
            state=state,
        )


def test_battlefield_resolve_score_uses_objective_control(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "limit": 2,
        },
        state=state,
    )
    battle_state = plan["state"]
    objective = battle_state["map"]["objectives"][0]
    red_unit = next(unit for unit in battle_state["units"] if unit["side"] == "red")
    red_unit["x"] = objective["x"]
    red_unit["y"] = objective["y"]
    battle_state["phase"] = "scoring"

    payload = web_api.battlefield_resolve_payload(
        {
            "edition": "10e",
            "state": battle_state,
            "action": {"type": "score", "side": "red", "actor_id": red_unit["instance_id"]},
        },
        state=state,
    )

    assert payload["state"]["score"]["red"] >= objective["points"]
    assert payload["outcome"]["log_entry"]["score_delta"]["red"] >= objective["points"]


def test_battlefield_autoplay_payload_accepts_turn_limit(tmp_path):
    payload = web_api.battlefield_autoplay_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "turns": 3,
        },
        state=_State(tmp_path),
    )

    assert payload["completed_turns"] == 3
    assert payload["state"]["turn"] == 4
    assert payload["replay"]
    assert payload["summary"]["basis"] in {"vp", "points_remaining", "even", "wipeout"}
    assert set(payload["summary"]) >= {"red", "blue", "leading_side", "reason"}


def test_battlefield_actions_payload_includes_unavailable_diagnostics(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
        },
        state=state,
    )
    battle_state = plan["state"]
    red = next(unit for unit in battle_state["units"] if unit["side"] == "red")
    blue = next(unit for unit in battle_state["units"] if unit["side"] == "blue")
    red["x"] = 10
    red["y"] = 10
    blue["x"] = 12
    blue["y"] = 10
    battle_state["phase"] = "shooting"

    payload = web_api.battlefield_actions_payload({"edition": "10e", "state": battle_state}, state=state)

    assert payload["unavailable_actions"]
    assert any(row["type"] == "shoot" and "engaged" in row["reason"] for row in payload["unavailable_actions"])


def test_battlefield_autoplay_payload_reports_completed_battle(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
        },
        state=state,
    )
    battle_state = plan["state"]
    blue_unit = next(unit for unit in battle_state["units"] if unit["side"] == "blue")
    blue_unit["models_remaining"] = 0
    blue_unit["wounds_remaining"] = 0
    blue_unit["status_flags"] = ["destroyed"]

    payload = web_api.battlefield_autoplay_payload({"edition": "10e", "state": battle_state, "turns": 1}, state=state)

    assert payload["completed_turns"] == 0
    assert payload["battle_complete"] is True
    assert payload["winner"] == "red"
    assert payload["summary"]["winner"] == "red"
    assert payload["summary"]["basis"] == "wipeout"
    assert payload["state"]["turn"] == 1


def test_battlefield_advance_phase_payload_updates_state(tmp_path):
    state = _State(tmp_path)
    plan = web_api.battlefield_ai_plan_payload(
        {
            "edition": "10e",
            "template_id": "strike_force_44x60",
            "armies": [
                {"side": "red", "units": [{"unit_id": "u1"}]},
                {"side": "blue", "units": [{"unit_id": "u2"}]},
            ],
            "limit": 1,
        },
        state=state,
    )

    payload = web_api.battlefield_advance_phase_payload({"edition": "10e", "state": plan["state"]}, state=state)

    assert payload["edition"] == "10e"
    assert payload["state"]["phase"] == "shooting"
    assert payload["state"]["active_side"] == "red"
    assert payload["log_entry"]["action"] == "advance_phase"
