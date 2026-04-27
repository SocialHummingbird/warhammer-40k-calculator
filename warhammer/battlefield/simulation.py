from __future__ import annotations

import copy
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..calculator import evaluate_unit
from ..context import EngagementContext
from ..matchup_payloads import points_per_model, unit_summary
from ..profiles import UnitProfile
from .models import (
    ArmyList,
    BattleAction,
    BattleMap,
    BattleOutcome,
    BattleState,
    BattleUnit,
    Objective,
    action_from_dict,
    army_from_dict,
    map_from_dict,
    state_from_dict,
    to_dict,
)

MVP_ASSUMPTIONS = [
    "Battlefield mode uses circular unit blobs and centre-to-centre range.",
    "Line of sight is approximated from terrain rectangles; obscuring edge cases are not tournament exact.",
    "Charge and fight resolution use expected values and simplified engagement distance.",
]


def initial_battle_state(
    battle_map: BattleMap,
    armies: Iterable[ArmyList],
    units_by_id: Dict[str, UnitProfile],
) -> BattleState:
    battle_units: List[BattleUnit] = []
    armies_list = list(armies)
    side_offsets = {"red": 0, "blue": 0}
    copy_counters: Dict[Tuple[str, str], int] = {}
    for army in armies_list:
        zone = deployment_zone_for_side(battle_map, army.side)
        if zone is None:
            continue
        entries = [entry for entry in army.units if entry.unit_id in units_by_id]
        for entry in entries:
            unit = units_by_id[entry.unit_id]
            for duplicate_index in range(max(1, entry.count)):
                counter_key = (army.side, entry.unit_id)
                copy_counters[counter_key] = copy_counters.get(counter_key, 0) + 1
                index = side_offsets[army.side]
                side_offsets[army.side] += 1
                columns = max(1, math.ceil(math.sqrt(max(1, len(entries)))))
                col = index % columns
                row = index // columns
                x = zone.x + min(zone.width - 2, 4 + col * 7)
                y = zone.y + min(zone.height - 2, 4 + row * 5)
                battle_units.append(
                    BattleUnit(
                        instance_id=f"{army.side}-{entry.unit_id}-{copy_counters[counter_key]}",
                        unit_id=entry.unit_id,
                        side=army.side,
                        name=unit.name,
                        x=max(1, min(battle_map.width - 1, x)),
                        y=max(1, min(battle_map.height - 1, y)),
                        radius=default_radius(unit),
                        models_remaining=default_models(unit),
                        wounds_remaining=float(default_models(unit) * max(1, unit.wounds)),
                    )
                )
    return BattleState(map=battle_map, armies=armies_list, units=battle_units)


def validate_state(state: BattleState, units_by_id: Dict[str, UnitProfile]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: set[str] = set()
    for unit in state.units:
        if unit.instance_id in seen_ids:
            errors.append(f"Duplicate battlefield unit id {unit.instance_id}.")
        seen_ids.add(unit.instance_id)
        if unit.unit_id not in units_by_id:
            errors.append(f"{unit.name} has unknown unit id {unit.unit_id}.")
        if not in_bounds(state.map, unit.x, unit.y, unit.radius):
            errors.append(f"{unit.name} is outside the battlefield.")
        if unit.side not in {"red", "blue"}:
            errors.append(f"{unit.name} has invalid side {unit.side}.")
        profile = units_by_id.get(unit.unit_id)
        if profile and not profile.weapons:
            warnings.append(f"{profile.name} has no imported weapons.")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "assumptions": MVP_ASSUMPTIONS,
        "state": to_dict(state),
    }


