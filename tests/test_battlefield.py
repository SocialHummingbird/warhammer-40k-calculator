from __future__ import annotations

import pytest

from warhammer.battlefield.army import validate_army
from warhammer.battlefield.maps import generate_map
from warhammer.battlefield.models import ArmyList, ArmyUnit, BattleAction, to_dict
from warhammer.battlefield.simulation import (
    advance_phase,
    ai_plan,
    autoplay_battle,
    autoplay_turn,
    available_actions,
    battle_summary,
    evaluate_battlefield_attack,
    initial_battle_state,
    objective_controller,
    resolve_action,
    score_objectives_for_side,
    state_from_dict,
    unavailable_actions,
    validate_state,
    visibility_for_attack,
)
from warhammer.profiles import UnitProfile


def _unit(
    name: str,
    unit_id: str,
    *,
    points: int = 100,
    weapons: bool = True,
    objective_control: int = 1,
) -> UnitProfile:
    data = {
        "unit_id": unit_id,
        "name": name,
        "faction": "Test Faction",
        "toughness": 4,
        "save": "3+",
        "wounds": 2,
        "models_min": 5,
        "models_max": 5,
        "move": 6,
        "objective_control": objective_control,
        "points": points,
        "weapons": [],
    }
    if weapons:
        data["weapons"] = [
            {
                "name": "Bolt rifle",
                "type": "ranged",
                "attacks": "2",
                "skill": "3+",
                "strength": 4,
                "ap": 0,
                "damage": "1",
            },
            {
                "name": "Close combat weapon",
                "type": "melee",
                "attacks": "2",
                "skill": "3+",
                "strength": 4,
                "ap": 0,
                "damage": "1",
            },
        ]
    return UnitProfile.from_dict(data)


def _units_by_id():
    return {"red": _unit("Red Squad", "red"), "blue": _unit("Blue Squad", "blue", points=95)}


def _armies():
    return [
        ArmyList("red", "Red Army", "red", [ArmyUnit("red")]),
        ArmyList("blue", "Blue Army", "blue", [ArmyUnit("blue")]),
    ]


def test_generate_map_keeps_features_in_bounds():
    battle_map = generate_map("strike_force_44x60")

    assert battle_map.width == 44
    assert battle_map.height == 60
    assert len(battle_map.objectives) == 5
    assert {"rectangle", "ellipse", "diamond"} <= {terrain.shape for terrain in battle_map.terrain}
    assert max(terrain.stories for terrain in battle_map.terrain) >= 2
    assert any(terrain.type == "barricade" for terrain in battle_map.terrain)
    assert all(0 <= terrain.x <= battle_map.width for terrain in battle_map.terrain)
    assert all(0 <= objective.y <= battle_map.height for objective in battle_map.objectives)


def test_validate_army_reports_points_and_missing_weapons():
    units = {"red": _unit("Red Squad", "red", weapons=False)}
    army = ArmyList("red", "Red Army", "red", [ArmyUnit("red", count=2)])

    payload = validate_army(army, units)

    assert payload["ok"] is True
    assert payload["points"] == 200
    assert payload["unit_count"] == 2
    assert any("no imported weapon" in warning for warning in payload["warnings"])


def test_initial_state_places_units_and_round_trips():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)

    assert validate_state(state, units)["ok"] is True
    assert {unit.side for unit in state.units} == {"red", "blue"}
    restored = state_from_dict(to_dict(state))
    assert restored.map.width == state.map.width
    assert [unit.instance_id for unit in restored.units] == [unit.instance_id for unit in state.units]


def test_initial_state_gives_duplicate_unit_rows_unique_instance_ids():
    units = _units_by_id()
    armies = [
        ArmyList("red", "Red Army", "red", [ArmyUnit("red"), ArmyUnit("red", count=2)]),
        ArmyList("blue", "Blue Army", "blue", [ArmyUnit("blue")]),
    ]

    state = initial_battle_state(generate_map(), armies, units)
    red_ids = [unit.instance_id for unit in state.units if unit.side == "red"]

    assert red_ids == ["red-red-1", "red-red-2", "red-red-3"]


def test_ai_plan_is_deterministic_and_explains_scores():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)

    first = ai_plan(state, units, limit=3)
    second = ai_plan(state, units, limit=3)

    assert first == second
    assert first["actions"]
    assert first["actions"][0]["reason"]
    assert first["actions"][0]["assumptions"]


