from __future__ import annotations

from typing import List

from .ability_resolver import (
    build_ability_notes,
    collect_ability_modifiers,
    merge_reroll,
    normalise_keywords,
    resolve_anti_threshold,
)
from .context import EngagementContext
from .profiles import UnitProfile, WeaponProfile
from .results import WeaponResult
from .rules import Ruleset


def resolve_weapon(
    *,
    attacker: UnitProfile,
    defender: UnitProfile,
    weapon: WeaponProfile,
    context: EngagementContext,
    ruleset: Ruleset,
) -> WeaponResult:
    defender_keywords = normalise_keywords(defender.keywords)
    applied_modifiers = collect_ability_modifiers(attacker, defender_keywords, weapon)
    weapon_assault = weapon.assault or applied_modifiers.grant_assault
    attacker_can_advance_and_shoot = getattr(attacker, "can_advance_and_shoot", False)

    advance_decision = ruleset.advance_attack_decision(
        weapon,
        attacker_advanced=context.attacker_advanced,
        weapon_assault=weapon_assault,
        attacker_can_advance_and_shoot=attacker_can_advance_and_shoot,
    )
    if not advance_decision.can_attack:
        ability_notes = build_ability_notes(weapon)
        ability_notes.extend(advance_decision.notes)
        wound_roll_label = wound_roll_label_for_weapon(weapon, defender.toughness, ruleset=ruleset)
        _save_target, save_label = ruleset.effective_save(defender, weapon)
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

    weapon_torrent = weapon.torrent or applied_modifiers.grant_torrent
    weapon_blast = weapon.blast or applied_modifiers.grant_blast
    weapon_auto_hits = weapon.auto_hits or weapon_torrent

    attack_adjustment = ruleset.adjusted_attack_count(
        weapon,
        base_attacks=weapon.attacks.average,
        target_model_count=context.target_model_count,
        defender=defender,
        target_within_half_range=context.target_within_half_range,
        weapon_blast=weapon_blast,
    )
    attacks = attack_adjustment.attacks

    combined_hit_modifier = weapon.hit_modifier + applied_modifiers.hit_modifier
    combined_wound_modifier = weapon.wound_modifier + applied_modifiers.wound_modifier
    combined_hit_reroll = merge_reroll(weapon.reroll_hits, applied_modifiers.reroll_hits)
    combined_wound_reroll = merge_reroll(weapon.reroll_wounds, applied_modifiers.reroll_wounds)

    context_notes: List[str] = []
    context_notes.extend(attack_adjustment.notes)
    hit_adjustment = ruleset.ranged_hit_modifier(
        weapon,
        attacker_moved=context.attacker_moved,
        attacker_advanced=context.attacker_advanced,
        weapon_assault=weapon_assault,
        attacker_can_advance_and_shoot=attacker_can_advance_and_shoot,
    )
    combined_hit_modifier += hit_adjustment.modifier_delta
    context_notes.extend(hit_adjustment.notes)

    uncapped_hit_modifier = combined_hit_modifier
    uncapped_wound_modifier = combined_wound_modifier
    combined_hit_modifier = ruleset.cap_roll_modifier(combined_hit_modifier)
    combined_wound_modifier = ruleset.cap_roll_modifier(combined_wound_modifier)
    if combined_hit_modifier != uncapped_hit_modifier:
        context_notes.append(f"Hit modifier capped at {combined_hit_modifier:+d}")
    if combined_wound_modifier != uncapped_wound_modifier:
        context_notes.append(f"Wound modifier capped at {combined_wound_modifier:+d}")

    if weapon.twin_linked or applied_modifiers.grant_twin_linked:
        combined_wound_reroll = merge_reroll(combined_wound_reroll, "all")

    hit_roll = ruleset.hit_roll_resolution(
        weapon,
        attacks=attacks,
        hit_modifier=combined_hit_modifier,
        hit_reroll=combined_hit_reroll,
        weapon_auto_hits=weapon_auto_hits,
    )

    anti_threshold = resolve_anti_threshold(weapon, applied_modifiers, defender_keywords)

    wound_roll = ruleset.wound_roll_resolution(
        weapon=weapon,
        defender_toughness=defender.toughness,
        wound_modifier=combined_wound_modifier,
        wound_reroll=combined_wound_reroll,
        anti_threshold=anti_threshold,
    )

    wound_pool = ruleset.wound_pool_resolution(
        weapon,
        auto_wounds=hit_roll.auto_wounds,
        hits_requiring_wound=hit_roll.hits_requiring_wound,
        wound_probability=wound_roll.wound_probability,
        critical_wound_probability=wound_roll.critical_wound_probability,
    )

    weapon_ignores_cover = weapon.ignores_cover or applied_modifiers.ignores_cover
    save_resolution = ruleset.save_resolution(
        defender,
        weapon,
        target_in_cover=context.target_in_cover,
        weapon_ignores_cover=weapon_ignores_cover,
    )
    context_notes.extend(save_resolution.notes)

    damage_resolution = ruleset.damage_resolution(
        weapon,
        defender=defender,
        target_within_half_range=context.target_within_half_range,
    )
    context_notes.extend(damage_resolution.notes)
    damage_pipeline = ruleset.damage_pipeline_resolution(
        defender,
        save_resolution=save_resolution,
        wound_pool=wound_pool,
        auto_wounds=hit_roll.auto_wounds,
        damage_resolution=damage_resolution,
    )

    ability_notes = build_ability_notes(weapon)
    if applied_modifiers.notes:
        ability_notes.extend(applied_modifiers.notes)
    if context_notes:
        ability_notes.extend(context_notes)

    return WeaponResult(
        weapon=weapon,
        attacks=attacks,
        hits=hit_roll.total_hits,
        critical_hits=hit_roll.critical_hits,
        extra_hits=hit_roll.extra_hits,
        auto_wounds=hit_roll.auto_wounds,
        devastating_wounds=wound_pool.devastating_wounds,
        wounds=wound_pool.wounds,
        unsaved_wounds_before_fnp=damage_pipeline.unsaved_wounds_before_fnp,
        unsaved_wounds=damage_pipeline.unsaved_wounds,
        expected_damage=damage_pipeline.expected_damage,
        hit_probability=hit_roll.hit_probability,
        wound_probability=wound_roll.wound_probability,
        critical_wound_probability=wound_roll.critical_wound_probability,
        failed_save_probability=damage_pipeline.failed_save_probability,
        wound_roll_label=wound_roll.label,
        save_used_label=save_resolution.label,
        fnp_success_probability=damage_pipeline.fnp_success_probability,
        target_fnp_label=defender.feel_no_pain_label,
        ability_notes=ability_notes,
        damage_cap_applied=damage_resolution.damage_cap_applied,
        target_wounds=defender.wounds,
        models_destroyed=damage_pipeline.models_destroyed,
    )


def wound_roll_label_for_weapon(weapon: WeaponProfile, defender_toughness: int, *, ruleset: Ruleset) -> str:
    return ruleset.wound_roll_resolution(
        weapon,
        defender_toughness=defender_toughness,
        wound_modifier=0,
        wound_reroll="none",
        anti_threshold=None,
    ).label