def available_actions(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e") -> List[BattleAction]:
    actions: List[BattleAction] = []
    active_units = [unit for unit in live_units(state) if unit.side == state.active_side]
    enemies = [unit for unit in live_units(state) if unit.side != state.active_side]
    for actor in active_units:
        profile = units_by_id.get(actor.unit_id)
        if profile is None:
            continue
        hold = BattleAction(
            id=f"{actor.instance_id}:hold",
            type="hold",
            side=actor.side,
            actor_id=actor.instance_id,
            score=0.1,
            reason="Hold position; no stronger action identified yet.",
            assumptions=MVP_ASSUMPTIONS[:1],
        )
        actions.append(hold)

        objective = nearest_objective(state.map.objectives, actor.x, actor.y)
        if objective is not None:
            move_allowance, move_notes = movement_allowance_for_unit(state.map, actor, profile)
            dest = step_towards(actor.x, actor.y, objective.x, objective.y, move_allowance)
            objective_value = objective_action_value(state, actor, profile, objective, dest)
            actions.append(
                BattleAction(
                    id=f"{actor.instance_id}:move:{objective.id}",
                    type="move",
                    side=actor.side,
                    actor_id=actor.instance_id,
                    destination=dest,
                    score=objective_value,
                    objective_value=objective_value,
                    reason=(
                        f"Move toward {objective.name} to improve objective control"
                        f" using {move_allowance:.1f}\" movement."
                    ),
                    assumptions=MVP_ASSUMPTIONS[:1] + move_notes,
                )
            )

        for target in enemies:
            target_profile = units_by_id.get(target.unit_id)
            if target_profile is None:
                continue
            ranged = score_combat_action(
                state,
                actor,
                target,
                profile,
                target_profile,
                mode="ranged",
                edition=edition,
            )
            actions.append(ranged)
            if distance(actor.x, actor.y, target.x, target.y) <= 12 + actor.radius + target.radius:
                melee = score_combat_action(
                    state,
                    actor,
                    target,
                    profile,
                    target_profile,
                    mode="melee",
                    edition=edition,
                )
                melee.type = "charge"
                melee.id = f"{actor.instance_id}:charge:{target.instance_id}"
                melee.reason = f"Attempt a simplified charge into {target.name}; expected melee damage {melee.expected_damage:.2f}."
                melee.assumptions = MVP_ASSUMPTIONS
                melee.score *= charge_probability(actor, target)
                actions.append(melee)
    return sorted(actions, key=lambda action: (-action.score, action.id))


def ai_plan(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e", limit: int = 8) -> Dict[str, Any]:
    actions = available_actions(state, units_by_id, edition=edition)
    return {
        "actions": [to_dict(action) for action in actions[: max(1, limit)]],
        "assumptions": MVP_ASSUMPTIONS,
    }


def resolve_action(
    state: BattleState,
    action: BattleAction,
    units_by_id: Dict[str, UnitProfile],
    *,
    edition: str = "10e",
) -> BattleOutcome:
    next_state = copy.deepcopy(state)
    actor = unit_by_instance(next_state, action.actor_id)
    if actor is None:
        raise ValueError(f"Unknown actor {action.actor_id}")

    log_entry: Dict[str, Any] = {
        "turn": next_state.turn,
        "phase": next_state.phase,
        "side": actor.side,
        "actor": actor.name,
        "action": action.type,
        "reason": action.reason,
        "assumptions": action.assumptions or MVP_ASSUMPTIONS[:1],
    }
    damage = 0.0
    points_removed = 0.0
    score_delta: Dict[str, int] = {}

    if action.type == "move" and action.destination:
        actor.x = max(actor.radius, min(next_state.map.width - actor.radius, float(action.destination["x"])))
        actor.y = max(actor.radius, min(next_state.map.height - actor.radius, float(action.destination["y"])))
        log_entry["destination"] = {"x": round(actor.x, 2), "y": round(actor.y, 2)}
    elif action.type in {"shoot", "charge", "fight"}:
        target = unit_by_instance(next_state, action.target_id or "")
        if target is None:
            raise ValueError(f"Unknown target {action.target_id}")
        attacker = units_by_id.get(actor.unit_id)
        defender = units_by_id.get(target.unit_id)
        if attacker is None or defender is None:
            raise ValueError("Action references unknown unit profile")
        mode = "melee" if action.type in {"charge", "fight"} else "ranged"
        result = evaluate_battlefield_attack(next_state, actor, target, attacker, defender, mode=mode, edition=edition)
        damage = result["damage"]
        target.wounds_remaining = max(0.0, target.wounds_remaining - damage)
        target.models_remaining = max(0, math.ceil(target.wounds_remaining / max(1, defender.wounds)))
        ppm = points_per_model(defender) or 0.0
        points_removed = max(0.0, (result["models_before"] - target.models_remaining) * ppm)
        if target.models_remaining <= 0:
            target.status_flags = sorted(set(target.status_flags + ["destroyed"]))
        log_entry.update(
            {
                "target": target.name,
                "damage": round(damage, 3),
                "models_remaining": target.models_remaining,
                "points_removed": round(points_removed, 2),
                "context": result["context"],
            }
        )
    elif action.type == "score":
        gained = score_objectives_for_side(next_state, actor.side, units_by_id)
        next_state.score[actor.side] = next_state.score.get(actor.side, 0) + gained
        score_delta[actor.side] = gained
        log_entry["score_delta"] = score_delta
    else:
        log_entry["detail"] = "Held position."

    next_state.log.append(log_entry)
    return BattleOutcome(action=action, state=next_state, log_entry=log_entry, damage=damage, points_removed=points_removed, score_delta=score_delta)


def autoplay_turn(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e") -> Dict[str, Any]:
    next_state = copy.deepcopy(state)
    replay: List[Dict[str, Any]] = []
    for side in ("red", "blue"):
        next_state.active_side = side
        next_state.phase = "battlefield_ai"
        for actor in [unit for unit in live_units(next_state) if unit.side == side]:
            plan_actions = [action for action in available_actions(next_state, units_by_id, edition=edition) if action.actor_id == actor.instance_id]
            if not plan_actions:
                continue
            chosen = plan_actions[0]
            outcome = resolve_action(next_state, chosen, units_by_id, edition=edition)
            next_state = outcome.state
            replay.append({"chosen": to_dict(chosen), "outcome": outcome.log_entry})
        gained = score_objectives_for_side(next_state, side, units_by_id)
        if gained:
            next_state.score[side] = next_state.score.get(side, 0) + gained
            entry = {
                "turn": next_state.turn,
                "phase": "scoring",
                "side": side,
                "action": "score",
                "score_delta": {side: gained},
                "reason": "End-of-turn objective scoring using Objective Control within objective range.",
                "assumptions": [MVP_ASSUMPTIONS[0]],
            }
            next_state.log.append(entry)
            replay.append({"chosen": {"type": "score", "side": side}, "outcome": entry})
    next_state.turn += 1
    next_state.phase = "movement"
    next_state.active_side = "red"
    return {"state": to_dict(next_state), "replay": replay, "assumptions": MVP_ASSUMPTIONS}


def state_from_payload(payload: Dict[str, Any], units_by_id: Dict[str, UnitProfile]) -> BattleState:
    if payload.get("state"):
        return state_from_dict(payload["state"])
    battle_map = map_from_dict(payload.get("map") or {})
    if not battle_map.deployment_zones:
        from .maps import generate_map

        battle_map = generate_map(str((payload.get("map") or {}).get("id") or payload.get("template_id") or "strike_force_44x60"))
    armies = [army_from_dict(row) for row in payload.get("armies", [])]
    return initial_battle_state(battle_map, armies, units_by_id)


def action_from_payload(payload: Dict[str, Any]) -> BattleAction:
    return action_from_dict(payload.get("action") or payload)


def score_combat_action(
    state: BattleState,
    actor: BattleUnit,
    target: BattleUnit,
    attacker: UnitProfile,
    defender: UnitProfile,
    *,
    mode: str,
    edition: str,
) -> BattleAction:
    result = evaluate_battlefield_attack(state, actor, target, attacker, defender, mode=mode, edition=edition)
    return_fire = 0.0
    if mode == "ranged":
        return_fire = evaluate_battlefield_attack(state, target, actor, defender, attacker, mode="ranged", edition=edition)["damage"]
    objective_bonus = nearest_objective_bonus(state, actor)
    score = result["damage"] * 10.0 - return_fire * 3.5 + objective_bonus
    distance_label = distance(actor.x, actor.y, target.x, target.y)
    return BattleAction(
        id=f"{actor.instance_id}:{mode}:{target.instance_id}",
        type="shoot" if mode == "ranged" else "fight",
        side=actor.side,
        actor_id=actor.instance_id,
        target_id=target.instance_id,
        score=round(score, 4),
        reason=(
            f"Attack {target.name} at {distance_label:.1f}\"; expected {result['damage']:.2f} damage"
            f" with {return_fire:.2f} expected return damage."
        ),
        expected_damage=result["damage"],
        expected_return_damage=return_fire,
        objective_value=objective_bonus,
        assumptions=result["assumptions"],
    )


def evaluate_battlefield_attack(
    state: BattleState,
    actor: BattleUnit,
    target: BattleUnit,
    attacker: UnitProfile,
    defender: UnitProfile,
    *,
    mode: str,
    edition: str,
) -> Dict[str, Any]:
    context = context_for_attack(state, actor, target)
    result = evaluate_unit(attacker, defender, mode, context=context, edition=edition)  # type: ignore[arg-type]
    models_before = target.models_remaining
    return {
        "damage": float(result.total_damage),
        "models_before": models_before,
        "context": {
            "target_in_cover": context.target_in_cover,
            "target_within_half_range": context.target_within_half_range,
            "target_model_count": context.target_model_count,
        },
        "assumptions": MVP_ASSUMPTIONS[:2] + ([MVP_ASSUMPTIONS[2]] if mode == "melee" else []),
    }


def context_for_attack(state: BattleState, actor: BattleUnit, target: BattleUnit) -> EngagementContext:
    dist = distance(actor.x, actor.y, target.x, target.y)
    return EngagementContext(
        attacker_moved=False,
        attacker_advanced=False,
        target_within_half_range=dist <= 12,
        target_in_cover=is_in_cover(state.map, target),
        target_model_count=max(1, target.models_remaining),
    )


def score_objectives_for_side(state: BattleState, side: str, units_by_id: Dict[str, UnitProfile]) -> int:
    total = 0
    for objective in state.map.objectives:
        controller = objective_controller(state, objective, units_by_id)
        if controller == side:
            total += objective.points
    return total


def objective_controller(state: BattleState, objective: Objective, units_by_id: Dict[str, UnitProfile]) -> Optional[str]:
    control: Dict[str, float] = {"red": 0.0, "blue": 0.0}
    for unit in live_units(state):
        if distance(unit.x, unit.y, objective.x, objective.y) <= objective.radius + unit.radius:
            profile = units_by_id.get(unit.unit_id)
            control[unit.side] += objective_control_value(unit, profile)
    if control["red"] == control["blue"]:
        return None
    return "red" if control["red"] > control["blue"] else "blue"


def objective_action_value(
    state: BattleState,
    actor: BattleUnit,
    profile: UnitProfile,
    objective: Objective,
    destination: Dict[str, float],
) -> float:
    before = distance(actor.x, actor.y, objective.x, objective.y)
    after = distance(destination["x"], destination["y"], objective.x, objective.y)
    control_bonus = objective.points * min(2.0, objective_control_value(actor, profile) / 5.0) if after <= objective.radius + actor.radius else 0
    return round(max(0.0, before - after) * 0.9 + control_bonus, 4)


def nearest_objective_bonus(state: BattleState, actor: BattleUnit) -> float:
    objective = nearest_objective(state.map.objectives, actor.x, actor.y)
    if objective is None:
        return 0.0
    dist = distance(actor.x, actor.y, objective.x, objective.y)
    return max(0.0, 6.0 - dist) * 0.4


def default_radius(unit: UnitProfile) -> float:
    models = default_models(unit)
    return round(max(1.0, min(6.0, math.sqrt(models) * 0.85)), 2)


def default_models(unit: UnitProfile) -> int:
    if unit.models_min and unit.models_max:
        return max(1, round((unit.models_min + unit.models_max) / 2))
    if unit.models_min:
        return max(1, unit.models_min)
    if unit.models_max:
        return max(1, unit.models_max)
    return 1


def movement_allowance(unit: UnitProfile) -> float:
    return float(unit.move or 6.0)


def movement_allowance_for_unit(battle_map: BattleMap, actor: BattleUnit, unit: UnitProfile) -> Tuple[float, List[str]]:
    base = movement_allowance(unit)
    penalty = max(
        (
            feature.movement_penalty
            for feature in battle_map.terrain
            if feature.movement_penalty
            and feature.x - actor.radius <= actor.x <= feature.x + feature.width + actor.radius
            and feature.y - actor.radius <= actor.y <= feature.y + feature.height + actor.radius
        ),
        default=0.0,
    )
    if penalty <= 0:
        return base, []
    adjusted = max(1.0, base - penalty)
    return adjusted, [f"Terrain movement penalty: -{penalty:g}\" from current terrain."]


def objective_control_value(unit: BattleUnit, profile: Optional[UnitProfile]) -> float:
    objective_control = profile.objective_control if profile and profile.objective_control is not None else 1
    return max(0.0, float(objective_control) * max(0, unit.models_remaining))


def live_units(state: BattleState) -> List[BattleUnit]:
    return [unit for unit in state.units if unit.models_remaining > 0 and "destroyed" not in unit.status_flags]


def unit_by_instance(state: BattleState, instance_id: str) -> Optional[BattleUnit]:
    return next((unit for unit in state.units if unit.instance_id == instance_id), None)


def deployment_zone_for_side(battle_map: BattleMap, side: str):
    return next((zone for zone in battle_map.deployment_zones if zone.side == side), None)


def nearest_objective(objectives: Iterable[Objective], x: float, y: float) -> Optional[Objective]:
    return min(objectives, key=lambda objective: distance(x, y, objective.x, objective.y), default=None)


def step_towards(x1: float, y1: float, x2: float, y2: float, max_distance: float) -> Dict[str, float]:
    dist = distance(x1, y1, x2, y2)
    if dist <= max_distance or dist == 0:
        return {"x": round(x2, 2), "y": round(y2, 2)}
    ratio = max_distance / dist
    return {"x": round(x1 + (x2 - x1) * ratio, 2), "y": round(y1 + (y2 - y1) * ratio, 2)}


def charge_probability(actor: BattleUnit, target: BattleUnit) -> float:
    required = max(2.0, distance(actor.x, actor.y, target.x, target.y) - actor.radius - target.radius)
    if required <= 3:
        return 0.85
    if required <= 6:
        return 0.58
    if required <= 9:
        return 0.28
    return 0.12


def is_in_cover(battle_map: BattleMap, unit: BattleUnit) -> bool:
    return any(
        feature.grants_cover
        and feature.x - unit.radius <= unit.x <= feature.x + feature.width + unit.radius
        and feature.y - unit.radius <= unit.y <= feature.y + feature.height + unit.radius
        for feature in battle_map.terrain
    )


def in_bounds(battle_map: BattleMap, x: float, y: float, radius: float) -> bool:
    return radius <= x <= battle_map.width - radius and radius <= y <= battle_map.height - radius


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def state_summary(state: BattleState, units_by_id: Dict[str, UnitProfile]) -> Dict[str, Any]:
    return {
        "turn": state.turn,
        "phase": state.phase,
        "active_side": state.active_side,
        "score": state.score,
        "units": [
            {
                **to_dict(unit),
                "profile": unit_summary(units_by_id[unit.unit_id]) if unit.unit_id in units_by_id else None,
            }
            for unit in state.units
        ],
    }
