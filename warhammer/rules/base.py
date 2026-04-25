from __future__ import annotations

from typing import Callable, List, Optional, Protocol, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from warhammer.profiles import UnitProfile, WeaponProfile


class Ruleset(Protocol):
    """Edition-specific combat rules used by the probability calculator."""

    edition: str
    label: str

    def required_wound_roll(self, strength: float, toughness: int) -> int:
        ...

    def cap_roll_modifier(self, value: int) -> int:
        ...

    def expected_models_destroyed_from_damage(
        self,
        *,
        unsaved_wounds: float,
        capped_damage_per_wound: float,
        target_wounds: Optional[int],
    ) -> Optional[float]:
        ...

    def modified_damage_averages(
        self,
        *,
        weapon: WeaponProfile,
        defender: UnitProfile,
        melta_bonus: float,
    ) -> Tuple[float, float]:
        ...

    def effective_save(
        self,
        defender: UnitProfile,
        weapon: WeaponProfile,
        *,
        cover_bonus: int = 0,
    ) -> Tuple[int, str]:
        ...

    def probability_success_on(self, target: int) -> float:
        ...

    def probability_success_with_reroll(self, target: int, reroll: str) -> float:
        ...

    def final_roll_distribution(self, reroll: str, success_check: Callable[[int], bool]) -> List[float]:
        ...

    def critical_probability(self, target: int, reroll: str) -> float:
        ...

    def feel_no_pain_success_probability(self, defender: UnitProfile) -> float:
        ...
