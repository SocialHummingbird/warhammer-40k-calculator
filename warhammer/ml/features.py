from __future__ import annotations

import csv
from pathlib import Path
import random
from typing import Iterable, Iterator, Sequence

from ..calculator import EngagementContext
from ..matchups import calculate_matchup, points_per_model
from ..profiles import UnitProfile


FEATURE_COLUMNS = [
    "edition",
    "mode",
    "label_source",
    "winner_label",
    "winner_name",
    "confidence",
    "basis",
    "edge",
    "attacker_id",
    "attacker_name",
    "attacker_faction",
    "attacker_points",
    "attacker_models",
    "attacker_toughness",
    "attacker_save",
    "attacker_invulnerable_save",
    "attacker_wounds",
    "attacker_keywords_count",
    "attacker_weapon_count",
    "attacker_mode_weapon_count",
    "attacker_points_per_model",
    "attacker_mode_avg_attacks",
    "attacker_mode_max_attacks",
    "attacker_mode_avg_skill",
    "attacker_mode_avg_strength",
    "attacker_mode_max_strength",
    "attacker_mode_avg_ap",
    "attacker_mode_best_ap",
    "attacker_mode_avg_damage",
    "attacker_mode_max_damage",
    "attacker_mode_keyword_count",
    "attacker_mode_special_rule_count",
    "defender_id",
    "defender_name",
    "defender_faction",
    "defender_points",
    "defender_models",
    "defender_toughness",
    "defender_save",
    "defender_invulnerable_save",
    "defender_wounds",
    "defender_keywords_count",
    "defender_weapon_count",
    "defender_mode_weapon_count",
    "defender_points_per_model",
    "defender_mode_avg_attacks",
    "defender_mode_max_attacks",
    "defender_mode_avg_skill",
    "defender_mode_avg_strength",
    "defender_mode_max_strength",
    "defender_mode_avg_ap",
    "defender_mode_best_ap",
    "defender_mode_avg_damage",
    "defender_mode_max_damage",
    "defender_mode_keyword_count",
    "defender_mode_special_rule_count",
    "outgoing_damage",
    "outgoing_unsaved_wounds",
    "outgoing_models_destroyed",
    "outgoing_points_removed",
    "incoming_damage",
    "incoming_unsaved_wounds",
    "incoming_models_destroyed",
    "incoming_points_removed",
    "damage_delta",
    "points_removed_delta",
]


def build_matchup_feature_rows(
    units: Iterable[UnitProfile],
    *,
    edition: str = "10e",
    modes: Sequence[str] = ("ranged", "melee"),
    max_rows: int | None = None,
) -> list[dict[str, object]]:
    rows = []
    for row in iter_matchup_feature_rows(units, edition=edition, modes=modes, max_rows=max_rows):
        rows.append(row)
    return rows


def sample_matchup_feature_rows(
    units: Iterable[UnitProfile],
    *,
    edition: str = "10e",
    modes: Sequence[str] = ("ranged", "melee"),
    row_count: int = 10000,
    seed: int = 40,
) -> list[dict[str, object]]:
    """Sample unique matchup rows across modes with a stable random seed."""

    if row_count <= 0:
        return []
    rng = random.Random(seed)
    unit_list = sorted(units, key=lambda unit: ((unit.name or "").casefold(), unit.unit_id or ""))
    pools = []
    for mode in modes:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"ranged", "melee"}:
            raise ValueError(f"Unsupported mode {mode!r}; expected ranged or melee")
        attackers = [unit for unit in unit_list if _mode_weapon_count(unit, normalized_mode) > 0]
        defenders = [unit for unit in unit_list if unit.wounds > 0]
        if attackers and defenders:
            pools.append((normalized_mode, attackers, defenders))
    if not pools:
        return []

    rows = []
    seen: set[tuple[str, str, str]] = set()
    max_attempts = max(row_count * 25, 1000)
    attempts = 0
    while len(rows) < row_count and attempts < max_attempts:
        attempts += 1
        mode, attackers, defenders = rng.choice(pools)
        attacker = rng.choice(attackers)
        defender = rng.choice(defenders)
        if attacker is defender or _same_unit_id(attacker, defender):
            continue
        key = (mode, _unit_key(attacker), _unit_key(defender))
        if key in seen:
            continue
        seen.add(key)
        rows.append(_matchup_feature_row(attacker, defender, mode, edition=edition))
    return rows


