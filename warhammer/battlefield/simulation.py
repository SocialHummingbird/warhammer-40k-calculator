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
    TerrainFeature,
    action_from_dict,
    army_from_dict,
    map_from_dict,
    state_from_dict,
    to_dict,
)

ADVANCE_EXPECTED_ROLL = 3.5

BASE_TYPE_DIMENSIONS_MM: Dict[str, Tuple[float, float]] = {
    "small_flying_base": (32.0, 32.0),
    "large_flying_base": (60.0, 60.0),
}
BASE_TYPE_RADIUS_INCHES: Dict[str, float] = {
    "hull": 2.8,
    "unique": 2.8,
}

MVP_ASSUMPTIONS = [
    "Battlefield mode uses circular unit blobs and centre-to-centre range.",
    "Line of sight is approximated from terrain bounding boxes; varied terrain shapes are visual in the MVP.",
    "Terrain storeys are recorded for planning display, but vertical movement and firing lanes are simplified.",
    "Charge and fight resolution use expected values and simplified engagement distance.",
]

BATTLE_PHASES = ["movement", "shooting", "charge", "fight", "scoring"]


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
    phase_value = str(state.phase or "").lower()
    if not isinstance(state.turn, int) or state.turn < 1:
        errors.append("Battle turn must be a positive integer.")
    if state.active_side not in {"red", "blue"}:
        errors.append(f"Battle active side must be red or blue, not {state.active_side}.")
    if phase_value not in {*BATTLE_PHASES, "battlefield_ai"}:
        errors.append(f"Battle phase {state.phase} is not supported.")
    score = state.score if isinstance(state.score, dict) else {}
    if not isinstance(state.score, dict):
        errors.append("Battle score must include red and blue numeric values.")
    for side in ("red", "blue"):
        if side not in score:
            errors.append(f"Battle score is missing {side}.")
            continue
        try:
            side_score = float(score[side])
        except (TypeError, ValueError):
            errors.append(f"Battle score for {side} must be numeric.")
            continue
        if side_score < 0:
            errors.append(f"Battle score for {side} cannot be negative.")
    map_validation = validate_map(state.map)
    errors.extend(map_validation["errors"])
    warnings.extend(map_validation["warnings"])
    seen_ids: set[str] = set()
    for unit in state.units:
        if not unit.instance_id:
            errors.append(f"{unit.name} is missing a battlefield unit id.")
        if unit.instance_id in seen_ids:
            errors.append(f"Duplicate battlefield unit id {unit.instance_id}.")
        seen_ids.add(unit.instance_id)
        if unit.unit_id not in units_by_id:
            errors.append(f"{unit.name} has unknown unit id {unit.unit_id}.")
        if unit.radius <= 0:
            errors.append(f"{unit.name} must have a positive footprint radius.")
        if not in_bounds(state.map, unit.x, unit.y, unit.radius):
            errors.append(f"{unit.name} is outside the battlefield.")
        if unit.side not in {"red", "blue"}:
            errors.append(f"{unit.name} has invalid side {unit.side}.")
        profile = units_by_id.get(unit.unit_id)
        if profile and not profile.weapons:
            warnings.append(f"{profile.name} has no imported weapons.")
    live = live_units(state)
    for index, unit in enumerate(live):
        for other in live[index + 1 :]:
            if units_overlap(unit, other):
                errors.append(f"{unit.name} overlaps {other.name}; move one blob so footprints do not overlap.")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "assumptions": MVP_ASSUMPTIONS,
        "summary": battle_summary(state, units_by_id),
        "state": to_dict(state),
    }