def test_resolve_shooting_action_updates_target_state():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    blue.x = red.x + 10
    blue.y = red.y
    state.phase = "shooting"
    action = next(action for action in available_actions(state, units) if action.type == "shoot")

    outcome = resolve_action(state, action, units)

    assert outcome.damage > 0
    assert outcome.state.log
    target = next(unit for unit in outcome.state.units if unit.instance_id == action.target_id)
    assert target.wounds_remaining < next(unit for unit in state.units if unit.instance_id == action.target_id).wounds_remaining


def test_autoplay_completes_one_turn_and_scores_or_logs_actions():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)

    payload = autoplay_turn(state, units)

    assert payload["state"]["turn"] == 2
    assert payload["replay"]
    assert payload["state"]["log"]
    assert {entry["outcome"]["phase"] for entry in payload["replay"]} <= {"movement", "shooting", "charge", "fight", "scoring"}
    assert "battlefield_ai" not in {entry["outcome"]["phase"] for entry in payload["replay"]}


def test_autoplay_battle_runs_multiple_bounded_turns():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)

    payload = autoplay_battle(state, units, turns=3)

    assert payload["completed_turns"] == 3
    assert payload["state"]["turn"] == 4
    assert payload["replay"]
    assert payload["state"]["log"]
    assert payload["battle_complete"] is False


def test_autoplay_stops_when_one_side_has_no_live_units():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    blue = next(unit for unit in state.units if unit.side == "blue")
    blue.models_remaining = 0
    blue.wounds_remaining = 0
    blue.status_flags = ["destroyed"]

    turn_payload = autoplay_turn(state, units)
    battle_payload = autoplay_battle(state, units, turns=3)

    assert turn_payload["completed_turns"] == 0
    assert turn_payload["battle_complete"] is True
    assert turn_payload["winner"] == "red"
    assert turn_payload["state"]["turn"] == 1
    assert battle_payload["completed_turns"] == 0
    assert battle_payload["battle_complete"] is True
    assert battle_payload["winner"] == "red"


def test_battle_summary_reports_leader_by_wipeout_vp_then_points():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    blue = next(unit for unit in state.units if unit.side == "blue")

    state.score["blue"] = 5
    score_summary = battle_summary(state, units)
    assert score_summary["leading_side"] == "blue"
    assert score_summary["basis"] == "vp"
    assert score_summary["margin"] == 5

    state.score["blue"] = 0
    blue.models_remaining = 1
    blue.wounds_remaining = units["blue"].wounds
    points_summary = battle_summary(state, units)
    assert points_summary["leading_side"] == "red"
    assert points_summary["basis"] == "points_remaining"
    assert points_summary["red"]["points_remaining"] > points_summary["blue"]["points_remaining"]

    blue.models_remaining = 0
    blue.wounds_remaining = 0
    blue.status_flags = ["destroyed"]
    wipeout_summary = battle_summary(state, units)
    assert wipeout_summary["battle_complete"] is True
    assert wipeout_summary["winner"] == "red"
    assert wipeout_summary["basis"] == "wipeout"


def test_objective_control_uses_profile_oc_not_raw_models():
    units = {
        "red": _unit("Red Squad", "red", objective_control=3),
        "blue": _unit("Blue Squad", "blue", objective_control=1),
    }
    state = initial_battle_state(generate_map(), _armies(), units)
    objective = state.map.objectives[2]
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = blue.x = objective.x
    red.y = blue.y = objective.y
    red.models_remaining = 2
    blue.models_remaining = 5

    assert objective_controller(state, objective, units) == "red"
    assert score_objectives_for_side(state, "red", units) >= objective.points


def test_available_actions_include_single_objective_score_action():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    objective = state.map.objectives[2]
    red = next(unit for unit in state.units if unit.side == "red")
    red.x = objective.x
    red.y = objective.y
    state.active_side = "red"
    state.phase = "scoring"

    actions = available_actions(state, units)
    score_actions = [action for action in actions if action.type == "score"]
    outcome = resolve_action(state, score_actions[0], units)
    after_score_actions = [action for action in available_actions(outcome.state, units) if action.type == "score"]

    assert len(score_actions) == 1
    assert score_actions[0].objective_value >= objective.points
    assert "controlled objectives" in score_actions[0].reason
    assert outcome.score_delta["red"] >= objective.points
    assert objective.name in outcome.log_entry["objectives"]
    assert after_score_actions == []


