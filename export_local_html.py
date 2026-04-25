from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from warhammer.dice import quantity_distribution
from warhammer.datasheet import load_units_from_csv
from warhammer.profiles import UnitProfile, WeaponProfile


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = PROJECT_ROOT / "web" / "index.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "warhammer_calculator_local.html"


def _weapon_payload(weapon: WeaponProfile) -> dict[str, Any]:
    return {
        "name": weapon.name,
        "type": weapon.type,
        "attacks": weapon.attacks.label,
        "attacksAverage": weapon.attacks.average,
        "skill": weapon.skill,
        "skillLabel": weapon.skill_label,
        "strength": weapon.strength_label or str(weapon.strength),
        "strengthDistribution": quantity_distribution(weapon.strength_label or weapon.strength),
        "ap": weapon.ap,
        "damage": weapon.damage.label,
        "damageAverage": weapon.damage.average,
        "damageDistribution": quantity_distribution(weapon.damage.label),
        "keywords": weapon.keywords,
        "hitModifier": weapon.hit_modifier,
        "woundModifier": weapon.wound_modifier,
        "rerollHits": weapon.reroll_hits,
        "rerollWounds": weapon.reroll_wounds,
        "lethalHits": weapon.lethal_hits,
        "sustainedHits": weapon.sustained_hits,
        "devastatingWounds": weapon.devastating_wounds,
        "autoHits": weapon.auto_hits,
        "assault": weapon.assault,
        "heavy": weapon.heavy,
        "torrent": weapon.torrent,
        "twinLinked": weapon.twin_linked,
        "ignoresCover": weapon.ignores_cover,
        "blast": weapon.blast,
        "melta": weapon.melta,
        "rapidFire": weapon.rapid_fire,
        "antiRules": weapon.anti_rules,
    }


def _unit_payload(unit: UnitProfile) -> dict[str, Any]:
    return {
        "name": unit.name,
        "faction": unit.faction,
        "toughness": unit.toughness,
        "save": unit.save,
        "saveLabel": unit.save_label,
        "wounds": unit.wounds,
        "invulnerableSave": unit.invulnerable_save,
        "invulnerableLabel": unit.invulnerable_label,
        "feelNoPain": unit.feel_no_pain,
        "feelNoPainLabel": unit.feel_no_pain_label,
        "damageCap": unit.damage_cap,
        "damageReduction": unit.damage_reduction,
        "points": unit.points,
        "modelsMin": unit.models_min,
        "modelsMax": unit.models_max,
        "keywords": unit.keywords,
        "canAdvanceAndShoot": unit.can_advance_and_shoot,
        "weapons": [_weapon_payload(weapon) for weapon in unit.weapons],
        "abilityModifiers": [
            {
                **asdict(modifier),
                "target_keywords": sorted(modifier.target_keywords),
            }
            for modifier in unit.ability_modifiers
        ],
    }