def validate_map(battle_map: BattleMap) -> Dict[str, List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if battle_map.width <= 0 or battle_map.height <= 0:
        errors.append("Battle map dimensions must be positive.")
    if not battle_map.deployment_zones:
        errors.append("Battle map must include deployment zones.")
    if not any(zone.side == "red" for zone in battle_map.deployment_zones):
        errors.append("Battle map is missing a red deployment zone.")
    if not any(zone.side == "blue" for zone in battle_map.deployment_zones):
        errors.append("Battle map is missing a blue deployment zone.")
    if not battle_map.objectives:
        warnings.append("Battle map has no objectives; scoring actions will not be available.")

    for zone in battle_map.deployment_zones:
        zone_label = zone.id or f"{zone.side} deployment zone"
        if zone.width <= 0 or zone.height <= 0:
            errors.append(f"Deployment zone {zone_label} must have positive width and height.")
        if zone.side not in {"red", "blue"}:
            errors.append(f"Deployment zone {zone_label} has invalid side {zone.side}.")
        if not rectangle_in_bounds(battle_map, zone.x, zone.y, zone.width, zone.height):
            errors.append(f"Deployment zone {zone_label} is outside the battlefield.")

    for feature in battle_map.terrain:
        if feature.width <= 0 or feature.height <= 0:
            errors.append(f"Terrain feature {feature.name or feature.id} must have positive width and height.")
        if not rectangle_in_bounds(battle_map, feature.x, feature.y, feature.width, feature.height):
            errors.append(f"Terrain feature {feature.name or feature.id} is outside the battlefield.")
        if feature.movement_penalty < 0:
            errors.append(f"Terrain feature {feature.name or feature.id} has an invalid negative movement penalty.")
        if feature.stories < 1:
            errors.append(f"Terrain feature {feature.name or feature.id} must have at least one storey.")

    for objective in battle_map.objectives:
        if objective.radius <= 0:
            errors.append(f"Objective {objective.name or objective.id} must have a positive radius.")
        if objective.points < 0:
            errors.append(f"Objective {objective.name or objective.id} has invalid negative points.")
        if not circle_in_bounds(battle_map, objective.x, objective.y, objective.radius):
            errors.append(f"Objective {objective.name or objective.id} is outside the battlefield.")
    return {"errors": errors, "warnings": warnings}


def available_actions(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e") -> List[BattleAction]:
    actions: List[BattleAction] = []
    phase = normalized_phase(state.phase)
    active_units = [unit for unit in live_units(state) if unit.side == state.active_side]
    actionable_units = [unit for unit in active_units if not unit_acted_this_phase(state, unit.instance_id)]
    enemies = [unit for unit in live_units(state) if unit.side != state.active_side]
    controlled = controlled_objectives_for_side(state, state.active_side, units_by_id)
    if controlled and actionable_units and not side_scored_this_turn(state, state.active_side):
        actor = scoring_actor_for_objectives(actionable_units, controlled)
        gained = sum(objective.points for objective in controlled)
        actions.append(
            BattleAction(
                id=f"{state.active_side}:score:{state.turn}",
                type="score",
                side=state.active_side,
                actor_id=actor.instance_id,
                score=float(gained * 8),
                objective_value=float(gained),
                reason=(
                    f"Score {gained} VP from controlled objectives: "
                    f"{', '.join(objective.name for objective in controlled)}."
                ),
                assumptions=[
                    "Objective scoring uses Objective Control from imported profiles.",
                    "A side can take one explicit score action per turn in Battlefield mode.",
                ],
            )
        )
    for actor in actionable_units:
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

        engaged_enemy = nearest_engaged_enemy(state, actor)
        if engaged_enemy is not None:
            move_allowance, move_notes = movement_allowance_for_unit(state.map, actor, profile)
            dest, fallback_notes = fall_back_destination(state, actor, engaged_enemy, move_allowance)
            actions.append(
                BattleAction(
                    id=f"{actor.instance_id}:fall_back:{engaged_enemy.instance_id}",
                    type="fall_back",
                    side=actor.side,
                    actor_id=actor.instance_id,
                    destination=dest,
                    score=4.0 + attack_distance(actor, engaged_enemy),
                    reason=(
                        f"Fall back from {engaged_enemy.name} using {move_allowance:.1f}\" movement; "
                        "this prevents shooting and charging later this turn in Battlefield mode."
                    ),
                    assumptions=MVP_ASSUMPTIONS[:1] + move_notes + fallback_notes,
                )
            )

        objective = nearest_objective(state.map.objectives, actor.x, actor.y)
        if objective is not None and engaged_enemy is None:
            move_allowance, move_notes = movement_allowance_for_unit(state.map, actor, profile)
            dest = step_towards(actor.x, actor.y, objective.x, objective.y, move_allowance)
            dest, collision_notes = non_overlapping_destination(state, actor, dest["x"], dest["y"])
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
                    assumptions=MVP_ASSUMPTIONS[:1] + move_notes + collision_notes,
                )
            )
            advance_allowance, advance_notes = advance_allowance_for_unit(state.map, actor, profile)
            advance_dest = step_towards(actor.x, actor.y, objective.x, objective.y, advance_allowance)
            advance_dest, advance_collision_notes = non_overlapping_destination(state, actor, advance_dest["x"], advance_dest["y"])
            advance_value = objective_action_value(state, actor, profile, objective, advance_dest)
            actions.append(
                BattleAction(
                    id=f"{actor.instance_id}:advance:{objective.id}",
                    type="advance",
                    side=actor.side,
                    actor_id=actor.instance_id,
                    destination=advance_dest,
                    score=advance_value + 0.4,
                    objective_value=advance_value,
                    reason=(
                        f"Advance toward {objective.name} using {advance_allowance:.1f}\" expected movement; "
                        "this improves board position but prevents charging later this turn."
                    ),
                    assumptions=MVP_ASSUMPTIONS[:1] + advance_notes + advance_collision_notes,
                )
            )

        for target in enemies:
            target_profile = units_by_id.get(target.unit_id)
            if target_profile is None:
                continue
            if (
                not unit_engaged_with_enemy(state, actor)
                and not unit_fell_back_this_turn(state, actor.instance_id)
                and attack_distance(actor, target) <= ranged_attack_reach(profile)
            ):
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
            if (
                not unit_fell_back_this_turn(state, actor.instance_id)
                and not unit_advanced_this_turn(state, actor.instance_id)
                and distance(actor.x, actor.y, target.x, target.y) <= 12 + actor.radius + target.radius
            ):
                melee = score_combat_action(
                    state,
                    actor,
                    target,
                    profile,
                    target_profile,
                    mode="melee",
                    edition=edition,
                )
                if phase == "fight" and attack_distance(actor, target) <= 1.0:
                    melee.type = "fight"
                    melee.id = f"{actor.instance_id}:fight:{target.instance_id}"
                    melee.reason = f"Fight {target.name} in engagement range for {melee.expected_damage:.2f} expected damage."
                elif unit_engaged_with_enemy(state, actor):
                    continue
                else:
                    melee.type = "charge"
                    melee.id = f"{actor.instance_id}:charge:{target.instance_id}"
                    probability = charge_probability(actor, target)
                    full_damage = melee.expected_damage
                    melee.expected_damage *= probability
                    melee.reason = (
                        f"Attempt a simplified charge into {target.name}; {probability:.0%} charge probability "
                        f"for {melee.expected_damage:.2f} expected damage ({full_damage:.2f} if it connects)."
                    )
                    melee.assumptions = MVP_ASSUMPTIONS
                    melee.score *= probability
                actions.append(melee)
    return sorted(
        [action for action in actions if action_allowed_in_phase(action, phase)],
        key=lambda action: (-action.score, action.id),
    )


