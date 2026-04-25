from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Set, Tuple

from .dice import quantity_distribution
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


EngagementMode = Literal["ranged", "melee"]


@dataclass
class EngagementContext:
    attacker_moved: bool = False
    attacker_advanced: bool = False
    target_within_half_range: bool = False
    target_in_cover: bool = False
    target_model_count: Optional[int] = None

    def __post_init__(self) -> None:
        if self.attacker_advanced and not self.attacker_moved:
            self.attacker_moved = True
        if self.target_model_count is not None and self.target_model_count <= 0:
            self.target_model_count = None


@dataclass
class _AppliedModifiers:
    hit_modifier: int = 0
    wound_modifier: int = 0
    reroll_hits: str = "none"
    reroll_wounds: str = "none"
    grant_twin_linked: bool = False
    grant_torrent: bool = False
    grant_blast: bool = False
    grant_assault: bool = False
    ignores_cover: bool = False
    anti_rules: List[Tuple[str, int]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def evaluate_unit(
    attacker: UnitProfile,
    defender: UnitProfile,
    mode: EngagementMode,
    context: Optional[EngagementContext] = None,
) -> UnitResult:
    context = context or EngagementContext()
    relevant_weapons = [weapon for weapon in attacker.weapons if weapon.type == mode]
    weapon_results = [
        _resolve_weapon(attacker=attacker, defender=defender, weapon=weapon, context=context)
        for weapon in relevant_weapons
    ]
    return UnitResult(unit=attacker, weapons=weapon_results, target_wounds=defender.wounds)


def evaluate_weapon(
    attacker: UnitProfile,
    defender: UnitProfile,
    weapon: WeaponProfile,
    *,
    context: Optional[EngagementContext] = None,
) -> WeaponResult:
    """Evaluate a single weapon profile against a defender."""

    return _resolve_weapon(attacker=attacker, defender=defender, weapon=weapon, context=context or EngagementContext())



def _merge_reroll(primary: str, extra: str) -> str:
    hierarchy = {"none": 0, "ones": 1, "all": 2}
    if primary not in hierarchy:
        primary = "none"
    if extra not in hierarchy:
        extra = "none"
    return primary if hierarchy[primary] >= hierarchy[extra] else extra


def _collect_ability_modifiers(
    attacker: UnitProfile, defender_keywords: Set[str], weapon: WeaponProfile
) -> _AppliedModifiers:
    result = _AppliedModifiers()
    modifiers = getattr(attacker, "ability_modifiers", None)
    if not modifiers:
        return result

    for modifier in modifiers:
        if not modifier.applies_to(weapon.type, defender_keywords):
            continue
        result.hit_modifier += modifier.hit_modifier
        result.wound_modifier += modifier.wound_modifier
        result.reroll_hits = _merge_reroll(result.reroll_hits, modifier.reroll_hits)
        result.reroll_wounds = _merge_reroll(result.reroll_wounds, modifier.reroll_wounds)
        if modifier.grant_twin_linked:
            result.grant_twin_linked = True
        if modifier.grant_torrent:
            result.grant_torrent = True
        if modifier.grant_blast:
            result.grant_blast = True
        if modifier.grant_assault:
            result.grant_assault = True
        if modifier.ignores_cover:
            result.ignores_cover = True
        if modifier.anti_rules:
            result.anti_rules.extend(modifier.anti_rules)
        if modifier.description:
            result.notes.append(modifier.description)
    return result


def _resolve_weapon(
    *,
    attacker: UnitProfile,
    defender: UnitProfile,
    weapon: WeaponProfile,
    context: EngagementContext,
) -> WeaponResult:
    defender_keywords = {keyword.lower() for keyword in defender.keywords}
    applied_modifiers = _collect_ability_modifiers(attacker, defender_keywords, weapon)
    weapon_assault = weapon.assault or applied_modifiers.grant_assault
    attacker_can_advance_and_shoot = getattr(attacker, "can_advance_and_shoot", False)

    advance_blocked = (
        weapon.type == "ranged"
        and context.attacker_advanced
        and not weapon_assault
        and not attacker_can_advance_and_shoot
    )
    if advance_blocked:
        ability_notes = _build_ability_notes(weapon)
        ability_notes.append("Cannot fire after advancing (weapon lacks Assault)")
        wound_roll_label = _wound_roll_label_for_weapon(weapon, defender.toughness)
        save_target, save_label = _effective_save(defender, weapon)
        return WeaponResult(
            weapon=weapon,
            attacks=0.0,
            hits=0.0,
            critical_hits=0.0,
            extra_hits=0.0,
            auto_wounds=0.0,
            devastating_wounds=0.0,
            wounds=0.0,
            unsaved_wounds_before_fnp=0.0,
            unsaved_wounds=0.0,
            expected_damage=0.0,
            hit_probability=0.0,
            wound_probability=0.0,
            critical_wound_probability=0.0,
            failed_save_probability=0.0,
            wound_roll_label=wound_roll_label,
            save_used_label=save_label,
            fnp_success_probability=0.0,
            target_fnp_label=defender.feel_no_pain_label,
            ability_notes=ability_notes,
            damage_cap_applied=None,
            target_wounds=defender.wounds,
        )

    attacks = weapon.attacks.average
    if weapon.type == "ranged" and weapon.rapid_fire is not None and context.target_within_half_range:
        attacks += weapon.rapid_fire

    weapon_heavy = weapon.heavy
    weapon_torrent = weapon.torrent or applied_modifiers.grant_torrent
    weapon_blast = weapon.blast or applied_modifiers.grant_blast
    weapon_auto_hits = weapon.auto_hits or weapon_torrent

    resolved_target_models = context.target_model_count
    if resolved_target_models is None:
        for candidate in (getattr(defender, "models_max", None), getattr(defender, "models_min", None)):
            if candidate is None:
                continue
            try:
                candidate_value = int(candidate)
            except (TypeError, ValueError):
                continue
            if candidate_value > 0:
                resolved_target_models = candidate_value
                break
    if resolved_target_models is None:
        resolved_target_models = 1

    blast_bonus_applied = 0.0
    if weapon_blast:
        if resolved_target_models >= 11:
            blast_bonus_applied = 2.0
        elif resolved_target_models >= 6:
            blast_bonus_applied = 1.0
        if blast_bonus_applied:
            attacks += blast_bonus_applied

    combined_hit_modifier = weapon.hit_modifier + applied_modifiers.hit_modifier
    combined_wound_modifier = weapon.wound_modifier + applied_modifiers.wound_modifier
    combined_hit_reroll = _merge_reroll(weapon.reroll_hits, applied_modifiers.reroll_hits)
    combined_wound_reroll = _merge_reroll(weapon.reroll_wounds, applied_modifiers.reroll_wounds)

    context_notes: List[str] = []
    if weapon.type == "ranged":
        if weapon.heavy and not context.attacker_moved:
            combined_hit_modifier += 1
            context_notes.append("Heavy: +1 to Hit (remained stationary)")
        elif weapon.heavy and context.attacker_moved:
            context_notes.append("Heavy: no bonus (moved)")

        if context.attacker_advanced and weapon_assault:
            if attacker_can_advance_and_shoot:
                context_notes.append("Advance & shoot ability: Assault penalty ignored")
            else:
                combined_hit_modifier -= 1
                context_notes.append("Assault: advanced this turn (-1 to Hit)")

        if context.attacker_advanced and attacker_can_advance_and_shoot and not weapon_assault:
            context_notes.append("Advance & shoot enabled by unit ability")

        if weapon.rapid_fire is not None:
            if context.target_within_half_range:
                context_notes.append("Rapid Fire active (additional attacks applied)")
            else:
                context_notes.append("Rapid Fire inactive (beyond half range)")

    uncapped_hit_modifier = combined_hit_modifier
    uncapped_wound_modifier = combined_wound_modifier
    combined_hit_modifier = _cap_roll_modifier(combined_hit_modifier)
    combined_wound_modifier = _cap_roll_modifier(combined_wound_modifier)
    if combined_hit_modifier != uncapped_hit_modifier:
        context_notes.append(f"Hit modifier capped at {combined_hit_modifier:+d}")
    if combined_wound_modifier != uncapped_wound_modifier:
        context_notes.append(f"Wound modifier capped at {combined_wound_modifier:+d}")

    if blast_bonus_applied:
        context_notes.append(f"Blast: +{blast_bonus_applied:g} Attacks (target models={resolved_target_models})")

    if weapon.twin_linked or applied_modifiers.grant_twin_linked:
        combined_wound_reroll = _merge_reroll(combined_wound_reroll, "all")

    hit_target = max(2, min(6, weapon.skill - combined_hit_modifier))
    if weapon_auto_hits:
        hit_probability = 1.0
        crit_hit_probability = 0.0
        hits = attacks
        critical_hits = 0.0
    else:
        hit_probability = _probability_success_with_reroll(hit_target, combined_hit_reroll)
        crit_hit_probability = _critical_probability(hit_target, combined_hit_reroll)
        hits = attacks * hit_probability
        critical_hits = attacks * crit_hit_probability

    extra_hits = critical_hits * weapon.sustained_hits if not weapon_auto_hits else 0.0
    total_hits = hits + extra_hits

    auto_wounds = critical_hits if weapon.lethal_hits and not weapon_auto_hits else 0.0
    hits_requiring_wound = max(total_hits - auto_wounds, 0.0)

    weapon_anti = weapon.anti_threshold_for(defender_keywords)
    ability_anti = None
    if applied_modifiers.anti_rules:
        matching_thresholds = [value for keyword, value in applied_modifiers.anti_rules if keyword in defender_keywords]
        if matching_thresholds:
            ability_anti = min(matching_thresholds)
    anti_threshold = None
    for candidate in (weapon_anti, ability_anti):
        if candidate is not None:
            anti_threshold = candidate if anti_threshold is None else min(anti_threshold, candidate)

    wound_probability, crit_wound_probability, wound_roll_label = _wound_probabilities_for_weapon(
        weapon=weapon,
        defender_toughness=defender.toughness,
        wound_modifier=combined_wound_modifier,
        wound_reroll=combined_wound_reroll,
        anti_threshold=anti_threshold,
    )

    wounds_from_roll = hits_requiring_wound * wound_probability

    devastating_wounds = 0.0
    normal_wounds_from_roll = wounds_from_roll
    if weapon.devastating_wounds:
        devastating_wounds = hits_requiring_wound * crit_wound_probability
        devastating_wounds = min(devastating_wounds, wounds_from_roll)
        normal_wounds_from_roll = max(wounds_from_roll - devastating_wounds, 0.0)

    wounds = auto_wounds + devastating_wounds + normal_wounds_from_roll

    weapon_ignores_cover = weapon.ignores_cover or applied_modifiers.ignores_cover
    cover_bonus = 1 if weapon.type == "ranged" and context.target_in_cover and not weapon_ignores_cover else 0
    if context.target_in_cover:
        if weapon_ignores_cover:
            context_notes.append("Ignores Cover")
        else:
            context_notes.append("Target in Cover (+1 Save)")

    save_target, save_label = _effective_save(defender, weapon, cover_bonus=cover_bonus)
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

    melta_bonus_applied = 0.0
    if context.target_within_half_range and getattr(weapon, "melta", None) is not None:
        melta_value = weapon.melta if weapon.melta is not None else 2
        try:
            melta_bonus = float(melta_value)
        except (TypeError, ValueError):
            melta_bonus = 0.0
        if melta_bonus > 0:
            melta_bonus_applied = melta_bonus
    damage_cap_applied = None
    if defender.damage_cap is not None:
        damage_cap_applied = defender.damage_cap

    if melta_bonus_applied:
        context_notes.append(f"Melta active (+{melta_bonus_applied:g} damage)")

    damage_per_wound, capped_damage_per_wound = _modified_damage_averages(
        weapon=weapon,
        defender=defender,
        melta_bonus=melta_bonus_applied,
    )
    expected_damage = unsaved_wounds * damage_per_wound
    models_destroyed = _expected_models_destroyed_from_damage(
        unsaved_wounds=unsaved_wounds,
        capped_damage_per_wound=capped_damage_per_wound,
        target_wounds=defender.wounds,
    )

    ability_notes = _build_ability_notes(weapon)
    if applied_modifiers.notes:
        ability_notes.extend(applied_modifiers.notes)
    if context_notes:
        ability_notes.extend(context_notes)
    if defender.damage_reduction:
        ability_notes.append(f"Target Damage Reduction {defender.damage_reduction:g}")

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
        wound_roll_label=wound_roll_label,
        save_used_label=save_label,
        fnp_success_probability=fnp_prob,
        target_fnp_label=defender.feel_no_pain_label,
        ability_notes=ability_notes,
        damage_cap_applied=damage_cap_applied,
        target_wounds=defender.wounds,
        models_destroyed=models_destroyed,
    )


