from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

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

    @property
    def expected_models_destroyed(self) -> Optional[float]:
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
        if not self.target_wounds or self.target_wounds <= 0:
            return None
        return self.total_damage / self.target_wounds

    @property
    def feel_no_pain_applied(self) -> bool:
        return any(result.fnp_success_probability > 0 for result in self.weapons)


EngagementMode = Literal["ranged", "melee"]


def evaluate_unit(attacker: UnitProfile, defender: UnitProfile, mode: EngagementMode) -> UnitResult:
    relevant_weapons = [weapon for weapon in attacker.weapons if weapon.type == mode]
    weapon_results = [
        _resolve_weapon(attacker=attacker, defender=defender, weapon=weapon) for weapon in relevant_weapons
    ]
    return UnitResult(unit=attacker, weapons=weapon_results, target_wounds=defender.wounds)


def _resolve_weapon(*, attacker: UnitProfile, defender: UnitProfile, weapon: WeaponProfile) -> WeaponResult:
    attacks = weapon.attacks.average

    hit_probability = _probability_success_with_reroll(weapon.skill, weapon.reroll_hits)
    crit_hit_probability = _critical_probability(weapon.skill, weapon.reroll_hits)

    hits = attacks * hit_probability
    critical_hits = attacks * crit_hit_probability
    extra_hits = critical_hits * weapon.sustained_hits
    total_hits = hits + extra_hits

    auto_wounds = critical_hits if weapon.lethal_hits else 0.0
    hits_requiring_wound = max(total_hits - auto_wounds, 0.0)

    wound_roll = _required_wound_roll(weapon.strength, defender.toughness)
    wound_probability = _probability_success_with_reroll(wound_roll, weapon.reroll_wounds)
    crit_wound_probability = _critical_probability(wound_roll, weapon.reroll_wounds)
    wounds_from_roll = hits_requiring_wound * wound_probability

    devastating_wounds = 0.0
    normal_wounds_from_roll = wounds_from_roll
    if weapon.devastating_wounds:
        devastating_wounds = hits_requiring_wound * crit_wound_probability
        devastating_wounds = min(devastating_wounds, wounds_from_roll)
        normal_wounds_from_roll = max(wounds_from_roll - devastating_wounds, 0.0)

    wounds = auto_wounds + devastating_wounds + normal_wounds_from_roll

    save_target, save_label = _effective_save(defender, weapon)
    if save_target >= 7:
        save_success_probability = 0.0
    else:
        save_success_probability = _probability_success_on(save_target)
    failed_save_probability = 1 - save_success_probability

    wounds_subject_to_save = auto_wounds + normal_wounds_from_roll
    unsaved_via_saves = wounds_subject_to_save * failed_save_probability
    unsaved_wounds_before_fnp = unsaved_via_saves + devastating_wounds

    fnp_prob = _feel_no_pain_success_probability(defender)
    unsaved_wounds = unsaved_wounds_before_fnp * (1 - fnp_prob)

    damage_per_wound = weapon.damage.average
    damage_cap_applied = None
    if defender.damage_cap is not None:
        damage_per_wound = min(damage_per_wound, defender.damage_cap)
        damage_cap_applied = defender.damage_cap

    expected_damage = unsaved_wounds * damage_per_wound

    ability_notes = _build_ability_notes(weapon)

    return WeaponResult(
        weapon=weapon,
        attacks=attacks,
        hits=total_hits,
        critical_hits=critical_hits,
        extra_hits=extra_hits,
        auto_wounds=auto_wounds,
        devastating_wounds=devastating_wounds,
        wounds=wounds,
        unsaved_wounds_before_fnp=unsaved_wounds_before_fnp,
        unsaved_wounds=unsaved_wounds,
        expected_damage=expected_damage,
        hit_probability=hit_probability,
        wound_probability=wound_probability,
        critical_wound_probability=crit_wound_probability,
        failed_save_probability=failed_save_probability,
        wound_roll_label=f"{wound_roll}+",
        save_used_label=save_label,
        fnp_success_probability=fnp_prob,
        target_fnp_label=defender.feel_no_pain_label,
        ability_notes=ability_notes,
        damage_cap_applied=damage_cap_applied,
        target_wounds=defender.wounds,
    )


def _required_wound_roll(strength: int, toughness: int) -> int:
    if strength >= toughness * 2:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if strength * 2 <= toughness:
        return 6
    return 5


def _effective_save(defender: UnitProfile, weapon: WeaponProfile) -> Tuple[int, str]:
    ap_value = weapon.ap
    if ap_value > 0:
        ap_value = -ap_value

    modified = defender.save - ap_value
    modified = max(2, min(7, modified))

    invul = defender.invulnerable_save
    invul_label = defender.invulnerable_label
    if invul is not None and invul < modified:
        return invul, invul_label or f"{invul}+"
    return modified, f"{modified}+"


def _probability_success_on(target: int) -> float:
    if target >= 7:
        return 0.0
    target = max(2, min(6, target))
    return (7 - target) / 6


def _probability_success_with_reroll(target: int, reroll: str) -> float:
    base = _probability_success_on(target)
    if reroll == "all":
        return base + (1 - base) * base
    if reroll == "ones":
        return base + (1 / 6) * base
    return base


def _critical_probability(target: int, reroll: str) -> float:
    base = 1 / 6
    if reroll == "all":
        failure_prob = 1 - _probability_success_on(target)
        return base + failure_prob * (1 / 6)
    if reroll == "ones":
        return base + (1 / 6) * (1 / 6)
    return base


def _feel_no_pain_success_probability(defender: UnitProfile) -> float:
    if defender.feel_no_pain is None:
        return 0.0
    target = max(2, min(6, defender.feel_no_pain))
    return (7 - target) / 6


def _build_ability_notes(weapon: WeaponProfile) -> List[str]:
    notes: List[str] = []
    if weapon.reroll_hits != "none":
        label = "Hit rerolls (all)" if weapon.reroll_hits == "all" else "Hit rerolls (ones)"
        notes.append(label)
    if weapon.reroll_wounds != "none":
        label = "Wound rerolls (all)" if weapon.reroll_wounds == "all" else "Wound rerolls (ones)"
        notes.append(label)
    if weapon.lethal_hits:
        notes.append("Lethal Hits")
    if weapon.sustained_hits:
        notes.append(f"Sustained Hits {weapon.sustained_hits}")
    if weapon.devastating_wounds:
        notes.append("Devastating Wounds")
    return notes
