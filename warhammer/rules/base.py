from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from warhammer.profiles import UnitProfile, WeaponProfile


@dataclass(frozen=True)
class AdvanceAttackDecision:
    """Ruleset decision for whether an advanced attacker may resolve an attack."""

    can_attack: bool
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AttackCountAdjustment:
    """Ruleset-adjusted attack count and annotations."""

    attacks: float
    target_model_count: int
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class HitModifierAdjustment:
    """Ruleset-adjusted hit modifier and annotations."""

    modifier_delta: int = 0
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class HitRollResolution:
    """Ruleset hit-roll and hit-pool output."""

    hit_probability: float
    critical_hit_probability: float
    hits: float
    critical_hits: float
    extra_hits: float
    total_hits: float
    auto_wounds: float
    hits_requiring_wound: float


@dataclass(frozen=True)
class SaveResolution:
    """Ruleset-selected saving throw and contextual annotations."""

    target: int
    label: str
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DamageResolution:
    """Ruleset-selected damage modifiers and contextual annotations."""

    damage_per_wound: float
    capped_damage_per_wound: float
    damage_cap_applied: Optional[float] = None
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DamagePipelineResolution:
    """Ruleset conversion from wound pools into unsaved wounds, damage, and models."""

    failed_save_probability: float
    fnp_success_probability: float
    unsaved_wounds_before_fnp: float
    unsaved_wounds: float
    expected_damage: float
    models_destroyed: Optional[float]


@dataclass(frozen=True)
class WoundRollResolution:
    """Ruleset wound-roll probability output."""

    wound_probability: float
    critical_wound_probability: float
    label: str


@dataclass(frozen=True)
class WoundPoolResolution:
    """Ruleset split of wounds into saveable and non-saveable pools."""

    wounds: float
    devastating_wounds: float
    normal_wounds_from_roll: float


@dataclass(frozen=True)
class RuleCapability:
    """Machine-readable implementation status for an edition-specific mechanic."""

    key: str
    label: str
    status: str = "implemented"
    notes: Tuple[str, ...] = ()


class Ruleset(Protocol):
    """Edition-specific combat rules used by the probability calculator."""

    edition: str
    label: str
    capabilities: Tuple[RuleCapability, ...]

    def required_wound_roll(self, strength: float, toughness: int) -> int:
        ...

    def cap_roll_modifier(self, value: int) -> int:
        ...

    def advance_attack_decision(
        self,
        weapon: WeaponProfile,
        *,
        attacker_advanced: bool,
        weapon_assault: bool,
        attacker_can_advance_and_shoot: bool,
    ) -> AdvanceAttackDecision:
        ...

    def adjusted_attack_count(
        self,
        weapon: WeaponProfile,
        *,
        base_attacks: float,
        target_model_count: Optional[int],
        defender: UnitProfile,
        target_within_half_range: bool,
        weapon_blast: bool,
    ) -> AttackCountAdjustment:
        ...

    def ranged_hit_modifier(
        self,
        weapon: WeaponProfile,
        *,
        attacker_moved: bool,
        attacker_advanced: bool,
        weapon_assault: bool,
        attacker_can_advance_and_shoot: bool,
    ) -> HitModifierAdjustment:
        ...

    def hit_roll_resolution(
        self,
        weapon: WeaponProfile,
        *,
        attacks: float,
        hit_modifier: int,
        hit_reroll: str,
        weapon_auto_hits: bool,
    ) -> HitRollResolution:
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

    def save_resolution(
        self,
        defender: UnitProfile,
        weapon: WeaponProfile,
        *,
        target_in_cover: bool,
        weapon_ignores_cover: bool,
    ) -> SaveResolution:
        ...

    def damage_resolution(
        self,
        weapon: WeaponProfile,
        defender: UnitProfile,
        *,
        target_within_half_range: bool,
    ) -> DamageResolution:
        ...

    def wound_roll_resolution(
        self,
        weapon: WeaponProfile,
        *,
        defender_toughness: int,
        wound_modifier: int,
        wound_reroll: str,
        anti_threshold: Optional[int],
    ) -> WoundRollResolution:
        ...

    def wound_pool_resolution(
        self,
        weapon: WeaponProfile,
        *,
        auto_wounds: float,
        hits_requiring_wound: float,
        wound_probability: float,
        critical_wound_probability: float,
    ) -> WoundPoolResolution:
        ...

    def damage_pipeline_resolution(
        self,
        defender: UnitProfile,
        *,
        save_resolution: SaveResolution,
        wound_pool: WoundPoolResolution,
        auto_wounds: float,
        damage_resolution: DamageResolution,
    ) -> DamagePipelineResolution:
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