def unavailable_actions(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e") -> List[Dict[str, Any]]:
    phase = normalized_phase(state.phase)
    diagnostics: List[Dict[str, Any]] = []
    active_units = [unit for unit in live_units(state) if unit.side == state.active_side]
    enemies = [unit for unit in live_units(state) if unit.side != state.active_side]

    if phase == "scoring":
        controlled = controlled_objectives_for_side(state, state.active_side, units_by_id)
        if side_scored_this_turn(state, state.active_side):
            diagnostics.append(
                unavailable_action_row(
                    state.active_side,
                    "score",
                    phase,
                    "This side has already scored objectives this turn.",
                )
            )
        elif not controlled:
            diagnostics.append(
                unavailable_action_row(
                    state.active_side,
                    "score",
                    phase,
                    "No objectives are currently controlled by the active side.",
                )
            )

    for actor in active_units:
        profile = units_by_id.get(actor.unit_id)
        if unit_acted_this_phase(state, actor.instance_id):
            diagnostics.append(
                unavailable_action_row(
                    actor.side,
                    "any",
                    phase,
                    f"{actor.name} has already acted in the {phase} phase.",
                    actor=actor,
                )
            )
            continue
        if profile is None:
            diagnostics.append(
                unavailable_action_row(
                    actor.side,
                    "any",
                    phase,
                    f"{actor.name} has no loaded unit profile.",
                    actor=actor,
                )
            )
            continue

        engaged_enemy = nearest_engaged_enemy(state, actor)
        if phase == "movement":
            if engaged_enemy is None:
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "fall_back",
                        phase,
                        f"{actor.name} is not engaged, so it cannot fall back.",
                        actor=actor,
                    )
                )
            else:
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "move",
                        phase,
                        f"{actor.name} is engaged with {engaged_enemy.name}; use fall back instead of a normal move.",
                        actor=actor,
                    )
                )
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "advance",
                        phase,
                        f"{actor.name} is engaged with {engaged_enemy.name}; use fall back instead of advancing.",
                        actor=actor,
                    )
                )
        elif phase == "shooting":
            if engaged_enemy is not None:
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "shoot",
                        phase,
                        f"{actor.name} is engaged with {engaged_enemy.name} and cannot make a normal shooting action.",
                        actor=actor,
                    )
                )
            elif unit_fell_back_this_turn(state, actor.instance_id):
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "shoot",
                        phase,
                        f"{actor.name} fell back this turn and cannot shoot.",
                        actor=actor,
                    )
                )
            elif not enemies:
                diagnostics.append(
                    unavailable_action_row(actor.side, "shoot", phase, "There are no live enemy units to target.", actor=actor)
                )
            elif ranged_attack_reach(profile) <= 0:
                diagnostics.append(
                    unavailable_action_row(actor.side, "shoot", phase, f"{actor.name} has no imported ranged weapon profile.", actor=actor)
                )
            elif all(attack_distance(actor, target) > ranged_attack_reach(profile) for target in enemies):
                diagnostics.append(
                    unavailable_action_row(actor.side, "shoot", phase, f"No live enemy unit is within {ranged_attack_reach(profile):.0f}\" tactical range.", actor=actor)
                )
        elif phase == "charge":
            if engaged_enemy is not None:
                diagnostics.append(
                    unavailable_action_row(
                        actor.side,
                        "charge",
                        phase,
                        f"{actor.name} is already engaged with {engaged_enemy.name}; fight in the Fight phase instead.",
                        actor=actor,
                    )
                )
            elif unit_fell_back_this_turn(state, actor.instance_id):
                diagnostics.append(
                    unavailable_action_row(actor.side, "charge", phase, f"{actor.name} fell back this turn and cannot charge.", actor=actor)
                )
            elif unit_advanced_this_turn(state, actor.instance_id):
                diagnostics.append(
                    unavailable_action_row(actor.side, "charge", phase, f"{actor.name} advanced this turn and cannot charge.", actor=actor)
                )
            elif not enemies:
                diagnostics.append(
                    unavailable_action_row(actor.side, "charge", phase, "There are no live enemy units to charge.", actor=actor)
                )
            elif all(attack_distance(actor, target) > 12.0 for target in enemies):
                diagnostics.append(
                    unavailable_action_row(actor.side, "charge", phase, "No live enemy unit is within 12 inches for a charge.", actor=actor)
                )
        elif phase == "fight":
            if not any(attack_distance(actor, target) <= 1.0 for target in enemies):
                diagnostics.append(
                    unavailable_action_row(actor.side, "fight", phase, f"{actor.name} has no enemy unit in engagement range.", actor=actor)
                )
    return diagnostics


def unavailable_action_row(
    side: str,
    action_type: str,
    phase: str,
    reason: str,
    *,
    actor: Optional[BattleUnit] = None,
) -> Dict[str, Any]:
    return {
        "side": side,
        "phase": phase,
        "type": action_type,
        "actor_id": actor.instance_id if actor else None,
        "actor": actor.name if actor else None,
        "reason": reason,
    }


def normalized_phase(phase: str) -> str:
    value = str(phase or "movement").lower()
    return value if value in {*BATTLE_PHASES, "battlefield_ai"} else "movement"


def action_allowed_in_phase(action: BattleAction, phase: str) -> bool:
    if action.type == "hold" or phase == "battlefield_ai":
        return True
    phase_actions = {
        "movement": {"move", "advance", "fall_back"},
        "shooting": {"shoot"},
        "charge": {"charge"},
        "fight": {"fight"},
        "scoring": {"score"},
    }
    return action.type in phase_actions.get(phase, {"move"})