def test_move_action_applies_current_terrain_penalty():
    units = _units_by_id()
    battle_map = generate_map()
    state = initial_battle_state(battle_map, _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    terrain = battle_map.terrain[0]
    red.x = terrain.x + 1
    red.y = terrain.y + 1
    state.active_side = "red"

    move = next(action for action in available_actions(state, units) if action.actor_id == red.instance_id and action.type == "move")
    moved_distance = ((move.destination["x"] - red.x) ** 2 + (move.destination["y"] - red.y) ** 2) ** 0.5

    assert moved_distance <= 4.01
    assert any("Terrain movement penalty" in note for note in move.assumptions)


def test_intervening_ruin_obscures_ranged_attacks():
    units = _units_by_id()
    battle_map = generate_map()
    state = initial_battle_state(battle_map, _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    ruin = next(feature for feature in battle_map.terrain if feature.blocks_line_of_sight)
    red.x = ruin.x - 2
    red.y = ruin.y + ruin.height / 2
    blue.x = ruin.x + ruin.width + 2
    blue.y = red.y

    visibility = visibility_for_attack(battle_map, red, blue)
    obscured = evaluate_battlefield_attack(state, red, blue, units["red"], units["blue"], mode="ranged", edition="10e")
    ruin.blocks_line_of_sight = False
    cover_only = evaluate_battlefield_attack(state, red, blue, units["red"], units["blue"], mode="ranged", edition="10e")

    assert visibility["line_of_sight_blocked"] is True
    assert ruin.name in visibility["intervening_terrain"]
    assert obscured["context"]["line_of_sight_blocked"] is True
    assert obscured["context"]["damage_multiplier"] == 0.25
    assert obscured["damage"] == cover_only["damage"] * 0.25


def test_state_validation_reports_overlapping_unit_footprints():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    blue.x = red.x
    blue.y = red.y

    payload = validate_state(state, units)

    assert payload["ok"] is False
    assert any("overlaps" in error for error in payload["errors"])


def test_state_validation_reports_invalid_imported_map_geometry():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    state.map.terrain[0].x = state.map.width + 1
    state.map.terrain[1].stories = 0
    state.map.objectives[0].x = -5
    state.map.deployment_zones[0].width = -1

    payload = validate_state(state, units)

    assert payload["ok"] is False
    assert any("Terrain feature" in error and "outside the battlefield" in error for error in payload["errors"])
    assert any("Terrain feature" in error and "at least one storey" in error for error in payload["errors"])
    assert any("Objective" in error and "outside the battlefield" in error for error in payload["errors"])
    assert any("Deployment zone" in error and "positive width and height" in error for error in payload["errors"])


def test_state_validation_reports_invalid_turn_phase_active_side_and_score():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    state.turn = 0
    state.phase = "psychic"
    state.active_side = "green"
    state.score = {"red": -1}

    payload = validate_state(state, units)

    assert payload["ok"] is False
    assert any("turn" in error and "positive integer" in error for error in payload["errors"])
    assert any("active side" in error and "red or blue" in error for error in payload["errors"])
    assert any("phase" in error and "not supported" in error for error in payload["errors"])
    assert any("score for red" in error and "negative" in error for error in payload["errors"])
    assert any("score is missing blue" in error for error in payload["errors"])


def test_state_validation_reports_invalid_unit_identity_and_side():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    unit = state.units[0]
    state.units[1].instance_id = unit.instance_id
    unit.unit_id = "missing"
    unit.side = "green"
    unit.radius = 0

    payload = validate_state(state, units)

    assert payload["ok"] is False
    assert any("Duplicate battlefield unit id" in error for error in payload["errors"])
    assert any("unknown unit id missing" in error for error in payload["errors"])
    assert any("invalid side green" in error for error in payload["errors"])
    assert any("positive footprint radius" in error for error in payload["errors"])


def test_move_resolution_adjusts_destination_to_avoid_overlap():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    blue.x = red.x + 5
    blue.y = red.y
    action = BattleAction(
        id="move-into-blue",
        type="move",
        side="red",
        actor_id=red.instance_id,
        destination={"x": blue.x, "y": blue.y},
    )

    outcome = resolve_action(state, action, units)
    moved_red = next(unit for unit in outcome.state.units if unit.instance_id == red.instance_id)
    blue_after = next(unit for unit in outcome.state.units if unit.instance_id == blue.instance_id)

    assert ((moved_red.x - blue_after.x) ** 2 + (moved_red.y - blue_after.y) ** 2) ** 0.5 >= moved_red.radius + blue_after.radius
    assert any("overlap" in note for note in outcome.log_entry["assumptions"])


def test_move_resolution_clamps_destination_to_movement_allowance():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    action = BattleAction(
        id="move-too-far",
        type="move",
        side="red",
        actor_id=red.instance_id,
        destination={"x": red.x + 30, "y": red.y},
    )

    outcome = resolve_action(state, action, units)
    moved_red = next(unit for unit in outcome.state.units if unit.instance_id == red.instance_id)

    assert ((moved_red.x - red.x) ** 2 + (moved_red.y - red.y) ** 2) ** 0.5 <= 6.01
    assert any("clamped" in note for note in outcome.log_entry["assumptions"])


def test_charge_resolution_uses_expected_charge_probability():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = 17
    blue.y = 10
    state.active_side = "red"
    state.phase = "charge"
    charge = next(action for action in available_actions(state, units) if action.type == "charge")
    fight = BattleAction(
        id="fight-blue",
        type="fight",
        side="red",
        actor_id=red.instance_id,
        target_id=blue.instance_id,
    )

    charge_outcome = resolve_action(state, charge, units)
    charged_red = next(unit for unit in charge_outcome.state.units if unit.instance_id == red.instance_id)
    charged_blue = next(unit for unit in charge_outcome.state.units if unit.instance_id == blue.instance_id)
    fight_state = charge_outcome.state
    fight_state.phase = "fight"
    fight_outcome = resolve_action(fight_state, fight, units)
    probability = charge_outcome.log_entry["context"]["charge_probability"]

    assert 0 < probability < 1
    assert charge.expected_damage == fight_outcome.damage * probability
    assert charge_outcome.damage == 0
    assert charged_blue.wounds_remaining == blue.wounds_remaining
    assert "destination" in charge_outcome.log_entry
    assert charge_outcome.log_entry["destination"]["x"] != red.x
    assert "melee damage is resolved in the Fight phase" in " ".join(charge_outcome.log_entry["assumptions"])
    assert max(0, ((charged_red.x - charged_blue.x) ** 2 + (charged_red.y - charged_blue.y) ** 2) ** 0.5 - charged_red.radius - charged_blue.radius) <= 1.0
    assert "full_melee_damage_if_charge_connects" in charge_outcome.log_entry["context"]
    assert "expected_followup_fight_damage" in charge_outcome.log_entry["context"]


def test_out_of_range_targets_do_not_generate_shoot_actions():
    units = _units_by_id()
    state = initial_battle_state(generate_map("onslaught_44x90"), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 2
    red.y = 2
    blue.x = 42
    blue.y = 88
    state.active_side = "red"
    state.phase = "shooting"

    actions = available_actions(state, units)

    assert [action for action in actions if action.type == "shoot" and action.target_id == blue.instance_id] == []


def test_available_actions_are_filtered_by_phase():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = red.x + red.radius + blue.radius + 0.5
    blue.y = 10
    state.active_side = "red"

    state.phase = "movement"
    assert {action.type for action in available_actions(state, units)} <= {"move", "advance", "fall_back", "hold"}

    state.phase = "shooting"
    blue.x = 20
    assert "shoot" in {action.type for action in available_actions(state, units)}
    assert "move" not in {action.type for action in available_actions(state, units)}

    blue.x = red.x + red.radius + blue.radius + 0.5
    state.phase = "charge"
    assert "charge" not in {action.type for action in available_actions(state, units)}
    assert "fight" not in {action.type for action in available_actions(state, units)}

    state.phase = "fight"
    assert "fight" in {action.type for action in available_actions(state, units)}
    assert "charge" not in {action.type for action in available_actions(state, units)}


def test_engaged_units_do_not_generate_normal_shooting_actions():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = red.x + red.radius + blue.radius + 0.5
    blue.y = 10
    state.active_side = "red"
    state.phase = "shooting"

    actions = available_actions(state, units)

    assert [action for action in actions if action.type == "shoot" and action.actor_id == red.instance_id] == []
    assert any(action.type == "hold" and action.actor_id == red.instance_id for action in actions)


def test_unavailable_actions_explain_phase_specific_blockers():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = red.x + red.radius + blue.radius + 0.5
    blue.y = 10
    state.active_side = "red"

    state.phase = "movement"
    movement_rows = unavailable_actions(state, units)
    assert any(row["type"] == "move" and "fall back" in row["reason"] for row in movement_rows)
    assert any(row["type"] == "advance" and "fall back" in row["reason"] for row in movement_rows)

    state.phase = "shooting"
    shooting_rows = unavailable_actions(state, units)
    assert any(row["type"] == "shoot" and "engaged" in row["reason"] for row in shooting_rows)

    state.phase = "charge"
    charge_rows = unavailable_actions(state, units)
    assert any(row["type"] == "charge" and "already engaged" in row["reason"] for row in charge_rows)

    blue.x = 40
    state.phase = "fight"
    fight_rows = unavailable_actions(state, units)
    assert any(row["type"] == "fight" and "engagement range" in row["reason"] for row in fight_rows)


def test_fall_back_moves_from_engagement_and_blocks_shooting_or_charging():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = red.x + red.radius + blue.radius + 0.5
    blue.y = 10
    state.active_side = "red"
    state.phase = "movement"

    generated_types = {action.type for action in available_actions(state, units) if action.actor_id == red.instance_id}
    assert "fall_back" in generated_types
    assert "move" not in generated_types
    assert "advance" not in generated_types

    with pytest.raises(ValueError, match="fall back instead"):
        resolve_action(
            state,
            BattleAction(id="bad-engaged-move", type="move", side="red", actor_id=red.instance_id, destination={"x": 4, "y": 10}),
            units,
        )
    with pytest.raises(ValueError, match="fall back instead"):
        resolve_action(
            state,
            BattleAction(id="bad-engaged-advance", type="advance", side="red", actor_id=red.instance_id, destination={"x": 2, "y": 10}),
            units,
        )

    fall_back = next(action for action in available_actions(state, units) if action.type == "fall_back")
    outcome = resolve_action(state, fall_back, units)
    moved_red = next(unit for unit in outcome.state.units if unit.instance_id == red.instance_id)

    assert moved_red.x < red.x
    assert "fell_back_turn_1" in moved_red.status_flags
    assert "Fall Back movement" in " ".join(outcome.log_entry["assumptions"])

    outcome.state.phase = "shooting"
    shooting_actions = available_actions(outcome.state, units)
    assert [action for action in shooting_actions if action.type == "shoot" and action.actor_id == red.instance_id] == []

    outcome.state.phase = "charge"
    charge_actions = available_actions(outcome.state, units)
    assert [action for action in charge_actions if action.type == "charge" and action.actor_id == red.instance_id] == []


def test_advance_moves_farther_and_blocks_charge_with_advanced_context():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = 20
    blue.y = 10
    state.active_side = "red"
    state.phase = "movement"

    advance = next(action for action in available_actions(state, units) if action.type == "advance")
    move = next(action for action in available_actions(state, units) if action.type == "move" and action.actor_id == red.instance_id)
    advance_outcome = resolve_action(state, advance, units)
    advanced_red = next(unit for unit in advance_outcome.state.units if unit.instance_id == red.instance_id)

    advance_distance = ((advanced_red.x - red.x) ** 2 + (advanced_red.y - red.y) ** 2) ** 0.5
    move_distance = ((move.destination["x"] - red.x) ** 2 + (move.destination["y"] - red.y) ** 2) ** 0.5
    assert advance_distance >= move_distance
    assert "advanced_turn_1" in advanced_red.status_flags
    assert "moved_turn_1" in advanced_red.status_flags

    advance_outcome.state.phase = "shooting"
    result = evaluate_battlefield_attack(advance_outcome.state, advanced_red, blue, units["red"], units["blue"], mode="ranged", edition="10e")
    assert result["context"]["attacker_moved"] is True
    assert result["context"]["attacker_advanced"] is True

    advance_outcome.state.phase = "charge"
    charge_actions = available_actions(advance_outcome.state, units)
    assert [action for action in charge_actions if action.type == "charge" and action.actor_id == red.instance_id] == []
    with pytest.raises(ValueError, match="after advancing"):
        resolve_action(
            advance_outcome.state,
            BattleAction(id="bad-charge", type="charge", side="red", actor_id=red.instance_id, target_id=blue.instance_id),
            units,
        )


def test_advance_phase_steps_side_and_battle_round():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)

    state = advance_phase(state)
    assert state.active_side == "red"
    assert state.phase == "shooting"
    assert state.turn == 1

    state.phase = "scoring"
    state = advance_phase(state)
    assert state.active_side == "blue"
    assert state.phase == "movement"
    assert state.turn == 1

    state.phase = "scoring"
    state = advance_phase(state)
    assert state.active_side == "red"
    assert state.phase == "movement"
    assert state.turn == 2
    assert state.log[-1]["action"] == "advance_phase"


def test_resolve_action_rejects_wrong_phase_and_inactive_side():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = 20
    blue.y = 10
    state.active_side = "red"
    state.phase = "movement"

    with pytest.raises(ValueError, match="not available"):
        resolve_action(
            state,
            BattleAction(id="early-shot", type="shoot", side="red", actor_id=red.instance_id, target_id=blue.instance_id),
            units,
        )

    state.phase = "shooting"
    with pytest.raises(ValueError, match="red's turn"):
        resolve_action(
            state,
            BattleAction(id="blue-shot", type="shoot", side="blue", actor_id=blue.instance_id, target_id=red.instance_id),
            units,
        )


def test_resolve_action_rejects_invalid_manual_targets_and_fallbacks():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = 30
    blue.y = 10
    state.active_side = "red"

    state.phase = "movement"
    with pytest.raises(ValueError, match="only fall back while engaged"):
        resolve_action(
            state,
            BattleAction(id="bad-fallback", type="fall_back", side="red", actor_id=red.instance_id, destination={"x": 4, "y": 10}),
            units,
        )

    state.phase = "shooting"
    with pytest.raises(ValueError, match="friendly"):
        resolve_action(
            state,
            BattleAction(id="friendly-fire", type="shoot", side="red", actor_id=red.instance_id, target_id=red.instance_id),
            units,
        )

    blue.models_remaining = 0
    blue.wounds_remaining = 0
    blue.status_flags = ["destroyed"]
    with pytest.raises(ValueError, match="no live models"):
        resolve_action(
            state,
            BattleAction(id="shoot-dead", type="shoot", side="red", actor_id=red.instance_id, target_id=blue.instance_id),
            units,
        )


def test_resolve_action_rejects_fight_outside_engagement_range():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = 25
    blue.y = 10
    state.active_side = "red"
    state.phase = "fight"

    with pytest.raises(ValueError, match="engagement range"):
        resolve_action(
            state,
            BattleAction(id="long-fight", type="fight", side="red", actor_id=red.instance_id, target_id=blue.instance_id),
            units,
        )


def test_resolve_action_rejects_charge_while_already_engaged():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 10
    red.y = 10
    blue.x = red.x + red.radius + blue.radius + 0.5
    blue.y = 10
    state.active_side = "red"
    state.phase = "charge"

    assert [action for action in available_actions(state, units) if action.type == "charge"] == []
    with pytest.raises(ValueError, match="already engaged"):
        resolve_action(
            state,
            BattleAction(id="charge-engaged", type="charge", side="red", actor_id=red.instance_id, target_id=blue.instance_id),
            units,
        )


def test_unit_cannot_act_twice_in_same_phase():
    units = _units_by_id()
    state = initial_battle_state(generate_map(), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    blue.x = red.x + 10
    blue.y = red.y
    state.active_side = "red"
    state.phase = "shooting"
    action = next(action for action in available_actions(state, units) if action.type == "shoot" and action.actor_id == red.instance_id)

    outcome = resolve_action(state, action, units)

    assert outcome.log_entry["actor_id"] == red.instance_id
    assert [action for action in available_actions(outcome.state, units) if action.actor_id == red.instance_id] == []
    with pytest.raises(ValueError, match="already acted"):
        resolve_action(outcome.state, action, units)


def test_out_of_range_shooting_resolves_to_zero_damage_with_context():
    units = _units_by_id()
    state = initial_battle_state(generate_map("onslaught_44x90"), _armies(), units)
    red = next(unit for unit in state.units if unit.side == "red")
    blue = next(unit for unit in state.units if unit.side == "blue")
    red.x = 2
    red.y = 2
    blue.x = 42
    blue.y = 88
    state.phase = "shooting"
    action = BattleAction(
        id="manual-too-far",
        type="shoot",
        side="red",
        actor_id=red.instance_id,
        target_id=blue.instance_id,
    )

    outcome = resolve_action(state, action, units)
    target = next(unit for unit in outcome.state.units if unit.instance_id == blue.instance_id)

    assert outcome.damage == 0
    assert target.wounds_remaining == blue.wounds_remaining
    assert outcome.log_entry["context"]["attack_in_range"] is False
    assert outcome.log_entry["context"]["weapon_range"] == 36
    assert any("no ranged weapon is assumed to reach" in note for note in outcome.log_entry["assumptions"])
