from warhammer.calculator import EngagementContext
from warhammer.matchups import calculate_matchup
from warhammer.ml.advisory import ml_judgement_from_result, model_status
from warhammer.ml.model import DEFAULT_FEATURE_COLUMNS, train_centroid_model
from warhammer.profiles import UnitProfile


def _unit(name, *, unit_id, weapons):
    return UnitProfile.from_dict(
        {
            "unit_id": unit_id,
            "name": name,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": 100,
            "models_min": 1,
            "models_max": 1,
            "weapons": weapons,
        }
    )


def _training_row(label, *, outgoing_damage, incoming_damage):
    row = {column: 0 for column in DEFAULT_FEATURE_COLUMNS}
    row.update(
        {
            "label_source": "deterministic_calculator",
            "winner_label": label,
            "outgoing_damage": outgoing_damage,
            "incoming_damage": incoming_damage,
            "damage_delta": outgoing_damage - incoming_damage,
            "outgoing_points_removed": outgoing_damage,
            "incoming_points_removed": incoming_damage,
            "points_removed_delta": outgoing_damage - incoming_damage,
        }
    )
    return row


def test_ml_judgement_from_result_returns_advisory_payload():
    attacker = _unit(
        "Shooter",
        unit_id="u1",
        weapons=[{"name": "Big gun", "type": "ranged", "attacks": "6", "skill": "3+", "strength": 8, "ap": -2, "damage": "3"}],
    )
    defender = _unit(
        "Target",
        unit_id="u2",
        weapons=[{"name": "Small gun", "type": "ranged", "attacks": "1", "skill": "5+", "strength": 3, "ap": 0, "damage": "1"}],
    )
    model = train_centroid_model(
        [
            _training_row("attacker", outgoing_damage=6, incoming_damage=1),
            _training_row("attacker", outgoing_damage=7, incoming_damage=1),
            _training_row("defender", outgoing_damage=1, incoming_damage=6),
            _training_row("defender", outgoing_damage=1, incoming_damage=7),
        ],
        validation_fraction=0,
    )
    model["training_source"] = {"rows": 4, "sha256": "abcdef1234567890"}
    result = calculate_matchup(
        attacker,
        defender,
        "ranged",
        outgoing_context=EngagementContext(),
        incoming_context=EngagementContext(),
    )

    judgement = ml_judgement_from_result(
        model,
        attacker=attacker,
        defender=defender,
        mode="ranged",
        result=result,
    )

    assert judgement is not None
    assert judgement["available"] is True
    assert judgement["winner_label"] in {"attacker", "defender", "close"}
    assert judgement["model_type"] == "nearest_centroid_classifier"
    assert judgement["feature_set"] == "full"
    assert judgement["feature_rows"] == 4
    assert judgement["feature_sha256_short"] == "abcdef123456"
    assert "advisory" in judgement["body"]


def test_ml_judgement_from_result_returns_none_without_model():
    attacker = _unit("A", unit_id="u1", weapons=[])
    defender = _unit("B", unit_id="u2", weapons=[])

    assert (
        ml_judgement_from_result(
            None,
            attacker=attacker,
            defender=defender,
            mode="ranged",
            result={"outgoing": {}, "incoming": {}, "judgement": {}},
        )
        is None
    )


def test_model_status_summarizes_loaded_and_missing_models():
    model = train_centroid_model(
        [
            _training_row("attacker", outgoing_damage=6, incoming_damage=1),
            _training_row("defender", outgoing_damage=1, incoming_damage=6),
        ],
        validation_fraction=0,
    )
    model["training_source"] = {"rows": 2, "sha256": "1234567890abcdef"}

    assert model_status(None) == {"available": False}
    status = model_status(model)
    assert status["available"] is True
    assert status["model_type"] == "nearest_centroid_classifier"
    assert status["feature_set"] == "full"
    assert status["training_rows"] == 2
    assert status["feature_rows"] == 2
    assert status["feature_sha256_short"] == "1234567890ab"
    assert status["labels"] == ["attacker", "defender"]