def _local_script(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""
    const LOCAL_DATA = {data_json};
    const state = {{
      units: LOCAL_DATA.units,
      factions: LOCAL_DATA.factions,
      auditReport: LOCAL_DATA.auditReport || null,
      importDiff: LOCAL_DATA.importDiff || null,
      metadata: LOCAL_DATA.metadata || null,
      searchTimer: null,
      openMenu: null
    }};

    const el = (id) => document.getElementById(id);
    const fmt = (value) => Number(value || 0).toFixed(2);
    const pct = (value) => `${{Math.round(Number(value || 0) * 100)}}%`;
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({{
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\\"": "&quot;",
      "'": "&#39;"
    }}[char]));

    function unitSummary(unit) {{
      return {{
        name: unit.name,
        faction: unit.faction,
        toughness: unit.toughness,
        save: unit.saveLabel,
        wounds: unit.wounds,
        points: unit.points,
        models_min: unit.modelsMin,
        models_max: unit.modelsMax,
        keywords: unit.keywords || []
      }};
    }}

    function weaponDetail(weapon) {{
      return {{
        name: weapon.name,
        type: weapon.type,
        attacks: weapon.attacks,
        skill: weapon.skillLabel,
        strength: weapon.strength,
        ap: weapon.ap,
        damage: weapon.damage,
        keywords: weapon.keywords || []
      }};
    }}

    function loadHealth() {{
      el("status").textContent = `${{LOCAL_DATA.units.length}} units loaded locally`;
      return Promise.resolve();
    }}

    function renderFactions() {{
      const select = el("faction");
      const current = select.value;
      select.innerHTML = `<option value="">All factions</option>`;
      for (const faction of state.factions) {{
        const option = document.createElement("option");
        option.value = faction;
        option.textContent = faction;
        select.appendChild(option);
      }}
      select.value = state.factions.includes(current) ? current : "";
    }}

    function searchUnits(query = "") {{
      const needle = query.trim().toLowerCase();
      const faction = el("faction").value.toLowerCase();
      const matches = state.units
        .filter((unit) => !faction || String(unit.faction || "").toLowerCase() === faction)
        .filter((unit) => {{
          if (!needle) return true;
          return [unit.name, unit.faction || "", ...(unit.keywords || [])].join(" ").toLowerCase().includes(needle);
        }})
        .slice(0, 400);
      renderFactions();
      return Promise.resolve(matches.map(unitSummary));
    }}

    async function loadUnits(query = "") {{
      const units = await searchUnits(query);
      if (state.openMenu) renderDropdown(state.openMenu, units);
      return units;
    }}

    async function loadDataReview() {{
      return Promise.resolve({{
        audit_report: state.auditReport,
        import_diff: state.importDiff,
        metadata: state.metadata
      }});
    }}

    function queueUnitSearch(value = "") {{
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(() => {{
        loadUnits(value).catch((error) => {{
          el("error").textContent = error.message;
        }});
      }}, 120);
    }}

    function optionSubtitle(unit) {{
      const parts = [];
      if (unit.faction) parts.push(unit.faction);
      if (unit.points) parts.push(`${{unit.points}} pts`);
      parts.push(`T${{unit.toughness}} W${{unit.wounds}} Sv ${{unit.save}}`);
      return parts.join(" | ");
    }}

    function closeDropdown(field = state.openMenu) {{
      if (!field) return;
      el(`${{field}}-menu`).classList.remove("open");
      el(field).setAttribute("aria-expanded", "false");
      if (state.openMenu === field) state.openMenu = null;
    }}

    function renderDropdown(field, units) {{
      const menu = el(`${{field}}-menu`);
      const rows = units.slice(0, 80);
      if (!rows.length) {{
        menu.innerHTML = `<button class="combo-option" type="button" disabled>No matching units</button>`;
        return;
      }}
      menu.innerHTML = rows.map((unit) => `
        <button class="combo-option" type="button" role="option" data-unit="${{escapeHtml(unit.name)}}">
          ${{escapeHtml(unit.name)}}
          <span>${{escapeHtml(optionSubtitle(unit))}}</span>
        </button>
      `).join("");
      menu.querySelectorAll(".combo-option").forEach((button) => {{
        button.addEventListener("mousedown", (event) => {{
          event.preventDefault();
          el(field).value = button.dataset.unit;
          closeDropdown(field);
        }});
      }});
    }}

    async function openDropdown(field) {{
      if (state.openMenu && state.openMenu !== field) closeDropdown(state.openMenu);
      state.openMenu = field;
      el(field).setAttribute("aria-expanded", "true");
      const units = await searchUnits(el(field).value);
      renderDropdown(field, units);
      el(`${{field}}-menu`).classList.add("open");
    }}

    function contextPayload(prefix = "") {{
      const targetModelCount = el(`${{prefix}}target-model-count`).value.trim();
      return {{
        attacker_moved: el(`${{prefix}}moved`).checked,
        attacker_advanced: el(`${{prefix}}advanced`).checked,
        target_within_half_range: el(`${{prefix}}half-range`).checked,
        target_in_cover: el(`${{prefix}}cover`).checked,
        target_model_count: targetModelCount ? Number(targetModelCount) : null
      }};
    }}

    function requireUnit(name) {{
      const key = String(name || "").toLowerCase();
      const unit = state.units.find((candidate) => candidate.name.toLowerCase() === key);
      if (!unit) throw new Error(`Unknown unit: ${{name || "(blank)"}}`);
      return unit;
    }}

    function normalizeContext(context) {{
      const result = {{
        attacker_moved: Boolean(context.attacker_moved),
        attacker_advanced: Boolean(context.attacker_advanced),
        target_within_half_range: Boolean(context.target_within_half_range),
        target_in_cover: Boolean(context.target_in_cover),
        target_model_count: context.target_model_count || null
      }};
      if (result.attacker_advanced) result.attacker_moved = true;
      if (result.target_model_count !== null && result.target_model_count <= 0) result.target_model_count = null;
      return result;
    }}

    function mergeReroll(primary, extra) {{
      const hierarchy = {{ none: 0, ones: 1, all: 2 }};
      return (hierarchy[primary] || 0) >= (hierarchy[extra] || 0) ? primary : extra;
    }}

    function collectAbilityModifiers(attacker, defenderKeywords, weapon) {{
      const result = {{
        hit_modifier: 0,
        wound_modifier: 0,
        reroll_hits: "none",
        reroll_wounds: "none",
        grant_twin_linked: false,
        grant_torrent: false,
        grant_blast: false,
        grant_assault: false,
        ignores_cover: false,
        anti_rules: [],
        notes: []
      }};
      for (const modifier of attacker.abilityModifiers || []) {{
        if (weapon.type === "ranged" && modifier.applies_to_ranged === false) continue;
        if (weapon.type === "melee" && modifier.applies_to_melee === false) continue;
        const targetKeywords = modifier.target_keywords || [];
        if (targetKeywords.length && !targetKeywords.some((keyword) => defenderKeywords.has(keyword))) continue;
        result.hit_modifier += Number(modifier.hit_modifier || 0);
        result.wound_modifier += Number(modifier.wound_modifier || 0);
        result.reroll_hits = mergeReroll(result.reroll_hits, modifier.reroll_hits || "none");
        result.reroll_wounds = mergeReroll(result.reroll_wounds, modifier.reroll_wounds || "none");
        result.grant_twin_linked ||= Boolean(modifier.grant_twin_linked);
        result.grant_torrent ||= Boolean(modifier.grant_torrent);
        result.grant_blast ||= Boolean(modifier.grant_blast);
        result.grant_assault ||= Boolean(modifier.grant_assault);
        result.ignores_cover ||= Boolean(modifier.ignores_cover);
        if (modifier.anti_rules) result.anti_rules.push(...modifier.anti_rules);
        if (modifier.description) result.notes.push(modifier.description);
      }}
      return result;
    }}

    function probabilitySuccessOn(target) {{
      if (target >= 7) return 0;
      target = Math.max(2, Math.min(6, target));
      return (7 - target) / 6;
    }}

    function probabilitySuccessWithReroll(target, reroll) {{
      const base = probabilitySuccessOn(target);
      if (reroll === "all") return base + (1 - base) * base;
      if (reroll === "ones") return base + (1 / 6) * base;
      return base;
    }}

    function criticalProbability(target, reroll) {{
      const base = 1 / 6;
      if (reroll === "all") return base + (1 - probabilitySuccessOn(target)) * (1 / 6);
      if (reroll === "ones") return base + (1 / 6) * (1 / 6);
      return base;
    }}

    function finalRollDistribution(reroll, successCheck) {{
      const probabilities = Array(7).fill(0);
      for (let initial = 1; initial <= 6; initial += 1) {{
        const firstProb = 1 / 6;
        if (reroll === "all" && !successCheck(initial)) {{
          for (let rerolled = 1; rerolled <= 6; rerolled += 1) probabilities[rerolled] += firstProb * (1 / 6);
        }} else if (reroll === "ones" && initial === 1) {{
          for (let rerolled = 1; rerolled <= 6; rerolled += 1) probabilities[rerolled] += firstProb * (1 / 6);
        }} else {{
          probabilities[initial] += firstProb;
        }}
      }}
      return probabilities;
    }}

    function requiredWoundRoll(strength, toughness) {{
      if (strength >= toughness * 2) return 2;
      if (strength > toughness) return 3;
      if (strength === toughness) return 4;
      if (strength * 2 <= toughness) return 6;
      return 5;
    }}

    function formatWoundRollLabel(rolls) {{
      const unique = [...new Set(rolls)].sort((a, b) => a - b);
      if (!unique.length) return "6+";
      return unique.map((roll) => `${{roll}}+`).join("/");
    }}

    function woundProbabilitiesForWeapon(weapon, defenderToughness, woundMod, woundReroll, antiThreshold) {{
      let woundProbability = 0;
      let critWoundProbability = 0;
      const rolls = [];
      const strengthDistribution = weapon.strengthDistribution || [[Number(weapon.strength || 0), 1]];
      for (const [strength, strengthProbability] of strengthDistribution) {{
        const woundRoll = requiredWoundRoll(Number(strength), defenderToughness);
        rolls.push(woundRoll);
        const woundTarget = Math.max(2, Math.min(6, woundRoll - woundMod));
        const woundSuccess = (roll) => antiThreshold !== null && roll >= antiThreshold ? true : roll >= woundTarget;
        const woundDist = finalRollDistribution(woundReroll, woundSuccess);
        woundProbability += strengthProbability * woundDist.reduce((sum, prob, roll) => sum + (woundSuccess(roll) ? prob : 0), 0);
        const critThreshold = antiThreshold !== null ? Math.max(2, Math.min(6, antiThreshold)) : 6;
        critWoundProbability += strengthProbability * woundDist.reduce((sum, prob, roll) => sum + (roll >= critThreshold ? prob : 0), 0);
      }}
      return [woundProbability, critWoundProbability, formatWoundRollLabel(rolls)];
    }}

    function capRollModifier(value) {{
      return Math.max(-1, Math.min(1, value));
    }}

    function effectiveSave(defender, weapon, coverBonus = 0) {{
      let apValue = Number(weapon.ap || 0);
      if (apValue > 0) apValue = -apValue;
      let modified = defender.save - apValue;
      if (coverBonus) modified = Math.max(2, modified - coverBonus);
      modified = Math.max(2, Math.min(7, modified));
      if (defender.invulnerableSave !== null && defender.invulnerableSave !== undefined && defender.invulnerableSave < modified) {{
        return [defender.invulnerableSave, defender.invulnerableLabel || `${{defender.invulnerableSave}}+`];
      }}
      return [modified, `${{modified}}+`];
    }}

    function feelNoPainSuccessProbability(defender) {{
      if (defender.feelNoPain === null || defender.feelNoPain === undefined) return 0;
      const target = Math.max(2, Math.min(6, defender.feelNoPain));
      return (7 - target) / 6;
    }}

    function modifiedDamageAverages(weapon, defender, meltaBonus) {{
      let totalDamage = 0;
      let cappedDamage = 0;
      const cap = defender.damageCap === null || defender.damageCap === undefined ? null : Number(defender.damageCap);
      const targetWounds = defender.wounds > 0 ? Number(defender.wounds) : null;
      for (const [rawDamage, probability] of weapon.damageDistribution || [[weapon.damageAverage, 1]]) {{
        let modified = Math.max(Number(rawDamage) + meltaBonus - Number(defender.damageReduction || 0), 0);
        if (cap !== null) modified = Math.min(modified, cap);
        totalDamage += modified * probability;
        cappedDamage += (targetWounds !== null ? Math.min(modified, targetWounds) : modified) * probability;
      }}
      return [totalDamage, cappedDamage];
    }}

    function buildAbilityNotes(weapon) {{
      const notes = [];
      if (weapon.rerollHits !== "none") notes.push(weapon.rerollHits === "all" ? "Hit rerolls (all)" : "Hit rerolls (ones)");
      if (weapon.rerollWounds !== "none") notes.push(weapon.rerollWounds === "all" ? "Wound rerolls (all)" : "Wound rerolls (ones)");
      if (weapon.lethalHits) notes.push("Lethal Hits");
      if (weapon.sustainedHits) notes.push(`Sustained Hits ${{weapon.sustainedHits}}`);
      if (weapon.devastatingWounds) notes.push("Devastating Wounds");
      if (weapon.twinLinked) notes.push("Twin-linked");
      if (weapon.assault) notes.push("Assault");
      if (weapon.heavy) notes.push("Heavy");
      if (weapon.torrent) notes.push("Torrent");
      if (weapon.ignoresCover) notes.push("Ignores Cover");
      if (weapon.blast) notes.push("Blast");
      if (weapon.melta !== null && weapon.melta !== undefined) notes.push(weapon.melta ? `Melta ${{weapon.melta}}` : "Melta");
      if (weapon.rapidFire !== null && weapon.rapidFire !== undefined) notes.push(weapon.rapidFire ? `Rapid Fire ${{weapon.rapidFire}}` : "Rapid Fire");
      if (weapon.antiRules && weapon.antiRules.length) notes.push("Anti-" + weapon.antiRules.map(([kw, threshold]) => `${{kw.toUpperCase()}} ${{threshold}}+`).sort().join("/"));
      if (weapon.autoHits) notes.push("Auto-hitting");
      return notes;
    }}

    function evaluateWeapon(attacker, defender, weapon, context) {{
      const defenderKeywords = new Set((defender.keywords || []).map((keyword) => keyword.toLowerCase()));
      const applied = collectAbilityModifiers(attacker, defenderKeywords, weapon);
      const weaponAssault = weapon.assault || applied.grant_assault;
      const notes = [];
      if (weapon.type === "ranged" && context.attacker_advanced && !weaponAssault && !attacker.canAdvanceAndShoot) {{
        const [, , woundRollLabel] = woundProbabilitiesForWeapon(weapon, defender.toughness, 0, "none", null);
        const [, saveLabel] = effectiveSave(defender, weapon);
        return {{
          weapon: weaponDetail(weapon), attacks: 0, hits: 0, wounds: 0, unsaved_wounds: 0,
          expected_damage: 0, expected_models_destroyed: 0, hit_probability: 0, wound_probability: 0,
          failed_save_probability: 0, wound_roll: woundRollLabel, save: saveLabel,
          notes: [...buildAbilityNotes(weapon), "Cannot fire after advancing (weapon lacks Assault)"]
        }};
      }}

      let attacks = weapon.attacksAverage;
      if (weapon.type === "ranged" && weapon.rapidFire !== null && weapon.rapidFire !== undefined && context.target_within_half_range) {{
        attacks += weapon.rapidFire;
      }}
      let targetModels = context.target_model_count || defender.modelsMax || defender.modelsMin || 1;
      if (weapon.blast || applied.grant_blast) {{
        let blastBonus = targetModels >= 11 ? 2 : (targetModels >= 6 ? 1 : 0);
        if (blastBonus) {{
          attacks += blastBonus;
          notes.push(`Blast: +${{blastBonus}} Attacks (target models=${{targetModels}})`);
        }}
      }}

      let hitMod = Number(weapon.hitModifier || 0) + applied.hit_modifier;
      let woundMod = Number(weapon.woundModifier || 0) + applied.wound_modifier;
      let hitReroll = mergeReroll(weapon.rerollHits || "none", applied.reroll_hits);
      let woundReroll = mergeReroll(weapon.rerollWounds || "none", applied.reroll_wounds);
      if (weapon.type === "ranged") {{
        if (weapon.heavy && !context.attacker_moved) {{
          hitMod += 1;
          notes.push("Heavy: +1 to Hit (remained stationary)");
        }} else if (weapon.heavy && context.attacker_moved) {{
          notes.push("Heavy: no bonus (moved)");
        }}
        if (context.attacker_advanced && weaponAssault) {{
          if (attacker.canAdvanceAndShoot) notes.push("Advance & shoot ability: Assault penalty ignored");
          else {{
            hitMod -= 1;
            notes.push("Assault: advanced this turn (-1 to Hit)");
          }}
        }}
        if (weapon.rapidFire !== null && weapon.rapidFire !== undefined) {{
          notes.push(context.target_within_half_range ? "Rapid Fire active (additional attacks applied)" : "Rapid Fire inactive (beyond half range)");
        }}
      }}
      const uncappedHit = hitMod;
      const uncappedWound = woundMod;
      hitMod = capRollModifier(hitMod);
      woundMod = capRollModifier(woundMod);
      if (hitMod !== uncappedHit) notes.push(`Hit modifier capped at ${{hitMod >= 0 ? "+" : ""}}${{hitMod}}`);
      if (woundMod !== uncappedWound) notes.push(`Wound modifier capped at ${{woundMod >= 0 ? "+" : ""}}${{woundMod}}`);
      if (weapon.twinLinked || applied.grant_twin_linked) woundReroll = mergeReroll(woundReroll, "all");

      const weaponAutoHits = weapon.autoHits || weapon.torrent || applied.grant_torrent;
      const hitTarget = Math.max(2, Math.min(6, weapon.skill - hitMod));
      let hitProbability, critHitProbability, hits, criticalHits;
      if (weaponAutoHits) {{
        hitProbability = 1;
        critHitProbability = 0;
        hits = attacks;
        criticalHits = 0;
      }} else {{
        hitProbability = probabilitySuccessWithReroll(hitTarget, hitReroll);
        critHitProbability = criticalProbability(hitTarget, hitReroll);
        hits = attacks * hitProbability;
        criticalHits = attacks * critHitProbability;
      }}
      const extraHits = !weaponAutoHits ? criticalHits * Number(weapon.sustainedHits || 0) : 0;
      const totalHits = hits + extraHits;
      const autoWounds = weapon.lethalHits && !weaponAutoHits ? criticalHits : 0;
      const hitsRequiringWound = Math.max(totalHits - autoWounds, 0);
      const weaponAnti = (weapon.antiRules || []).filter(([kw]) => defenderKeywords.has(kw)).map(([, threshold]) => threshold);
      const abilityAnti = (applied.anti_rules || []).filter(([kw]) => defenderKeywords.has(kw)).map(([, threshold]) => threshold);
      const antiValues = [...weaponAnti, ...abilityAnti];
      const antiThreshold = antiValues.length ? Math.min(...antiValues) : null;
      const [woundProbability, critWoundProbability, woundRollLabel] = woundProbabilitiesForWeapon(
        weapon, defender.toughness, woundMod, woundReroll, antiThreshold
      );
      const woundsFromRoll = hitsRequiringWound * woundProbability;
      let devastatingWounds = 0;
      let normalWoundsFromRoll = woundsFromRoll;
      if (weapon.devastatingWounds) {{
        devastatingWounds = Math.min(hitsRequiringWound * critWoundProbability, woundsFromRoll);
        normalWoundsFromRoll = Math.max(woundsFromRoll - devastatingWounds, 0);
      }}

      const weaponIgnoresCover = weapon.ignoresCover || applied.ignores_cover;
      const coverBonus = weapon.type === "ranged" && context.target_in_cover && !weaponIgnoresCover ? 1 : 0;
      if (context.target_in_cover) notes.push(weaponIgnoresCover ? "Ignores Cover" : "Target in Cover (+1 Save)");
      const [saveTarget, saveLabel] = effectiveSave(defender, weapon, coverBonus);
      const failedSaveProbability = 1 - (saveTarget >= 7 ? 0 : probabilitySuccessOn(saveTarget));
      const woundsSubjectToSave = autoWounds + normalWoundsFromRoll;
      const unsavedBeforeFnp = woundsSubjectToSave * failedSaveProbability + devastatingWounds;
      const fnpProb = feelNoPainSuccessProbability(defender);
      const unsavedWounds = unsavedBeforeFnp * (1 - fnpProb);
      let meltaBonus = 0;
      if (context.target_within_half_range && weapon.melta !== null && weapon.melta !== undefined) {{
        meltaBonus = Number(weapon.melta || 0);
        if (meltaBonus > 0) notes.push(`Melta active (+${{meltaBonus}} damage)`);
      }}
      const [damagePerWound, cappedDamagePerWound] = modifiedDamageAverages(weapon, defender, meltaBonus);
      const expectedDamage = unsavedWounds * damagePerWound;
      const expectedModels = defender.wounds > 0 ? unsavedWounds * (Math.max(cappedDamagePerWound, 0) / defender.wounds) : null;
      if (defender.damageReduction) notes.push(`Target Damage Reduction ${{defender.damageReduction}}`);

      return {{
        weapon: weaponDetail(weapon),
        attacks,
        hits: totalHits,
        wounds: autoWounds + devastatingWounds + normalWoundsFromRoll,
        unsaved_wounds: unsavedWounds,
        expected_damage: expectedDamage,
        expected_models_destroyed: expectedModels,
        hit_probability: hitProbability,
        wound_probability: woundProbability,
        failed_save_probability: failedSaveProbability,
        wound_roll: woundRollLabel,
        save: saveLabel,
        notes: [...buildAbilityNotes(weapon), ...applied.notes, ...notes]
      }};
    }}

    function evaluateUnit(attacker, defender, mode, context) {{
      const weapons = attacker.weapons
        .filter((weapon) => weapon.type === mode)
        .map((weapon) => evaluateWeapon(attacker, defender, weapon, context));
      return {{
        total_damage: weapons.reduce((sum, row) => sum + row.expected_damage, 0),
        total_unsaved_wounds: weapons.reduce((sum, row) => sum + row.unsaved_wounds, 0),
        expected_models_destroyed: weapons.reduce((sum, row) => sum + (row.expected_models_destroyed || 0), 0),
        feel_no_pain_applied: weapons.some((row) => false),
        weapons
      }};
    }}

    async function calculate() {{
      el("error").textContent = "";
      if (!el("attacker").value.trim() || !el("defender").value.trim()) {{
        el("error").textContent = "Choose both units.";
        return;
      }}
      const button = el("calculate");
      button.disabled = true;
      try {{
        const attacker = requireUnit(el("attacker").value);
        const defender = requireUnit(el("defender").value);
        const mode = el("mode").value;
        const outgoingContext = normalizeContext(contextPayload("attacker-"));
        const incomingContext = normalizeContext(contextPayload("return-"));
        renderResults({{
          attacker: unitSummary(attacker),
          defender: unitSummary(defender),
          mode,
          outgoing: evaluateUnit(attacker, defender, mode, outgoingContext),
          incoming: evaluateUnit(defender, attacker, mode, incomingContext)
        }});
      }} catch (error) {{
        el("error").textContent = error.message;
      }} finally {{
        button.disabled = false;
      }}
    }}

    function renderUnit(unit, label) {{
      const keywords = (unit.keywords || []).slice(0, 8).map((keyword) => `<span class="chip">${{escapeHtml(keyword)}}</span>`).join("");
      const modelRange = unit.models_min && unit.models_max && unit.models_min !== unit.models_max
        ? `${{unit.models_min}}-${{unit.models_max}}`
        : (unit.models_min || unit.models_max || "unknown");
      return `
        <div class="unit-pane">
          <div class="small">${{escapeHtml(label)}}</div>
          <div class="unit-name">${{escapeHtml(unit.name)}}</div>
          <div class="small">${{escapeHtml(unit.faction || "No faction")}} | T${{unit.toughness}} W${{unit.wounds}} Sv ${{escapeHtml(unit.save)}} | ${{unit.points || 0}} pts | Models ${{modelRange}}</div>
          <div class="chips">${{keywords}}</div>
        </div>
      `;
    }}

    function metric(label, value) {{
      return `<div class="metric"><b>${{value}}</b><span>${{label}}</span></div>`;
    }}

    function renderBar(label, value, cls = "") {{
      const width = Math.max(0, Math.min(100, Number(value || 0) * 100));
      return `
        <div class="bar">
          <span>${{label}}</span>
          <div class="track"><div class="fill ${{cls}}" style="width:${{width}}%"></div></div>
          <span>${{pct(value)}}</span>
        </div>
      `;
    }}

    function renderWeapon(row) {{
      const notes = row.notes && row.notes.length ? row.notes.map(escapeHtml).join(", ") : "No special notes";
      return `
        <article class="weapon">
          <div class="weapon-head">
            <div>
              <div class="weapon-title">${{escapeHtml(row.weapon.name)}}</div>
              <div class="small">${{escapeHtml(row.weapon.type)}} | A${{escapeHtml(row.weapon.attacks)}} | ${{escapeHtml(row.weapon.skill)}} | S${{escapeHtml(row.weapon.strength)}} | AP${{row.weapon.ap}} | D${{escapeHtml(row.weapon.damage)}}</div>
            </div>
            <div><div class="small">Damage</div><b>${{fmt(row.expected_damage)}}</b></div>
            <div><div class="small">Models</div><b>${{fmt(row.expected_models_destroyed)}}</b></div>
            <div><div class="small">Hits</div><b>${{fmt(row.hits)}}</b></div>
            <div><div class="small">Unsaved</div><b>${{fmt(row.unsaved_wounds)}}</b></div>
          </div>
          <div class="bars">
            ${{renderBar("Hit", row.hit_probability)}}
            ${{renderBar("Wound", row.wound_probability, "wound")}}
            ${{renderBar("Fail save", row.failed_save_probability, "save")}}
          </div>
          <div class="notes">${{notes}}</div>
        </article>
      `;
    }}

    function renderWeaponList(result, label, fallback) {{
      const weapons = result.weapons.length
        ? result.weapons.map(renderWeapon).join("")
        : `<div class="empty">${{escapeHtml(fallback)}}</div>`;
      return `
        <div class="result-band">${{escapeHtml(label)}}</div>
        <div class="weapon-list">${{weapons}}</div>
      `;
    }}

    function matchupJudgement(payload) {{
      const outgoing = payload.outgoing.total_damage || 0;
      const incoming = payload.incoming.total_damage || 0;
      const attacker = payload.attacker;
      const defender = payload.defender;
      const delta = outgoing - incoming;
      const total = Math.max(outgoing + incoming, 0.01);
      const edge = Math.abs(delta) / total;
      const winner = delta >= 0 ? attacker.name : defender.name;
      let confidence = "narrow";
      if (edge >= 0.45) confidence = "decisive";
      else if (edge >= 0.22) confidence = "clear";
      const loserDamage = delta >= 0 ? incoming : outgoing;
      const winnerDamage = delta >= 0 ? outgoing : incoming;
      const reason = `${{winner}} is projected to deal ${{fmt(winnerDamage)}} damage while taking ${{fmt(loserDamage)}} in the return strike.`;
      const efficiency = attacker.points && defender.points
        ? ` Points context: ${{attacker.name}} is ${{attacker.points}} pts and ${{defender.name}} is ${{defender.points}} pts.`
        : "";
      return {{
        title: edge < 0.08 ? "AI judgement: too close to call" : `AI judgement: ${{winner}} favored (${{confidence}})`,
        body: edge < 0.08
          ? `The exchange is nearly even: ${{attacker.name}} deals ${{fmt(outgoing)}} expected damage and ${{defender.name}} returns ${{fmt(incoming)}}.${{efficiency}}`
          : `${{reason}}${{efficiency}}`
      }};
    }}

    function renderResults(payload) {{
      const outgoing = payload.outgoing;
      const incoming = payload.incoming;
      const judgement = matchupJudgement(payload);
      el("results").innerHTML = `
        <div class="summary">
          ${{metric("Outgoing damage", fmt(outgoing.total_damage))}}
          ${{metric("Outgoing models", fmt(outgoing.expected_models_destroyed))}}
          ${{metric("Return damage", fmt(incoming.total_damage))}}
          ${{metric("Return models", fmt(incoming.expected_models_destroyed))}}
        </div>
        <div class="duel">
          ${{renderUnit(payload.attacker, "Attacker")}}
          ${{renderUnit(payload.defender, "Defender")}}
        </div>
        <div class="judgement">
          <h3>${{escapeHtml(judgement.title)}}</h3>
          <p>${{escapeHtml(judgement.body)}}</p>
        </div>
        ${{renderWeaponList(outgoing, `${{payload.attacker.name}} attack`, `No ${{payload.mode}} weapons found for ${{payload.attacker.name}}.`)}}
        ${{renderWeaponList(incoming, `${{payload.defender.name}} return strike`, `No ${{payload.mode}} weapons found for ${{payload.defender.name}}.`)}}
      `;
    }}

    async function showDataReview() {{
      el("error").textContent = "";
      const button = el("data-review");
      button.disabled = true;
      try {{
        renderDataReview(await loadDataReview());
      }} catch (error) {{
        el("error").textContent = error.message;
      }} finally {{
        button.disabled = false;
      }}
    }}

    function renderDataReview(payload) {{
      const audit = payload.audit_report;
      const diff = payload.import_diff;
      const metadata = payload.metadata;
      if (!audit && !diff && !metadata) {{
        el("results").innerHTML = `<div class="empty">No generated audit or import diff files were found.</div>`;
        return;
      }}
      const source = metadata && metadata.source_revisions && metadata.source_revisions[0]
        ? metadata.source_revisions[0]
        : null;
      const generatedAt = metadata && metadata.generated_at ? metadata.generated_at : (audit && audit.generated_at ? audit.generated_at : "unknown");
      const commit = source && source.commit ? source.commit.slice(0, 12) : "unknown";
      const remote = source && source.remote_origin ? source.remote_origin : "unknown source";
      const summary = audit && audit.summary ? audit.summary : {{ error: 0, warning: 0, info: 0, total: 0 }};
      el("results").innerHTML = `
        <div class="review-head">
          <h2>Data Review</h2>
          <div class="review-meta">${{escapeHtml(remote)}} | ${{escapeHtml(commit)}} | generated ${{escapeHtml(generatedAt)}}</div>
        </div>
        <div class="summary">
          ${{metric("Audit errors", summary.error || 0)}}
          ${{metric("Warnings", summary.warning || 0)}}
          ${{metric("Info", summary.info || 0)}}
          ${{metric("Rows checked", audit && audit.row_counts ? Object.values(audit.row_counts).reduce((total, value) => total + Number(value || 0), 0) : 0)}}
        </div>
        ${{renderDiff(diff)}}
        ${{renderAuditSections(audit)}}
      `;
    }}

    function renderDiff(diff) {{
      if (!diff || !diff.tables) return `<div class="review-section"><h3>Import Diff</h3><div class="empty">No import diff available.</div></div>`;
      const rows = Object.entries(diff.tables).map(([name, row]) => `
        <div class="diff-row">
          <div><b>${{escapeHtml(name)}}</b></div>
          <div>${{row.before_count ?? 0}}</div>
          <div>${{row.after_count ?? 0}}</div>
          <div>${{Number(row.delta || 0) >= 0 ? "+" : ""}}${{row.delta ?? 0}}</div>
          <div>${{row.changed_count ?? 0}}</div>
        </div>
      `).join("");
      return `
        <div class="review-section">
          <h3>Import Diff</h3>
          <div class="diff-grid">
            <div class="diff-row diff-head"><div>Table</div><div>Before</div><div>After</div><div>Delta</div><div>Changed</div></div>
            ${{rows}}
          </div>
        </div>
      `;
    }}

    function renderAuditSections(audit) {{
      if (!audit || !audit.sections) return `<div class="review-section"><h3>Audit Findings</h3><div class="empty">No audit report available.</div></div>`;
      return Object.entries(audit.sections).map(([name, section]) => {{
        const issues = section.issues || [];
        const body = issues.length
          ? `<div class="issue-list">${{issues.map(renderIssue).join("")}}</div>`
          : `<div class="empty">No issues in this section.</div>`;
        return `<div class="review-section"><h3>${{escapeHtml(name.replace("_", " "))}}</h3>${{body}}</div>`;
      }}).join("");
    }}

    function renderIssue(issue) {{
      const samples = (issue.samples || []).slice(0, 8).map((sample) => `<li>${{escapeHtml(sample)}}</li>`).join("");
      return `
        <div class="issue ${{escapeHtml(issue.severity || "info")}}">
          <div class="issue-title">${{escapeHtml(issue.label || issue.key || "Issue")}}<span>${{escapeHtml(issue.severity || "info")}}</span></div>
          <ul class="issue-samples">${{samples}}</ul>
        </div>
      `;
    }}

    function setMode(mode) {{
      el("mode").value = mode;
      document.querySelectorAll(".segment").forEach((button) => {{
        const active = button.dataset.mode === mode;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      }});
    }}

    function swapContexts() {{
      const suffixes = ["target-model-count", "moved", "advanced", "half-range", "cover"];
      for (const suffix of suffixes) {{
        const left = el(`attacker-${{suffix}}`);
        const right = el(`return-${{suffix}}`);
        if (left.type === "checkbox") {{
          const checked = left.checked;
          left.checked = right.checked;
          right.checked = checked;
        }} else {{
          const value = left.value;
          left.value = right.value;
          right.value = value;
        }}
      }}
    }}

    function wireEvents() {{
      el("calculate").addEventListener("click", calculate);
      el("data-review").addEventListener("click", showDataReview);
      el("swap").addEventListener("click", () => {{
        const attacker = el("attacker").value;
        el("attacker").value = el("defender").value;
        el("defender").value = attacker;
        swapContexts();
      }});
      el("faction").addEventListener("change", () => loadUnits("").catch((error) => {{
        el("error").textContent = error.message;
      }}));
      document.querySelectorAll(".combo-toggle").forEach((button) => {{
        button.addEventListener("click", () => openDropdown(button.dataset.target).catch((error) => {{
          el("error").textContent = error.message;
        }}));
      }});
      document.addEventListener("click", (event) => {{
        if (state.openMenu && !event.target.closest(".unit-combo")) closeDropdown();
      }});
      document.querySelectorAll(".segment").forEach((button) => {{
        button.addEventListener("click", () => setMode(button.dataset.mode));
      }});
      for (const id of ["attacker", "defender"]) {{
        el(id).addEventListener("input", (event) => {{
          const value = event.target.value;
          if (value.length === 0 || value.length >= 2) {{
            state.openMenu = id;
            el(`${{id}}-menu`).classList.add("open");
            el(id).setAttribute("aria-expanded", "true");
            queueUnitSearch(value);
          }}
        }});
        el(id).addEventListener("focus", () => openDropdown(id).catch((error) => {{
          el("error").textContent = error.message;
        }}));
        el(id).addEventListener("keydown", (event) => {{
          if (event.key === "Enter") calculate();
          if (event.key === "Escape") closeDropdown(id);
        }});
      }}
    }}

    wireEvents();
    Promise.all([loadHealth(), loadUnits()]).catch((error) => {{
      el("status").textContent = "Data failed to load";
      el("error").textContent = error.message;
    }});
  """


def build_local_html(*, csv_dir: Path, template_path: Path, output_path: Path) -> None:
    units = sorted(load_units_from_csv(csv_dir).values(), key=lambda unit: unit.name.casefold())
    data = {
        "units": [_unit_payload(unit) for unit in units],
        "factions": sorted({unit.faction for unit in units if unit.faction}, key=str.casefold),
        "auditReport": _load_json(csv_dir / "audit_report.json"),
        "importDiff": _load_json(csv_dir / "import_diff.json"),
        "metadata": _load_json(csv_dir / "metadata.json"),
    }
    template = template_path.read_text(encoding="utf-8")
    start = template.index("  <script>")
    end = template.index("  </script>", start) + len("  </script>")
    replacement = "  <script>\n" + _local_script(data).rstrip() + "\n  </script>"
    output_path.write_text(template[:start] + replacement + template[end:], encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a standalone local HTML calculator")
    parser.add_argument("--csv-dir", type=Path, default=PROJECT_ROOT / "data" / "latest")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_local_html(csv_dir=args.csv_dir, template_path=args.template, output_path=args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