def _required_wound_roll(strength: float, toughness: int) -> int:
    if strength >= toughness * 2:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if strength * 2 <= toughness:
        return 6
    return 5


def _wound_probabilities_for_weapon(
    *,
    weapon: WeaponProfile,
    defender_toughness: int,
    wound_modifier: int,
    wound_reroll: str,
    anti_threshold: Optional[int],
) -> Tuple[float, float, str]:
    wound_probability = 0.0
    crit_wound_probability = 0.0
    roll_labels: List[int] = []

    for strength, strength_probability in quantity_distribution(weapon.strength_label or weapon.strength):
        wound_roll = _required_wound_roll(strength, defender_toughness)
        roll_labels.append(wound_roll)
        wound_target = max(2, min(6, wound_roll - wound_modifier))

        def _wound_success(roll: int) -> bool:
            if roll <= 0:
                return False
            if anti_threshold is not None and roll >= anti_threshold:
                return True
            return roll >= wound_target

        wound_roll_probs = _final_roll_distribution(wound_reroll, _wound_success)
        wound_probability += strength_probability * sum(
            prob for value, prob in enumerate(wound_roll_probs) if _wound_success(value)
        )

        crit_threshold = max(2, min(6, anti_threshold)) if anti_threshold is not None else 6
        crit_wound_probability += strength_probability * sum(
            prob for value, prob in enumerate(wound_roll_probs) if value >= crit_threshold
        )

    return wound_probability, crit_wound_probability, _format_wound_roll_label(roll_labels)


