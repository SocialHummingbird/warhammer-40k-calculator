from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TerrainFeature:
    id: str
    name: str
    type: str
    x: float
    y: float
    width: float
    height: float
    grants_cover: bool = True
    blocks_line_of_sight: bool = True
    movement_penalty: float = 0.0


@dataclass
class Objective:
    id: str
    name: str
    x: float
    y: float
    radius: float = 3.0
    points: int = 5


@dataclass
class DeploymentZone:
    id: str
    side: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class BattleMap:
    id: str
    name: str
    width: float
    height: float
    deployment_zones: List[DeploymentZone]
    terrain: List[TerrainFeature]
    objectives: List[Objective]
    rules_preset: str = "tactical_mvp_v1"


@dataclass
class ArmyUnit:
    unit_id: str
    name: str = ""
    count: int = 1
    selected_weapons: List[str] = field(default_factory=list)
    loadout_note: str = ""


@dataclass
class ArmyList:
    id: str
    name: str
    side: str
    units: List[ArmyUnit]


@dataclass
class BattleUnit:
    instance_id: str
    unit_id: str
    side: str
    name: str
    x: float
    y: float
    radius: float
    models_remaining: int
    wounds_remaining: float
    status_flags: List[str] = field(default_factory=list)


@dataclass
class BattleState:
    map: BattleMap
    armies: List[ArmyList]
    units: List[BattleUnit]
    turn: int = 1
    phase: str = "movement"
    active_side: str = "red"
    score: Dict[str, int] = field(default_factory=lambda: {"red": 0, "blue": 0})
    log: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BattleAction:
    id: str
    type: str
    side: str
    actor_id: str
    target_id: Optional[str] = None
    destination: Optional[Dict[str, float]] = None
    score: float = 0.0
    reason: str = ""
    expected_damage: float = 0.0
    expected_return_damage: float = 0.0
    objective_value: float = 0.0
    assumptions: List[str] = field(default_factory=list)


@dataclass
class BattleOutcome:
    action: BattleAction
    state: BattleState
    log_entry: Dict[str, Any]
    damage: float = 0.0
    points_removed: float = 0.0
    score_delta: Dict[str, int] = field(default_factory=dict)


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


def terrain_from_dict(data: Dict[str, Any]) -> TerrainFeature:
    return TerrainFeature(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or data.get("id") or "Terrain"),
        type=str(data.get("type") or "ruin"),
        x=float(data.get("x") or 0),
        y=float(data.get("y") or 0),
        width=float(data.get("width") or 0),
        height=float(data.get("height") or 0),
        grants_cover=bool(data.get("grants_cover", True)),
        blocks_line_of_sight=bool(data.get("blocks_line_of_sight", True)),
        movement_penalty=float(data.get("movement_penalty") or 0),
    )


def objective_from_dict(data: Dict[str, Any]) -> Objective:
    return Objective(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or data.get("id") or "Objective"),
        x=float(data.get("x") or 0),
        y=float(data.get("y") or 0),
        radius=float(data.get("radius") or 3),
        points=int(data.get("points") or 5),
    )


def deployment_zone_from_dict(data: Dict[str, Any]) -> DeploymentZone:
    return DeploymentZone(
        id=str(data.get("id") or ""),
        side=str(data.get("side") or "red"),
        x=float(data.get("x") or 0),
        y=float(data.get("y") or 0),
        width=float(data.get("width") or 0),
        height=float(data.get("height") or 0),
    )


def map_from_dict(data: Dict[str, Any]) -> BattleMap:
    return BattleMap(
        id=str(data.get("id") or "custom"),
        name=str(data.get("name") or "Custom battlefield"),
        width=float(data.get("width") or 44),
        height=float(data.get("height") or 60),
        deployment_zones=[deployment_zone_from_dict(row) for row in data.get("deployment_zones", [])],
        terrain=[terrain_from_dict(row) for row in data.get("terrain", [])],
        objectives=[objective_from_dict(row) for row in data.get("objectives", [])],
        rules_preset=str(data.get("rules_preset") or "tactical_mvp_v1"),
    )


def army_unit_from_dict(data: Dict[str, Any]) -> ArmyUnit:
    return ArmyUnit(
        unit_id=str(data.get("unit_id") or data.get("id") or ""),
        name=str(data.get("name") or ""),
        count=max(1, int(data.get("count") or 1)),
        selected_weapons=[str(item) for item in data.get("selected_weapons", [])],
        loadout_note=str(data.get("loadout_note") or ""),
    )


def army_from_dict(data: Dict[str, Any]) -> ArmyList:
    side = str(data.get("side") or data.get("id") or "red").lower()
    return ArmyList(
        id=str(data.get("id") or side),
        name=str(data.get("name") or f"{side.title()} Army"),
        side=side,
        units=[army_unit_from_dict(row) for row in data.get("units", [])],
    )


def battle_unit_from_dict(data: Dict[str, Any]) -> BattleUnit:
    return BattleUnit(
        instance_id=str(data.get("instance_id") or data.get("id") or ""),
        unit_id=str(data.get("unit_id") or ""),
        side=str(data.get("side") or "red").lower(),
        name=str(data.get("name") or data.get("unit_id") or "Unit"),
        x=float(data.get("x") or 0),
        y=float(data.get("y") or 0),
        radius=float(data.get("radius") or 1),
        models_remaining=max(0, int(data.get("models_remaining") or 0)),
        wounds_remaining=max(0.0, float(data.get("wounds_remaining") or 0)),
        status_flags=[str(item) for item in data.get("status_flags", [])],
    )


def state_from_dict(data: Dict[str, Any]) -> BattleState:
    return BattleState(
        map=map_from_dict(data.get("map") or {}),
        armies=[army_from_dict(row) for row in data.get("armies", [])],
        units=[battle_unit_from_dict(row) for row in data.get("units", [])],
        turn=max(1, int(data.get("turn") or 1)),
        phase=str(data.get("phase") or "movement"),
        active_side=str(data.get("active_side") or "red").lower(),
        score={
            "red": int((data.get("score") or {}).get("red") or 0),
            "blue": int((data.get("score") or {}).get("blue") or 0),
        },
        log=list(data.get("log") or []),
    )


def action_from_dict(data: Dict[str, Any]) -> BattleAction:
    destination = data.get("destination")
    return BattleAction(
        id=str(data.get("id") or ""),
        type=str(data.get("type") or "hold"),
        side=str(data.get("side") or "red").lower(),
        actor_id=str(data.get("actor_id") or ""),
        target_id=(str(data.get("target_id")) if data.get("target_id") is not None else None),
        destination=(
            {"x": float(destination.get("x") or 0), "y": float(destination.get("y") or 0)}
            if isinstance(destination, dict)
            else None
        ),
        score=float(data.get("score") or 0),
        reason=str(data.get("reason") or ""),
        expected_damage=float(data.get("expected_damage") or 0),
        expected_return_damage=float(data.get("expected_return_damage") or 0),
        objective_value=float(data.get("objective_value") or 0),
        assumptions=[str(item) for item in data.get("assumptions", [])],
    )
