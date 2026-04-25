from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from warhammer.dice import quantity_distribution
from warhammer.profiles import UnitProfile, WeaponProfile


@dataclass(frozen=True)
class TenthEditionRules:
    """Warhammer 40,000 10th edition combat math currently supported by the app."""

    edition: str = "10e"
    label: str = "Warhammer 40,000 10th Edition"

    def required_wound_roll(self, strength: float, toughness: int) -> int:
        if strength >= toughness * 2:
            return 2
        if strength > toughness:
            return 3
        if strength == toughness:
            return 4
        if strength * 2 <= toughness:
            return 6
        return 5

    def cap_roll_modifier(self, value: int) -> int:
        return max(-1, min(1, value))

    def expected_models_destroyed_from_damage(
        self,
        *,
        unsaved_wounds: float,
        capped_damage_per_wound: float,
        target_wounds: Optional[int],
    ) -> Optional[float]:
        if target_wounds is None or target_wounds <= 0:
            return None
        return unsaved_wounds * (max(capped_damage_per_wound, 0.0) / target_wounds)

    def modified_damage_averages(
        self,
        *,
        weapon: WeaponProfile,
        defender: UnitProfile,
        melta_bonus: float,
    ) -> Tuple[float, float]:
        total_damage = 0.0
        capped_damage = 0.0
        cap = float(defender.damage_cap) if defender.damage_cap is not None else None
        target_wounds = float(defender.wounds) if defender.wounds and defender.wounds > 0 else None

        for damage, probability in quantity_distribution(weapon.damage.label):
            modified = max(damage + melta_bonus - float(defender.damage_reduction or 0.0), 0.0)
            if cap is not None:
                modified = min(modified, cap)
            total_damage += modified * probability
            capped_damage += (min(modified, target_wounds) if target_wounds is not None else modified) * probability

        return total_damage, capped_damage

    def effective_save(
        self,
        defender: UnitProfile,
        weapon: WeaponProfile,
        *,
        cover_bonus: int = 0,
    ) -> Tuple[int, str]:
        ap_value = weapon.ap
        if ap_value > 0:
            ap_value = -ap_value

        modified = defender.save - ap_value
        if cover_bonus:
            modified = max(2, modified - cover_bonus)
        modified = max(2, min(7, modified))

        invul = defender.invulnerable_save
        invul_label = defender.invulnerable_label
        if invul is not None and invul < modified:
            return invul, invul_label or f"{invul}+"
        return modified, f"{modified}+"

    def probability_success_on(self, target: int) -> float:
        if target >= 7:
            return 0.0
        target = max(2, min(6, target))
        return (7 - target) / 6

    def probability_success_with_reroll(self, target: int, reroll: str) -> float:
        base = self.probability_success_on(target)
        if reroll == "all":
            return base + (1 - base) * base
        if reroll == "ones":
            return base + (1 / 6) * base
        return base

    def final_roll_distribution(self, reroll: str, success_check: Callable[[int], bool]) -> List[float]:
        probabilities = [0.0] * 7
        for initial in range(1, 7):
            first_prob = 1 / 6
            if reroll == "all" and not success_check(initial):
                for rerolled in range(1, 7):
                    probabilities[rerolled] += first_prob * (1 / 6)
            elif reroll == "ones" and initial == 1:
                for rerolled in range(1, 7):
                    probabilities[rerolled] += first_prob * (1 / 6)
            else:
                probabilities[initial] += first_prob
        return probabilities

    def critical_probability(self, target: int, reroll: str) -> float:
        base = 1 / 6
        if reroll == "all":
            failure_prob = 1 - self.probability_success_on(target)
            return base + failure_prob * (1 / 6)
        if reroll == "ones":
            return base + (1 / 6) * (1 / 6)
        return base

    def feel_no_pain_success_probability(self, defender: UnitProfile) -> float:
        if defender.feel_no_pain is None:
            return 0.0
        target = max(2, min(6, defender.feel_no_pain))
        return (7 - target) / 6
