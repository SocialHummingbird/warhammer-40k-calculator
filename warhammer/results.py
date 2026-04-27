from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional

from .profiles import UnitProfile, WeaponProfile


@dataclass
class WeaponResult:
    weapon: WeaponProfile
    attacks: float
    hits: float
    critical_hits: float
    extra_hits: float
    auto_wounds: float
    devastating_wounds: float
    wounds: float
    unsaved_wounds_before_fnp: float
    unsaved_wounds: float
    expected_damage: float
    hit_probability: float
    wound_probability: float
    critical_wound_probability: float
    failed_save_probability: float
    wound_roll_label: str
    save_used_label: str
    fnp_success_probability: float
    target_fnp_label: Optional[str]
    ability_notes: List[str]
    damage_cap_applied: Optional[float]
    target_wounds: Optional[int] = None
    models_destroyed: Optional[float] = None

    @property
    def expected_models_destroyed(self) -> Optional[float]:
        if self.models_destroyed is not None:
            return self.models_destroyed
        if not self.target_wounds or self.target_wounds <= 0:
            return None
        return self.expected_damage / self.target_wounds


@dataclass
class UnitResult:
    unit: UnitProfile
    weapons: List[WeaponResult]
    target_wounds: Optional[int] = None

    @property
    def total_damage(self) -> float:
        return sum(result.expected_damage for result in self.weapons)

    @property
    def total_unsaved_wounds(self) -> float:
        return sum(result.unsaved_wounds for result in self.weapons)

    @property
    def total_unsaved_wounds_before_fnp(self) -> float:
        return sum(result.unsaved_wounds_before_fnp for result in self.weapons)

    @property
    def expected_models_destroyed(self) -> Optional[float]:
        weapon_values = [result.expected_models_destroyed for result in self.weapons]
        if all(value is not None for value in weapon_values):
            return sum(value for value in weapon_values if value is not None)
        if not self.target_wounds or self.target_wounds <= 0:
            return None
        return self.total_damage / self.target_wounds

    @property
    def feel_no_pain_applied(self) -> bool:
        return any(result.fnp_success_probability > 0 for result in self.weapons)


def scale_weapon_result(result: WeaponResult, multiplier: int) -> WeaponResult:
    """Scale expected counts for repeated identical weapon profiles."""

    multiplier = max(1, int(multiplier))
    return replace(
        result,
        attacks=result.attacks * multiplier,
        hits=result.hits * multiplier,
        critical_hits=result.critical_hits * multiplier,
        extra_hits=result.extra_hits * multiplier,
        auto_wounds=result.auto_wounds * multiplier,
        devastating_wounds=result.devastating_wounds * multiplier,
        wounds=result.wounds * multiplier,
        unsaved_wounds_before_fnp=result.unsaved_wounds_before_fnp * multiplier,
        unsaved_wounds=result.unsaved_wounds * multiplier,
        expected_damage=result.expected_damage * multiplier,
        models_destroyed=(
            result.models_destroyed * multiplier
            if result.models_destroyed is not None
            else None
        ),
    )


def scale_unit_result(result: UnitResult, multiplier: int) -> UnitResult:
    """Scale all weapon results in a unit result by the same repeat count."""

    multiplier = max(1, int(multiplier))
    if multiplier == 1:
        return result
    return replace(
        result,
        weapons=[scale_weapon_result(weapon_result, multiplier) for weapon_result in result.weapons],
    )
