from __future__ import annotations

from warhammer.battlefield.army import validate_army
from warhammer.battlefield.maps import generate_map
from warhammer.battlefield.models import ArmyList, ArmyUnit, to_dict
from warhammer.battlefield.simulation import (
    ai_plan,
    autoplay_turn,
    available_actions,
    initial_battle_state,
    objective_controller,
    resolve_action,
    score_objectives_for_side,
    state_from_dict,
    validate_state,
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
