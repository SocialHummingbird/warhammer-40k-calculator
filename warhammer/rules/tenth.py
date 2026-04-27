from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from warhammer.dice import quantity_distribution
from warhammer.profiles import UnitProfile, WeaponProfile
from warhammer.rules.base import (
    AdvanceAttackDecision,
    AttackCountAdjustment,
    DamagePipelineResolution,
    DamageResolution,
    HitModifierAdjustment,
    HitRollResolution,
    RuleCapability,
    SaveResolution,
    WoundPoolResolution,
    WoundRollResolution,
)


@dataclass(frozen=True)
class TenthEditionRules:
    """Warhammer 40,000 10th edition combat math currently supported by the app."""

    edition: str = "10e"
    label: str = "Warhammer 40,000 10th Edition"
    capabilities: Tuple[RuleCapability, ...] = (
        RuleCapability("hit_rolls", "Hit rolls, hit modifiers, and critical hits"),
        RuleCapability("hit_rerolls", "Hit rerolls"),
        RuleCapability("lethal_hits", "Lethal Hits"),
        RuleCapability("sustained_hits", "Sustained Hits"),
        RuleCapability("auto_hits", "Torrent and automatic hits"),
        RuleCapability("advance_firing", "Advance firing restrictions and Assault handling"),
        RuleCapability("heavy", "Heavy stationary hit bonus"),
        RuleCapability("rapid_fire", "Rapid Fire attack bonuses"),
        RuleCapability("blast", "Blast attack bonuses"),
        RuleCapability("wound_rolls", "Wound roll thresholds and wound modifiers"),
        RuleCapability("wound_rerolls", "Wound rerolls and Twin-linked"),
        RuleCapability("anti", "Anti keyword critical wounds"),
        RuleCapability("devastating_wounds", "Devastating Wounds pool splitting"),
        RuleCapability("save_resolution", "Armour, invulnerable, AP, cover, and Ignores Cover"),
        RuleCapability("feel_no_pain", "Feel No Pain damage prevention"),
        RuleCapability("melta", "Melta range damage bonuses"),
        RuleCapability("damage_reduction", "Flat damage reduction"),
        RuleCapability("damage_caps", "Defender damage caps"),
        RuleCapability("model_removal", "Expected model removal with overkill capping"),
    )

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

    def advance_attack_decision(
        self,
        weapon: WeaponProfile,
        *,
        attacker_advanced: bool,
        weapon_assault: bool,
        attacker_can_advance_and_shoot: bool,
    ) -> AdvanceAttackDecision:
        if (
            weapon.type == "ranged"
            and attacker_advanced
            and not weapon_assault
            and not attacker_can_advance_and_shoot
        ):
            return AdvanceAttackDecision(False, ("Cannot fire after advancing (weapon lacks Assault)",))
        return AdvanceAttackDecision(True)

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
        attacks = base_attacks
        notes: list[str] = []

        if weapon.type == "ranged" and weapon.rapid_fire is not None:
            if target_within_half_range:
                attacks += weapon.rapid_fire
                notes.append("Rapid Fire active (additional attacks applied)")
            else:
                notes.append("Rapid Fire inactive (beyond half range)")

        resolved_target_models = self.target_model_count(defender, target_model_count)
        blast_bonus = self.blast_attack_bonus(weapon_blast=weapon_blast, target_model_count=resolved_target_models)
        if blast_bonus:
            attacks += blast_bonus
            notes.append(f"Blast: +{blast_bonus:g} Attacks (target models={resolved_target_models})")

        return AttackCountAdjustment(attacks=attacks, target_model_count=resolved_target_models, notes=tuple(notes))

    def target_model_count(self, defender: UnitProfile, requested: Optional[int] = None) -> int:
        if requested is not None and requested > 0:
            return int(requested)
        for candidate in (getattr(defender, "models_max", None), getattr(defender, "models_min", None)):
            if candidate is None:
                continue
            try:
                candidate_value = int(candidate)
            except (TypeError, ValueError):
                continue
            if candidate_value > 0:
                return candidate_value
        return 1

    def blast_attack_bonus(self, *, weapon_blast: bool, target_model_count: int) -> float:
        if not weapon_blast:
            return 0.0
        if target_model_count >= 11:
            return 2.0
        if target_model_count >= 6:
            return 1.0
        return 0.0

    def ranged_hit_modifier(
        self,
        weapon: WeaponProfile,
        *,
        attacker_moved: bool,
        attacker_advanced: bool,
        weapon_assault: bool,
        attacker_can_advance_and_shoot: bool,
    ) -> HitModifierAdjustment:
        if weapon.type != "ranged":
            return HitModifierAdjustment()

        modifier = 0
        notes: list[str] = []
        if weapon.heavy and not attacker_moved:
            modifier += 1
            notes.append("Heavy: +1 to Hit (remained stationary)")
        elif weapon.heavy and attacker_moved:
            notes.append("Heavy: no bonus (moved)")

        if attacker_advanced and weapon_assault:
            if attacker_can_advance_and_shoot:
                notes.append("Advance & shoot ability: Assault penalty ignored")
            else:
                modifier -= 1
                notes.append("Assault: advanced this turn (-1 to Hit)")

        if attacker_advanced and attacker_can_advance_and_shoot and not weapon_assault:
            notes.append("Advance & shoot enabled by unit ability")

        return HitModifierAdjustment(modifier_delta=modifier, notes=tuple(notes))

    def hit_roll_resolution(
        self,
        weapon: WeaponProfile,
        *,
        attacks: float,
        hit_modifier: int,
        hit_reroll: str,
        weapon_auto_hits: bool,
    ) -> HitRollResolution:
        if weapon_auto_hits:
            hit_probability = 1.0
            critical_hit_probability = 0.0
            hits = attacks
            critical_hits = 0.0
        else:
            hit_target = max(2, min(6, weapon.skill - hit_modifier))
            hit_probability = self.probability_success_with_reroll(hit_target, hit_reroll)
            critical_hit_probability = self.critical_probability(hit_target, hit_reroll)
            hits = attacks * hit_probability
            critical_hits = attacks * critical_hit_probability

        extra_hits = critical_hits * weapon.sustained_hits if not weapon_auto_hits else 0.0
        total_hits = hits + extra_hits
        auto_wounds = critical_hits if weapon.lethal_hits and not weapon_auto_hits else 0.0
        hits_requiring_wound = max(total_hits - auto_wounds, 0.0)

        return HitRollResolution(
            hit_probability=hit_probability,
            critical_hit_probability=critical_hit_probability,
            hits=hits,
            critical_hits=critical_hits,
            extra_hits=extra_hits,
            total_hits=total_hits,
            auto_wounds=auto_wounds,
            hits_requiring_wound=hits_requiring_wound,
        )

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

    def save_resolution(
        self,
        defender: UnitProfile,
        weapon: WeaponProfile,
        *,
        target_in_cover: bool,
        weapon_ignores_cover: bool,
    ) -> SaveResolution:
        cover_bonus = 1 if weapon.type == "ranged" and target_in_cover and not weapon_ignores_cover else 0
        notes: list[str] = []
        if target_in_cover:
            if weapon_ignores_cover:
                notes.append("Ignores Cover")
            else:
                notes.append("Target in Cover (+1 Save)")
        target, label = self.effective_save(defender, weapon, cover_bonus=cover_bonus)
        return SaveResolution(target=target, label=label, notes=tuple(notes))

    def damage_resolution(
        self,
        weapon: WeaponProfile,
        defender: UnitProfile,
        *,
        target_within_half_range: bool,
    ) -> DamageResolution:
        melta_bonus = self.melta_bonus(weapon, target_within_half_range=target_within_half_range)
        damage_per_wound, capped_damage_per_wound = self.modified_damage_averages(
            weapon=weapon,
            defender=defender,
            melta_bonus=melta_bonus,
        )
        notes: list[str] = []
        if melta_bonus:
            notes.append(f"Melta active (+{melta_bonus:g} damage)")
        if defender.damage_reduction:
            notes.append(f"Target Damage Reduction {defender.damage_reduction:g}")
        return DamageResolution(
            damage_per_wound=damage_per_wound,
            capped_damage_per_wound=capped_damage_per_wound,
            damage_cap_applied=defender.damage_cap if defender.damage_cap is not None else None,
            notes=tuple(notes),
        )

    def wound_roll_resolution(
        self,
        weapon: WeaponProfile,
        *,
        defender_toughness: int,
        wound_modifier: int,
        wound_reroll: str,
        anti_threshold: Optional[int],
    ) -> WoundRollResolution:
        wound_probability = 0.0
        critical_wound_probability = 0.0
        roll_labels: list[int] = []

        for strength, strength_probability in quantity_distribution(weapon.strength_label or weapon.strength):
            wound_roll = self.required_wound_roll(strength, defender_toughness)
            roll_labels.append(wound_roll)
            wound_target = max(2, min(6, wound_roll - wound_modifier))

            def wound_success(roll: int) -> bool:
                if roll <= 0:
                    return False
                if anti_threshold is not None and roll >= anti_threshold:
                    return True
                return roll >= wound_target

            wound_roll_probs = self.final_roll_distribution(wound_reroll, wound_success)
            wound_probability += strength_probability * sum(
                prob for value, prob in enumerate(wound_roll_probs) if wound_success(value)
            )

            crit_threshold = max(2, min(6, anti_threshold)) if anti_threshold is not None else 6
            critical_wound_probability += strength_probability * sum(
                prob for value, prob in enumerate(wound_roll_probs) if value >= crit_threshold
            )

        return WoundRollResolution(
            wound_probability=wound_probability,
            critical_wound_probability=critical_wound_probability,
            label=self.format_wound_roll_label(roll_labels),
        )

    def wound_pool_resolution(
        self,
        weapon: WeaponProfile,
        *,
        auto_wounds: float,
        hits_requiring_wound: float,
        wound_probability: float,
        critical_wound_probability: float,
    ) -> WoundPoolResolution:
        wounds_from_roll = hits_requiring_wound * wound_probability
        devastating_wounds = 0.0
        normal_wounds_from_roll = wounds_from_roll
        if weapon.devastating_wounds:
            devastating_wounds = hits_requiring_wound * critical_wound_probability
            devastating_wounds = min(devastating_wounds, wounds_from_roll)
            normal_wounds_from_roll = max(wounds_from_roll - devastating_wounds, 0.0)
        return WoundPoolResolution(
            wounds=auto_wounds + devastating_wounds + normal_wounds_from_roll,
            devastating_wounds=devastating_wounds,
            normal_wounds_from_roll=normal_wounds_from_roll,
        )

    def damage_pipeline_resolution(
        self,
        defender: UnitProfile,
        *,
        save_resolution: SaveResolution,
        wound_pool: WoundPoolResolution,
        auto_wounds: float,
        damage_resolution: DamageResolution,
    ) -> DamagePipelineResolution:
        if save_resolution.target >= 7:
            save_success_probability = 0.0
        else:
            save_success_probability = self.probability_success_on(save_resolution.target)
        failed_save_probability = 1 - save_success_probability

        wounds_subject_to_save = auto_wounds + wound_pool.normal_wounds_from_roll
        unsaved_via_saves = wounds_subject_to_save * failed_save_probability
        unsaved_wounds_before_fnp = unsaved_via_saves + wound_pool.devastating_wounds

        fnp_probability = self.feel_no_pain_success_probability(defender)
        unsaved_wounds = unsaved_wounds_before_fnp * (1 - fnp_probability)
        expected_damage = unsaved_wounds * damage_resolution.damage_per_wound
        models_destroyed = self.expected_models_destroyed_from_damage(
            unsaved_wounds=unsaved_wounds,
            capped_damage_per_wound=damage_resolution.capped_damage_per_wound,
            target_wounds=defender.wounds,
        )

        return DamagePipelineResolution(
            failed_save_probability=failed_save_probability,
            fnp_success_probability=fnp_probability,
            unsaved_wounds_before_fnp=unsaved_wounds_before_fnp,
            unsaved_wounds=unsaved_wounds,
            expected_damage=expected_damage,
            models_destroyed=models_destroyed,
        )

    def format_wound_roll_label(self, rolls: list[int]) -> str:
        unique = sorted(set(rolls))
        if not unique:
            return "6+"
        if len(unique) == 1:
            return f"{unique[0]}+"
        return "/".join(f"{roll}+" for roll in unique)

    def melta_bonus(self, weapon: WeaponProfile, *, target_within_half_range: bool) -> float:
        if not target_within_half_range or getattr(weapon, "melta", None) is None:
            return 0.0
        melta_value = weapon.melta if weapon.melta is not None else 2
        try:
            return max(float(melta_value), 0.0)
        except (TypeError, ValueError):
            return 0.0

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