def ai_plan(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e", limit: int = 8) -> Dict[str, Any]:
    actions = available_actions(state, units_by_id, edition=edition)
    return {
        "actions": [to_dict(action) for action in actions[: max(1, limit)]],
        "assumptions": MVP_ASSUMPTIONS,
        "summary": battle_summary(state, units_by_id),
    }


def advance_phase(state: BattleState) -> BattleState:
    next_state = copy.deepcopy(state)
    phase = normalized_phase(next_state.phase)
    if phase == "battlefield_ai":
        phase = "movement"
    phase_index = BATTLE_PHASES.index(phase) if phase in BATTLE_PHASES else 0
    if phase_index < len(BATTLE_PHASES) - 1:
        next_state.phase = BATTLE_PHASES[phase_index + 1]
    elif next_state.active_side == "red":
        next_state.active_side = "blue"
        next_state.phase = "movement"
    else:
        next_state.active_side = "red"
        next_state.phase = "movement"
        next_state.turn += 1
    next_state.log.append(
        {
            "turn": next_state.turn,
            "phase": next_state.phase,
            "side": next_state.active_side,
            "action": "advance_phase",
            "reason": f"Advance to {next_state.active_side} {next_state.phase} phase.",
        }
    )
    return next_state


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
    validate_action_timing(next_state, action, actor)

    log_entry: Dict[str, Any] = {
        "turn": next_state.turn,
        "phase": next_state.phase,
        "side": actor.side,
        "actor_id": actor.instance_id,
        "actor": actor.name,
        "action": action.type,
        "reason": action.reason,
        "assumptions": action.assumptions or MVP_ASSUMPTIONS[:1],
    }
    damage = 0.0
    points_removed = 0.0
    score_delta: Dict[str, int] = {}

    if action.type in {"move", "advance", "fall_back"} and action.destination:
        profile = units_by_id.get(actor.unit_id)
        if profile is None:
            raise ValueError("Action references unknown unit profile")
        extra_allowance = ADVANCE_EXPECTED_ROLL if action.type == "advance" else 0.0
        extra_notes = (
            [f"Advance movement uses an expected D6 roll of {ADVANCE_EXPECTED_ROLL:.1f}\"."]
            if action.type == "advance"
            else []
        )
        range_limited, range_notes = movement_limited_destination(
            next_state,
            actor,
            profile,
            float(action.destination["x"]),
            float(action.destination["y"]),
            extra_allowance=extra_allowance,
            extra_notes=extra_notes,
        )
        destination, collision_notes = non_overlapping_destination(
            next_state,
            actor,
            range_limited["x"],
            range_limited["y"],
        )
        actor.x = destination["x"]
        actor.y = destination["y"]
        log_entry["destination"] = {"x": round(actor.x, 2), "y": round(actor.y, 2)}
        actor.status_flags = sorted(set(actor.status_flags + [moved_flag(next_state.turn)]))
        log_entry["status_flags"] = actor.status_flags
        if action.type == "advance":
            actor.status_flags = sorted(set(actor.status_flags + [advanced_flag(next_state.turn)]))
            log_entry["status_flags"] = actor.status_flags
            log_entry["assumptions"] = list(log_entry["assumptions"]) + [
                "Advancing prevents this unit from charging later in the same turn.",
                "Ranged attacks after advancing are resolved through the calculator's attacker_advanced context.",
            ]
        if action.type == "fall_back":
            actor.status_flags = sorted(set(actor.status_flags + [fall_back_flag(next_state.turn)]))
            log_entry["status_flags"] = actor.status_flags
            log_entry["assumptions"] = list(log_entry["assumptions"]) + [
                "Falling back prevents this unit from shooting or charging later in the same turn."
            ]
        if range_notes or collision_notes:
            log_entry["assumptions"] = list(log_entry["assumptions"]) + range_notes + collision_notes
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
        if action.type == "charge":
            probability = charge_probability(actor, target)
            result["context"]["charge_probability"] = probability
            result["context"]["full_melee_damage_if_charge_connects"] = result["damage"]
            result["context"]["expected_followup_fight_damage"] = result["damage"] * probability
            result["assumptions"] = list(result["assumptions"]) + [
                "Charge resolution moves the unit into engagement range; melee damage is resolved in the Fight phase.",
                f"AI scoring still values the charge using {probability:.0%} simplified charge probability for follow-up fight damage.",
            ]
            damage = 0.0
        target.wounds_remaining = max(0.0, target.wounds_remaining - damage)
        target.models_remaining = max(0, math.ceil(target.wounds_remaining / max(1, defender.wounds)))
        ppm = points_per_model(defender) or 0.0
        points_removed = max(0.0, (result["models_before"] - target.models_remaining) * ppm)
        if target.models_remaining <= 0:
            target.status_flags = sorted(set(target.status_flags + ["destroyed"]))
        if action.type == "charge" and target.models_remaining > 0:
            destination, charge_move_notes = charge_engagement_destination(next_state, actor, target)
            actor.x = destination["x"]
            actor.y = destination["y"]
            log_entry["destination"] = {"x": round(actor.x, 2), "y": round(actor.y, 2)}
            result["assumptions"] = list(result["assumptions"]) + charge_move_notes
        log_entry.update(
            {
                "target": target.name,
                "damage": round(damage, 3),
                "models_remaining": target.models_remaining,
                "points_removed": round(points_removed, 2),
                "context": result["context"],
            }
        )
        log_entry["assumptions"] = result["assumptions"]
    elif action.type == "score":
        if side_scored_this_turn(next_state, actor.side):
            gained = 0
            controlled = []
        else:
            controlled = controlled_objectives_for_side(next_state, actor.side, units_by_id)
            gained = sum(objective.points for objective in controlled)
        next_state.score[actor.side] = next_state.score.get(actor.side, 0) + gained
        score_delta[actor.side] = gained
        log_entry["score_delta"] = score_delta
        log_entry["objectives"] = [objective.name for objective in controlled]
    else:
        log_entry["detail"] = "Held position."

    next_state.log.append(log_entry)
    return BattleOutcome(action=action, state=next_state, log_entry=log_entry, damage=damage, points_removed=points_removed, score_delta=score_delta)


def validate_action_timing(state: BattleState, action: BattleAction, actor: BattleUnit) -> None:
    phase = normalized_phase(state.phase)
    if actor.models_remaining <= 0 or "destroyed" in actor.status_flags:
        raise ValueError(f"{actor.name} cannot act because it has no live models.")
    if action.side and action.side != actor.side:
        raise ValueError(f"Action side {action.side} does not match actor side {actor.side}.")
    if phase != "battlefield_ai" and actor.side != state.active_side:
        raise ValueError(f"{actor.name} cannot act during {state.active_side}'s turn.")
    if not action_allowed_in_phase(action, phase):
        raise ValueError(f"{action.type} actions are not available in the {phase} phase.")
    if unit_acted_this_phase(state, actor.instance_id):
        raise ValueError(f"{actor.name} has already acted in the {phase} phase.")
    if action.type in {"move", "advance", "fall_back"} and not action.destination:
        raise ValueError(f"{action.type} actions require a destination.")
    if action.type in {"move", "advance"} and unit_engaged_with_enemy(state, actor):
        raise ValueError(f"{actor.name} cannot {action.type} while engaged; fall back instead.")
    if action.type == "fall_back" and nearest_engaged_enemy(state, actor) is None:
        raise ValueError(f"{actor.name} can only fall back while engaged with an enemy unit.")
    if action.type in {"shoot", "charge"} and unit_fell_back_this_turn(state, actor.instance_id):
        raise ValueError(f"{actor.name} cannot {action.type} after falling back this turn.")
    if action.type == "charge" and unit_advanced_this_turn(state, actor.instance_id):
        raise ValueError(f"{actor.name} cannot charge after advancing this turn.")
    if action.type == "shoot" and unit_engaged_with_enemy(state, actor):
        raise ValueError(f"{actor.name} cannot make a normal shooting action while engaged.")
    if action.type == "charge" and unit_engaged_with_enemy(state, actor):
        raise ValueError(f"{actor.name} cannot charge while already engaged.")
    if action.type in {"shoot", "charge", "fight"}:
        if not action.target_id:
            raise ValueError(f"{action.type} actions require a target.")
        target = unit_by_instance(state, action.target_id)
        if target is None:
            raise ValueError(f"Unknown target {action.target_id}.")
        if target.side == actor.side:
            raise ValueError(f"{actor.name} cannot target a friendly unit.")
        if target.models_remaining <= 0 or "destroyed" in target.status_flags:
            raise ValueError(f"{actor.name} cannot target {target.name} because it has no live models.")
        if action.type == "fight" and attack_distance(actor, target) > 1.0:
            raise ValueError(f"{actor.name} can only fight targets within engagement range.")
        if action.type == "charge" and attack_distance(actor, target) > 12.0:
            raise ValueError(f"{actor.name} cannot charge a target more than 12 inches away.")


def autoplay_turn(state: BattleState, units_by_id: Dict[str, UnitProfile], *, edition: str = "10e") -> Dict[str, Any]:
    next_state = copy.deepcopy(state)
    replay: List[Dict[str, Any]] = []
    completed_turns = 0
    if battle_complete(next_state):
        return {
            "state": to_dict(next_state),
            "replay": replay,
            "assumptions": MVP_ASSUMPTIONS,
            "completed_turns": completed_turns,
            "battle_complete": True,
            "winner": battle_winner(next_state),
            "summary": battle_summary(next_state, units_by_id),
        }
    for side in ("red", "blue"):
        if battle_complete(next_state):
            break
        next_state.active_side = side
        for phase in BATTLE_PHASES:
            if battle_complete(next_state):
                break
            next_state.phase = phase
            actors = [unit for unit in live_units(next_state) if unit.side == side]
            for actor in actors:
                if battle_complete(next_state):
                    break
                plan_actions = [
                    action
                    for action in available_actions(next_state, units_by_id, edition=edition)
                    if action.actor_id == actor.instance_id
                ]
                if not plan_actions:
                    continue
                chosen = plan_actions[0]
                if chosen.type == "hold" and any(action.type != "hold" for action in plan_actions):
                    chosen = next(action for action in plan_actions if action.type != "hold")
                if chosen.type == "hold":
                    continue
                outcome = resolve_action(next_state, chosen, units_by_id, edition=edition)
                next_state = outcome.state
                replay.append({"chosen": to_dict(chosen), "outcome": outcome.log_entry})
                if battle_complete(next_state):
                    completion_entry = battle_completion_log_entry(next_state)
                    next_state.log.append(completion_entry)
                    replay.append({"chosen": None, "outcome": completion_entry})
                    break
                if phase == "scoring" and chosen.type == "score":
                    break
    completed_turns = 1
    if not battle_complete(next_state):
        next_state.turn += 1
        next_state.phase = "movement"
        next_state.active_side = "red"
    return {
        "state": to_dict(next_state),
        "replay": replay,
        "assumptions": MVP_ASSUMPTIONS,
        "completed_turns": completed_turns,
        "battle_complete": battle_complete(next_state),
        "winner": battle_winner(next_state),
        "summary": battle_summary(next_state, units_by_id),
    }


def autoplay_battle(
    state: BattleState,
    units_by_id: Dict[str, UnitProfile],
    *,
    edition: str = "10e",
    turns: int = 5,
) -> Dict[str, Any]:
    next_state = copy.deepcopy(state)
    replay: List[Dict[str, Any]] = []
    completed_turns = 0
    max_turns = max(1, min(20, int(turns or 1)))
    for _ in range(max_turns):
        if battle_complete(next_state):
            break
        turn_payload = autoplay_turn(next_state, units_by_id, edition=edition)
        next_state = state_from_dict(turn_payload["state"])
        replay.extend(turn_payload.get("replay") or [])
        completed_turns += int(turn_payload.get("completed_turns") or 0)
    return {
        "state": to_dict(next_state),
        "replay": replay,
        "assumptions": MVP_ASSUMPTIONS,
        "completed_turns": completed_turns,
        "battle_complete": battle_complete(next_state),
        "winner": battle_winner(next_state),
        "summary": battle_summary(next_state, units_by_id),
    }


def battle_complete(state: BattleState) -> bool:
    live_sides = {unit.side for unit in live_units(state)}
    return "red" not in live_sides or "blue" not in live_sides


def battle_winner(state: BattleState) -> Optional[str]:
    live_sides = {unit.side for unit in live_units(state)}
    if live_sides == {"red"}:
        return "red"
    if live_sides == {"blue"}:
        return "blue"
    return None


def battle_completion_log_entry(state: BattleState) -> Dict[str, Any]:
    winner = battle_winner(state)
    reason = f"{winner.title()} wins; opposing side has no live battlefield units remaining." if winner else "Battle ended with no live battlefield units remaining."
    return {
        "turn": state.turn,
        "phase": state.phase,
        "side": winner or state.active_side,
        "action": "battle_complete",
        "winner": winner,
        "reason": reason,
    }


def battle_summary(state: BattleState, units_by_id: Dict[str, UnitProfile]) -> Dict[str, Any]:
    red_live = len([unit for unit in live_units(state) if unit.side == "red"])
    blue_live = len([unit for unit in live_units(state) if unit.side == "blue"])
    red_score = score_for_side(state, "red")
    blue_score = score_for_side(state, "blue")
    red_points = remaining_points_for_side(state, units_by_id, "red")
    blue_points = remaining_points_for_side(state, units_by_id, "blue")
    complete = battle_complete(state)
    winner = battle_winner(state)
    leading_side: Optional[str] = winner
    basis = "wipeout" if complete else "even"
    margin = 0.0

    if winner:
        reason = f"{winner.title()} wins because the opposing side has no live battlefield units remaining."
    elif complete:
        reason = "Battle is complete with no live units remaining on either side."
    elif red_score != blue_score:
        leading_side = "red" if red_score > blue_score else "blue"
        basis = "vp"
        margin = float(abs(red_score - blue_score))
        reason = f"{leading_side.title()} leads on mission score by {margin:.0f} VP."
    elif abs(red_points - blue_points) > 0.01:
        leading_side = "red" if red_points > blue_points else "blue"
        basis = "points_remaining"
        margin = abs(red_points - blue_points)
        reason = f"{leading_side.title()} leads on remaining army value by {margin:.1f} points."
    else:
        reason = "Battle is currently level on VP and remaining army value."

    return {
        "battle_complete": complete,
        "winner": winner,
        "leading_side": leading_side,
        "basis": basis,
        "margin": round(margin, 3),
        "reason": reason,
        "red": {
            "score": red_score,
            "live_units": red_live,
            "points_remaining": round(red_points, 3),
        },
        "blue": {
            "score": blue_score,
            "live_units": blue_live,
            "points_remaining": round(blue_points, 3),
        },
    }


def score_for_side(state: BattleState, side: str) -> int:
    if not isinstance(state.score, dict):
        return 0
    try:
        return int(state.score.get(side, 0))
    except (TypeError, ValueError):
        return 0


def remaining_points_for_side(state: BattleState, units_by_id: Dict[str, UnitProfile], side: str) -> float:
    total = 0.0
    for unit in state.units:
        if unit.side != side or unit.models_remaining <= 0:
            continue
        profile = units_by_id.get(unit.unit_id)
        if profile is None:
            continue
        total += (points_per_model(profile) or 0.0) * unit.models_remaining
    return total


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
    if mode == "ranged" and attack_distance(target, actor) <= ranged_attack_reach(defender):
        return_fire = evaluate_battlefield_attack(state, target, actor, defender, attacker, mode="ranged", edition=edition)["damage"]
    objective_bonus = nearest_objective_bonus(state, actor)
    score = result["damage"] * 10.0 - return_fire * 3.5 + objective_bonus
    distance_label = attack_distance(actor, target)
    range_label = ""
    if mode == "ranged":
        range_label = f" within {ranged_attack_reach(attacker):.0f}\" tactical range"
    visibility_note = ""
    if result["context"].get("line_of_sight_blocked"):
        terrain = ", ".join(result["context"].get("intervening_terrain") or ["terrain"])
        visibility_note = f" Line of sight is obscured by {terrain}; ranged output is reduced."
    return BattleAction(
        id=f"{actor.instance_id}:{mode}:{target.instance_id}",
        type="shoot" if mode == "ranged" else "fight",
        side=actor.side,
        actor_id=actor.instance_id,
        target_id=target.instance_id,
        score=round(score, 4),
        reason=(
            f"Attack {target.name} at {distance_label:.1f}\"{range_label}; expected {result['damage']:.2f} damage"
            f" with {return_fire:.2f} expected return damage.{visibility_note}"
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
    visibility = visibility_for_attack(state.map, actor, target)
    reach = ranged_attack_reach(attacker) if mode == "ranged" else 1.0
    current_attack_distance = attack_distance(actor, target)
    attack_in_range = mode != "ranged" or current_attack_distance <= reach
    half_range = max(0.0, reach / 2.0) if mode == "ranged" else 12.0
    context = context_for_attack(state, actor, target, visibility=visibility, half_range=half_range)
    result = evaluate_unit(attacker, defender, mode, context=context, edition=edition)  # type: ignore[arg-type]
    damage_multiplier = visibility["damage_multiplier"] if mode == "ranged" else 1.0
    models_before = target.models_remaining
    assumptions = MVP_ASSUMPTIONS[:2] + ([MVP_ASSUMPTIONS[2]] if mode == "melee" else [])
    if mode == "ranged":
        assumptions.extend(ranged_attack_assumptions(attacker))
    if mode == "ranged" and not attack_in_range:
        assumptions.append(
            f"Target is {current_attack_distance:.1f}\" away after footprints; no ranged weapon is assumed to reach beyond {reach:.1f}\"."
        )
    if mode == "ranged" and visibility["line_of_sight_blocked"]:
        assumptions.append(
            f"Intervening terrain obscures line of sight; ranged damage is multiplied by {damage_multiplier:.2f}."
        )
    return {
        "damage": (float(result.total_damage) * damage_multiplier) if attack_in_range else 0.0,
        "models_before": models_before,
        "context": {
            "target_in_cover": context.target_in_cover,
            "target_within_half_range": context.target_within_half_range,
            "target_model_count": context.target_model_count,
            "attacker_moved": context.attacker_moved,
            "attacker_advanced": context.attacker_advanced,
            "attack_distance": round(current_attack_distance, 2),
            "weapon_range": round(reach, 2) if mode == "ranged" else None,
            "attack_in_range": attack_in_range,
            "line_of_sight_blocked": visibility["line_of_sight_blocked"],
            "intervening_terrain": visibility["intervening_terrain"],
            "cover_sources": visibility["cover_sources"],
            "damage_multiplier": damage_multiplier,
        },
        "assumptions": assumptions,
    }


def context_for_attack(
    state: BattleState,
    actor: BattleUnit,
    target: BattleUnit,
    *,
    visibility: Optional[Dict[str, Any]] = None,
    half_range: float = 12.0,
) -> EngagementContext:
    dist = attack_distance(actor, target)
    visibility = visibility or visibility_for_attack(state.map, actor, target)
    return EngagementContext(
        attacker_moved=unit_moved_this_turn(state, actor.instance_id),
        attacker_advanced=unit_advanced_this_turn(state, actor.instance_id),
        target_within_half_range=dist <= half_range,
        target_in_cover=bool(visibility["target_in_cover"]),
        target_model_count=max(1, target.models_remaining),
    )


def visibility_for_attack(battle_map: BattleMap, actor: BattleUnit, target: BattleUnit) -> Dict[str, Any]:
    cover_sources: List[str] = []
    intervening_terrain: List[str] = []
    target_cover = is_in_cover(battle_map, target)
    for feature in battle_map.terrain:
        if not segment_intersects_feature(actor.x, actor.y, target.x, target.y, feature):
            continue
        actor_inside = point_in_feature(actor.x, actor.y, feature)
        target_inside = point_in_feature(target.x, target.y, feature)
        if feature.grants_cover and (target_inside or not actor_inside):
            cover_sources.append(feature.name)
        if feature.blocks_line_of_sight and not actor_inside and not target_inside:
            intervening_terrain.append(feature.name)
    blocked = bool(intervening_terrain)
    return {
        "target_in_cover": target_cover or bool(cover_sources),
        "line_of_sight_blocked": blocked,
        "intervening_terrain": sorted(set(intervening_terrain)),
        "cover_sources": sorted(set(cover_sources)),
        "damage_multiplier": 0.25 if blocked else 1.0,
    }


def score_objectives_for_side(state: BattleState, side: str, units_by_id: Dict[str, UnitProfile]) -> int:
    total = 0
    for objective in state.map.objectives:
        controller = objective_controller(state, objective, units_by_id)
        if controller == side:
            total += objective.points
    return total


def controlled_objectives_for_side(state: BattleState, side: str, units_by_id: Dict[str, UnitProfile]) -> List[Objective]:
    return [objective for objective in state.map.objectives if objective_controller(state, objective, units_by_id) == side]


def scoring_actor_for_objectives(active_units: List[BattleUnit], objectives: List[Objective]) -> BattleUnit:
    return min(
        active_units,
        key=lambda unit: (
            min(distance(unit.x, unit.y, objective.x, objective.y) for objective in objectives),
            unit.instance_id,
        ),
    )


def side_scored_this_turn(state: BattleState, side: str) -> bool:
    return any(
        entry.get("turn") == state.turn
        and entry.get("side") == side
        and entry.get("action") == "score"
        and (entry.get("score_delta") or {}).get(side, 0) > 0
        for entry in state.log
    )


def unit_acted_this_phase(state: BattleState, instance_id: str) -> bool:
    phase = normalized_phase(state.phase)
    return any(
        entry.get("turn") == state.turn
        and normalized_phase(str(entry.get("phase") or "")) == phase
        and entry.get("actor_id") == instance_id
        and entry.get("action") != "advance_phase"
        for entry in state.log
    )


def unit_engaged_with_enemy(state: BattleState, actor: BattleUnit) -> bool:
    return any(
        other.side != actor.side and attack_distance(actor, other) <= 1.0
        for other in live_units(state)
        if other.instance_id != actor.instance_id
    )


def nearest_engaged_enemy(state: BattleState, actor: BattleUnit) -> Optional[BattleUnit]:
    engaged = [
        other
        for other in live_units(state)
        if other.side != actor.side and attack_distance(actor, other) <= 1.0
    ]
    return min(engaged, key=lambda other: (attack_distance(actor, other), other.instance_id), default=None)


def unit_fell_back_this_turn(state: BattleState, instance_id: str) -> bool:
    unit = unit_by_instance(state, instance_id)
    return bool(unit and fall_back_flag(state.turn) in unit.status_flags)


def unit_advanced_this_turn(state: BattleState, instance_id: str) -> bool:
    unit = unit_by_instance(state, instance_id)
    return bool(unit and advanced_flag(state.turn) in unit.status_flags)


def unit_moved_this_turn(state: BattleState, instance_id: str) -> bool:
    unit = unit_by_instance(state, instance_id)
    return bool(unit and moved_flag(state.turn) in unit.status_flags)


def fall_back_flag(turn: int) -> str:
    return f"fell_back_turn_{turn}"


def advanced_flag(turn: int) -> str:
    return f"advanced_turn_{turn}"


def moved_flag(turn: int) -> str:
    return f"moved_turn_{turn}"


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
    dimensions = footprint_dimensions_mm(unit)
    if dimensions:
        return radius_from_base_dimensions(models, *dimensions)
    base_type = getattr(unit, "base_type", None)
    if base_type in BASE_TYPE_RADIUS_INCHES and models <= 1:
        return BASE_TYPE_RADIUS_INCHES[base_type]
    return round(max(1.0, min(6.0, math.sqrt(models) * 0.85)), 2)


def footprint_dimensions_mm(unit: UnitProfile) -> Tuple[float, float] | None:
    base_width = _float_or_none(getattr(unit, "base_width_mm", None))
    base_depth = _float_or_none(getattr(unit, "base_depth_mm", None))
    if base_width and base_depth:
        return base_width, base_depth
    return BASE_TYPE_DIMENSIONS_MM.get(str(getattr(unit, "base_type", "") or ""))


def radius_from_base_dimensions(models: int, base_width_mm: float, base_depth_mm: float) -> float:
    largest_base_inches = max(float(base_width_mm), float(base_depth_mm)) / 25.4
    single_model_radius = max(0.45, largest_base_inches / 2)
    formation_radius = math.sqrt(models) * (single_model_radius + 0.2)
    return round(max(0.75, min(8.0, formation_radius)), 2)


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def advance_allowance_for_unit(battle_map: BattleMap, actor: BattleUnit, unit: UnitProfile) -> Tuple[float, List[str]]:
    allowance, notes = movement_allowance_for_unit(battle_map, actor, unit)
    return allowance + ADVANCE_EXPECTED_ROLL, notes + [f"Advance movement adds an expected D6 roll of {ADVANCE_EXPECTED_ROLL:.1f}\"."]


def movement_limited_destination(
    state: BattleState,
    actor: BattleUnit,
    profile: UnitProfile,
    x: float,
    y: float,
    *,
    extra_allowance: float = 0.0,
    extra_notes: Optional[List[str]] = None,
) -> Tuple[Dict[str, float], List[str]]:
    allowance, notes = movement_allowance_for_unit(state.map, actor, profile)
    allowance += max(0.0, float(extra_allowance or 0.0))
    notes = notes + list(extra_notes or [])
    bounded_x = max(actor.radius, min(state.map.width - actor.radius, float(x)))
    bounded_y = max(actor.radius, min(state.map.height - actor.radius, float(y)))
    dist = distance(actor.x, actor.y, bounded_x, bounded_y)
    if dist <= allowance:
        return {"x": round(bounded_x, 2), "y": round(bounded_y, 2)}, notes
    destination = step_towards(actor.x, actor.y, bounded_x, bounded_y, allowance)
    return destination, notes + [f"Move destination clamped to {allowance:.1f}\" movement allowance."]


def non_overlapping_destination(
    state: BattleState,
    actor: BattleUnit,
    x: float,
    y: float,
) -> Tuple[Dict[str, float], List[str]]:
    proposed = {
        "x": max(actor.radius, min(state.map.width - actor.radius, float(x))),
        "y": max(actor.radius, min(state.map.height - actor.radius, float(y))),
    }
    if not collides_at(state, actor, proposed["x"], proposed["y"]):
        return {"x": round(proposed["x"], 2), "y": round(proposed["y"], 2)}, []

    for step in range(23, -1, -1):
        ratio = step / 24
        candidate_x = actor.x + (proposed["x"] - actor.x) * ratio
        candidate_y = actor.y + (proposed["y"] - actor.y) * ratio
        if not collides_at(state, actor, candidate_x, candidate_y):
            return (
                {"x": round(candidate_x, 2), "y": round(candidate_y, 2)},
                ["Movement destination adjusted to avoid overlapping another unit footprint."],
            )
    return (
        {"x": round(actor.x, 2), "y": round(actor.y, 2)},
        ["Movement blocked because no non-overlapping destination was available along that path."],
    )


def fall_back_destination(
    state: BattleState,
    actor: BattleUnit,
    enemy: BattleUnit,
    allowance: float,
) -> Tuple[Dict[str, float], List[str]]:
    centre_distance = distance(actor.x, actor.y, enemy.x, enemy.y)
    if centre_distance <= 0:
        direction_x, direction_y = 1.0, 0.0
    else:
        direction_x = (actor.x - enemy.x) / centre_distance
        direction_y = (actor.y - enemy.y) / centre_distance
    proposed_x = actor.x + direction_x * allowance
    proposed_y = actor.y + direction_y * allowance
    destination, collision_notes = non_overlapping_destination(state, actor, proposed_x, proposed_y)
    return (
        destination,
        ["Fall Back movement is approximated as a direct move away from the nearest engaged enemy."]
        + collision_notes,
    )


def charge_engagement_destination(
    state: BattleState,
    actor: BattleUnit,
    target: BattleUnit,
) -> Tuple[Dict[str, float], List[str]]:
    if attack_distance(actor, target) <= 1.0:
        return (
            {"x": round(actor.x, 2), "y": round(actor.y, 2)},
            ["Charge movement already ends in engagement range."],
        )
    centre_distance = distance(actor.x, actor.y, target.x, target.y)
    if centre_distance <= 0:
        direction_x, direction_y = -1.0, 0.0
    else:
        direction_x = (actor.x - target.x) / centre_distance
        direction_y = (actor.y - target.y) / centre_distance
    desired_centre_distance = actor.radius + target.radius + 0.5
    proposed_x = target.x + direction_x * desired_centre_distance
    proposed_y = target.y + direction_y * desired_centre_distance
    destination, collision_notes = non_overlapping_destination(state, actor, proposed_x, proposed_y)
    return (
        destination,
        [
            "Successful charge movement is modeled deterministically into engagement range after expected damage."
        ]
        + collision_notes,
    )


def collides_at(state: BattleState, actor: BattleUnit, x: float, y: float) -> bool:
    moved = copy.copy(actor)
    moved.x = float(x)
    moved.y = float(y)
    return any(units_overlap(moved, other) for other in live_units(state) if other.instance_id != actor.instance_id)


def units_overlap(left: BattleUnit, right: BattleUnit) -> bool:
    return distance(left.x, left.y, right.x, right.y) < left.radius + right.radius


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


def attack_distance(actor: BattleUnit, target: BattleUnit) -> float:
    return max(0.0, distance(actor.x, actor.y, target.x, target.y) - actor.radius - target.radius)


def ranged_attack_reach(unit: UnitProfile) -> float:
    ranges = [weapon_range_inches(weapon) for weapon in unit.weapons if weapon.type == "ranged"]
    return max(ranges, default=0.0)


def ranged_attack_assumptions(unit: UnitProfile) -> List[str]:
    if not any(weapon.type == "ranged" for weapon in unit.weapons):
        return ["This unit has no imported ranged weapon profiles."]
    if any(getattr(weapon, "range_inches", None) for weapon in unit.weapons if weapon.type == "ranged"):
        return []
    return ["Weapon ranges are not present in the current imported CSV; Battlefield mode uses tactical range estimates."]


def weapon_range_inches(weapon: Any) -> float:
    explicit = getattr(weapon, "range_inches", None)
    if explicit:
        try:
            return max(0.0, float(explicit))
        except (TypeError, ValueError):
            pass
    text = f"{getattr(weapon, 'name', '')} {' '.join(getattr(weapon, 'keywords', []) or [])}".casefold()
    if "grenade" in text:
        return 8.0
    if "pistol" in text:
        return 12.0
    if "torrent" in text or "flamer" in text or "flame" in text:
        return 12.0
    if "melta" in text:
        return 18.0
    if any(term in text for term in ("lascannon", "missile", "mortar", "battle cannon", "railgun", "volcano")):
        return 48.0
    return 36.0


def is_in_cover(battle_map: BattleMap, unit: BattleUnit) -> bool:
    return any(
        feature.grants_cover
        and feature.x - unit.radius <= unit.x <= feature.x + feature.width + unit.radius
        and feature.y - unit.radius <= unit.y <= feature.y + feature.height + unit.radius
        for feature in battle_map.terrain
    )


def point_in_feature(x: float, y: float, feature: TerrainFeature) -> bool:
    return feature.x <= x <= feature.x + feature.width and feature.y <= y <= feature.y + feature.height


def segment_intersects_feature(x1: float, y1: float, x2: float, y2: float, feature: TerrainFeature) -> bool:
    left = feature.x
    right = feature.x + feature.width
    top = feature.y
    bottom = feature.y + feature.height
    if point_in_feature(x1, y1, feature) or point_in_feature(x2, y2, feature):
        return True
    return (
        segments_intersect(x1, y1, x2, y2, left, top, right, top)
        or segments_intersect(x1, y1, x2, y2, right, top, right, bottom)
        or segments_intersect(x1, y1, x2, y2, right, bottom, left, bottom)
        or segments_intersect(x1, y1, x2, y2, left, bottom, left, top)
    )


def segments_intersect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> bool:
    def orientation(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qy - py) * (rx - qx) - (qx - px) * (ry - qy)

    def on_segment(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> bool:
        return min(px, rx) <= qx <= max(px, rx) and min(py, ry) <= qy <= max(py, ry)

    o1 = orientation(ax, ay, bx, by, cx, cy)
    o2 = orientation(ax, ay, bx, by, dx, dy)
    o3 = orientation(cx, cy, dx, dy, ax, ay)
    o4 = orientation(cx, cy, dx, dy, bx, by)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    epsilon = 1e-9
    return (
        abs(o1) <= epsilon and on_segment(ax, ay, cx, cy, bx, by)
        or abs(o2) <= epsilon and on_segment(ax, ay, dx, dy, bx, by)
        or abs(o3) <= epsilon and on_segment(cx, cy, ax, ay, dx, dy)
        or abs(o4) <= epsilon and on_segment(cx, cy, bx, by, dx, dy)
    )


def in_bounds(battle_map: BattleMap, x: float, y: float, radius: float) -> bool:
    return radius <= x <= battle_map.width - radius and radius <= y <= battle_map.height - radius


def rectangle_in_bounds(battle_map: BattleMap, x: float, y: float, width: float, height: float) -> bool:
    return x >= 0 and y >= 0 and x + width <= battle_map.width and y + height <= battle_map.height


def circle_in_bounds(battle_map: BattleMap, x: float, y: float, radius: float) -> bool:
    return radius >= 0 and radius <= x <= battle_map.width - radius and radius <= y <= battle_map.height - radius


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