def _wound_roll_label_for_weapon(weapon: WeaponProfile, defender_toughness: int) -> str:
    rolls = [
        _required_wound_roll(strength, defender_toughness)
        for strength, _probability in quantity_distribution(weapon.strength_label or weapon.strength)
    ]
    return _format_wound_roll_label(rolls)


def _format_wound_roll_label(rolls: List[int]) -> str:
    unique = sorted(set(rolls))
    if not unique:
        return "6+"
    if len(unique) == 1:
        return f"{unique[0]}+"
    return "/".join(f"{roll}+" for roll in unique)


def _cap_roll_modifier(value: int) -> int:
    return max(-1, min(1, value))


def _expected_models_destroyed_from_damage(
    *,
    unsaved_wounds: float,
    capped_damage_per_wound: float,
    target_wounds: Optional[int],
) -> Optional[float]:
    if target_wounds is None or target_wounds <= 0:
        return None
    return unsaved_wounds * (max(capped_damage_per_wound, 0.0) / target_wounds)


def _modified_damage_averages(
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


def _effective_save(defender: UnitProfile, weapon: WeaponProfile, *, cover_bonus: int = 0) -> Tuple[int, str]:
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


def _final_roll_distribution(reroll: str, success_check) -> List[float]:
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
    if weapon.twin_linked:
        notes.append("Twin-linked")
    if weapon.assault:
        notes.append("Assault")
    if weapon.heavy:
        notes.append("Heavy")
    if weapon.torrent:
        notes.append("Torrent")
    if weapon.ignores_cover:
        notes.append("Ignores Cover")
    if weapon.blast:
        notes.append("Blast")
    if weapon.melta is not None:
        notes.append(f"Melta {weapon.melta}" if weapon.melta else "Melta")
    if weapon.rapid_fire is not None:
        notes.append(f"Rapid Fire {weapon.rapid_fire}" if weapon.rapid_fire else "Rapid Fire")
    if weapon.anti_rules:
        anti_text = "/".join(sorted(f"{keyword.upper()} {threshold}+" for keyword, threshold in weapon.anti_rules))
        notes.append(f"Anti-{anti_text}")
    if weapon.auto_hits:
        notes.append("Auto-hitting")
    return notes