def iter_matchup_feature_rows(
    units: Iterable[UnitProfile],
    *,
    edition: str = "10e",
    modes: Sequence[str] = ("ranged", "melee"),
    max_rows: int | None = None,
) -> Iterator[dict[str, object]]:
    unit_list = sorted(units, key=lambda unit: ((unit.name or "").casefold(), unit.unit_id or ""))
    emitted = 0
    for mode in modes:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"ranged", "melee"}:
            raise ValueError(f"Unsupported mode {mode!r}; expected ranged or melee")
        attackers = [unit for unit in unit_list if _mode_weapon_count(unit, normalized_mode) > 0]
        defenders = [unit for unit in unit_list if unit.wounds > 0]
        for attacker in attackers:
            for defender in defenders:
                if attacker is defender or _same_unit_id(attacker, defender):
                    continue
                yield _matchup_feature_row(attacker, defender, normalized_mode, edition=edition)
                emitted += 1
                if max_rows is not None and emitted >= max_rows:
                    return


def write_matchup_feature_csv(rows: Iterable[dict[str, object]], path: Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEATURE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _matchup_feature_row(attacker: UnitProfile, defender: UnitProfile, mode: str, *, edition: str) -> dict[str, object]:
    result = calculate_matchup(
        attacker,
        defender,
        mode,
        outgoing_context=EngagementContext(),
        incoming_context=EngagementContext(),
        edition=edition,
    )
    return matchup_feature_row_from_result(attacker, defender, mode, result, edition=edition)


def matchup_feature_row_from_result(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: str,
    result: dict[str, object],
    *,
    edition: str = "10e",
) -> dict[str, object]:
    outgoing = result["outgoing"]
    incoming = result["incoming"]
    judgement = result["judgement"]
    winner_name = judgement.get("winner")
    if winner_name is None:
        winner_label = "close"
    elif winner_name == attacker.name:
        winner_label = "attacker"
    else:
        winner_label = "defender"

    outgoing_damage = _number(outgoing.get("total_damage"))
    incoming_damage = _number(incoming.get("total_damage"))
    outgoing_points = _number(outgoing.get("estimated_points_removed"))
    incoming_points = _number(incoming.get("estimated_points_removed"))

    return {
        "edition": edition,
        "mode": mode,
        "label_source": "deterministic_calculator",
        "winner_label": winner_label,
        "winner_name": winner_name or "",
        "confidence": judgement.get("confidence", ""),
        "basis": judgement.get("basis", ""),
        "edge": _number(judgement.get("edge")),
        **_unit_features(attacker, prefix="attacker", mode=mode),
        **_unit_features(defender, prefix="defender", mode=mode),
        "outgoing_damage": outgoing_damage,
        "outgoing_unsaved_wounds": _number(outgoing.get("total_unsaved_wounds")),
        "outgoing_models_destroyed": _number(outgoing.get("expected_models_destroyed")),
        "outgoing_points_removed": outgoing_points,
        "incoming_damage": incoming_damage,
        "incoming_unsaved_wounds": _number(incoming.get("total_unsaved_wounds")),
        "incoming_models_destroyed": _number(incoming.get("expected_models_destroyed")),
        "incoming_points_removed": incoming_points,
        "damage_delta": outgoing_damage - incoming_damage,
        "points_removed_delta": outgoing_points - incoming_points,
    }


def _unit_features(unit: UnitProfile, *, prefix: str, mode: str) -> dict[str, object]:
    return {
        f"{prefix}_id": unit.unit_id or "",
        f"{prefix}_name": unit.name,
        f"{prefix}_faction": unit.faction or "",
        f"{prefix}_points": unit.points or "",
        f"{prefix}_models": _model_count(unit) or "",
        f"{prefix}_toughness": unit.toughness,
        f"{prefix}_save": unit.save,
        f"{prefix}_invulnerable_save": unit.invulnerable_save or "",
        f"{prefix}_wounds": unit.wounds,
        f"{prefix}_keywords_count": len(unit.keywords),
        f"{prefix}_weapon_count": len(unit.weapons),
        f"{prefix}_mode_weapon_count": _mode_weapon_count(unit, mode),
        f"{prefix}_points_per_model": _number(points_per_model(unit)),
        **_mode_weapon_features(unit, prefix=prefix, mode=mode),
    }


def _mode_weapon_features(unit: UnitProfile, *, prefix: str, mode: str) -> dict[str, object]:
    weapons = [weapon for weapon in unit.weapons if weapon.type == mode]
    return {
        f"{prefix}_mode_avg_attacks": _average([weapon.attacks.average for weapon in weapons]),
        f"{prefix}_mode_max_attacks": _maximum([weapon.attacks.average for weapon in weapons]),
        f"{prefix}_mode_avg_skill": _average([weapon.skill for weapon in weapons]),
        f"{prefix}_mode_avg_strength": _average([weapon.strength for weapon in weapons]),
        f"{prefix}_mode_max_strength": _maximum([weapon.strength for weapon in weapons]),
        f"{prefix}_mode_avg_ap": _average([weapon.ap for weapon in weapons]),
        f"{prefix}_mode_best_ap": _minimum([weapon.ap for weapon in weapons]),
        f"{prefix}_mode_avg_damage": _average([weapon.damage.average for weapon in weapons]),
        f"{prefix}_mode_max_damage": _maximum([weapon.damage.average for weapon in weapons]),
        f"{prefix}_mode_keyword_count": sum(len(weapon.keywords) for weapon in weapons),
        f"{prefix}_mode_special_rule_count": sum(_special_rule_count(weapon) for weapon in weapons),
    }


def _same_unit_id(left: UnitProfile, right: UnitProfile) -> bool:
    return bool(left.unit_id and right.unit_id and left.unit_id == right.unit_id)


def _unit_key(unit: UnitProfile) -> str:
    return unit.unit_id or f"{unit.faction or ''}:{unit.name}"


def _mode_weapon_count(unit: UnitProfile, mode: str) -> int:
    return sum(1 for weapon in unit.weapons if weapon.type == mode)


def _special_rule_count(weapon: object) -> int:
    return sum(
        1
        for flag in (
            getattr(weapon, "lethal_hits", False),
            getattr(weapon, "sustained_hits", 0),
            getattr(weapon, "devastating_wounds", False),
            getattr(weapon, "auto_hits", False),
            getattr(weapon, "assault", False),
            getattr(weapon, "heavy", False),
            getattr(weapon, "torrent", False),
            getattr(weapon, "twin_linked", False),
            getattr(weapon, "ignores_cover", False),
            getattr(weapon, "blast", False),
            getattr(weapon, "melta", None),
            getattr(weapon, "rapid_fire", None),
            getattr(weapon, "anti_rules", []),
        )
        if flag
    )


def _model_count(unit: UnitProfile) -> int | None:
    if unit.models_min and unit.models_max:
        return max(1, round((unit.models_min + unit.models_max) / 2))
    if unit.models_max:
        return max(1, unit.models_max)
    if unit.models_min:
        return max(1, unit.models_min)
    return None


def _number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _average(values: Iterable[object]) -> float:
    numbers = [_number(value) for value in values]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _maximum(values: Iterable[object]) -> float:
    numbers = [_number(value) for value in values]
    return max(numbers) if numbers else 0.0


def _minimum(values: Iterable[object]) -> float:
    numbers = [_number(value) for value in values]
    return min(numbers) if numbers else 0.0
