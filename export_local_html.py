from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from warhammer.dice import quantity_distribution
from warhammer.data_review import (
    ability_modifier_summary,
    artifact_verification_report,
    loadout_summary,
    schema_summary,
    source_catalogue_summary,
    suspicious_weapon_summary,
    unit_profile_summary,
    unit_variant_summary,
    weapon_coverage_summary,
)
from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.profiles import UnitProfile, WeaponProfile


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "10e" / "latest"
LEGACY_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_TEMPLATE = PROJECT_ROOT / "web" / "index.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "warhammer_calculator_local.html"
DEFAULT_MODEL = PROJECT_ROOT / "models" / "10e" / "matchup_centroid_model.json"


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
        "sourceFile": weapon.source_file,
    }


def _unit_payload(unit: UnitProfile) -> dict[str, Any]:
    return {
        "id": unit.unit_id,
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
        "sourceFile": unit.source_file,
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
      editionStatus: LOCAL_DATA.editionStatus || null,
      artifactManifest: LOCAL_DATA.artifactManifest || null,
      verificationReport: LOCAL_DATA.verificationReport || null,
      suspiciousWeaponSummary: LOCAL_DATA.suspiciousWeaponSummary || null,
      unitProfileSummary: LOCAL_DATA.unitProfileSummary || null,
      updateReport: LOCAL_DATA.updateReport || null,
      profileReview: LOCAL_DATA.profileReview || null,
      editionReadiness: LOCAL_DATA.editionReadiness || null,
      modelAudit: LOCAL_DATA.modelAudit || null,
      modelComparison: LOCAL_DATA.modelComparison || null,
      reviewFiles: LOCAL_DATA.reviewFiles || [],
      modelFiles: LOCAL_DATA.modelFiles || [],
      mlModel: LOCAL_DATA.mlModel || null,
      mlModels: {{}},
      unitDetails: {{}},
      selectedUnitIds: {{ attacker: null, defender: null }},
      searchTimer: null,
      openMenu: null,
      rulesEdition: "10e",
      supportedRulesEditions: ["10e"],
      availableEditions: []
    }};

    const el = (id) => document.getElementById(id);
    const hasNumber = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
    const fmt = (value) => hasNumber(value) ? Number(value).toFixed(2) : "n/a";
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
        id: unit.id,
        name: unit.name,
        faction: unit.faction,
        toughness: unit.toughness,
        save: unit.saveLabel,
        wounds: unit.wounds,
        points: unit.points,
        models_min: unit.modelsMin,
        models_max: unit.modelsMax,
        source_file: unit.sourceFile || "",
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
        keywords: weapon.keywords || [],
        source_file: weapon.sourceFile || ""
      }};
    }}

    function loadHealth() {{
      const sourceInfo = sourceInfoFromMetadata(state.metadata);
      state.rulesEdition = sourceInfo.rules_edition || "10e";
      state.mlModels = state.mlModel ? {{ [state.rulesEdition]: modelStatus(state.mlModel) }} : {{}};
      state.rulesets = state.editionStatus ? {{ [state.rulesEdition]: rulesetStatus(state.editionStatus) }} : {{}};
      state.supportedRulesEditions = sourceInfo.supported_rules_editions || [state.rulesEdition];
      state.availableEditions = [{{
        edition: state.rulesEdition,
        label: editionLabel(state.rulesEdition),
        units: LOCAL_DATA.units.length,
        active: true,
        loaded: true,
        rules_available: true,
        status: "loaded",
        unavailable_reason: ""
      }}];
      renderEditionSelect();
      setStatus(LOCAL_DATA.units.length, sourceInfo, true, state.mlModels, state.rulesets);
      return Promise.resolve();
    }}

    function rulesetStatus(status) {{
      const capabilities = status && Array.isArray(status.rule_capabilities) ? status.rule_capabilities : [];
      return {{
        label: editionLabel(status && status.edition ? status.edition : state.rulesEdition),
        capability_count: capabilities.length,
        capabilities
      }};
    }}

    function modelStatus(model) {{
      const validation = model && model.validation ? model.validation : {{}};
      const trainingSource = model && model.training_source ? model.training_source : {{}};
      const featureHash = trainingSource.sha256 || "";
      return {{
        available: Boolean(model),
        model_type: model ? model.model_type : "",
        feature_set: model ? (model.feature_set || "custom") : "",
        label_source: model ? model.label_source : "",
        labels: model ? (model.labels || []) : [],
        training_rows: model ? (model.training_rows || 0) : 0,
        validation_rows: model ? (model.validation_rows || 0) : 0,
        validation_accuracy: validation.accuracy,
        feature_rows: trainingSource.rows || 0,
        feature_sha256: featureHash,
        feature_sha256_short: featureHash ? String(featureHash).slice(0, 12) : ""
      }};
    }}

    function renderEditionSelect() {{
      const select = el("edition");
      const editions = state.supportedRulesEditions.length ? state.supportedRulesEditions : ["10e"];
      select.innerHTML = editions.map((edition) => `<option value="${{escapeHtml(edition)}}">${{editionLabel(edition)}}</option>`).join("");
      select.value = editions.includes(state.rulesEdition) ? state.rulesEdition : editions[0];
      select.disabled = editions.length <= 1;
      const discovered = state.availableEditions.length
        ? state.availableEditions.map((row) => editionDiscoveryText(row)).join(" | ")
        : "";
      select.title = discovered || "Only the loaded edition is available for calculation.";
    }}

    function editionDiscoveryText(row) {{
      const label = row.label || editionLabel(row.edition);
      const status = row.active ? "loaded" : (row.status || (row.rules_available ? "available" : "blocked"));
      const reason = row.unavailable_reason ? `: ${{row.unavailable_reason}}` : "";
      return `${{label}}: ${{row.units || 0}} units (${{status}}${{reason}})`;
    }}

    function editionLabel(edition) {{
      if (edition === "10e") return "10th Edition";
      if (edition === "11e") return "11th Edition";
      return String(edition).toUpperCase();
    }}

    function sourceInfoFromMetadata(metadata) {{
      if (!metadata) return {{}};
      const source = metadata.source_revisions && metadata.source_revisions.length ? metadata.source_revisions[0] : {{}};
      const commit = source.commit || "";
      return {{
        commit,
        commit_short: commit ? commit.slice(0, 12) : "",
        branch: source.branch || metadata.github_ref || "",
        remote_origin: source.remote_origin || metadata.github_repo || "",
        dirty: Boolean(source.dirty),
        generated_at: metadata.generated_at || "",
        rules_edition: metadata.rules_edition || "10e",
        supported_rules_editions: metadata.supported_rules_editions || ["10e"]
      }};
    }}

    function setStatus(unitCount, sourceInfo = {{}}, locally = false, mlModels = {{}}, rulesets = {{}}) {{
      const parts = [`${{unitCount}} units loaded${{locally ? " locally" : ""}}`];
      if (sourceInfo.rules_edition) parts.push(`${{String(sourceInfo.rules_edition).toUpperCase()}} rules`);
      if (sourceInfo.commit_short) parts.push(`BSData ${{sourceInfo.commit_short}}`);
      const mlStatus = mlModels[sourceInfo.rules_edition || state.rulesEdition] || null;
      const ruleset = rulesets[sourceInfo.rules_edition || state.rulesEdition] || null;
      if (mlStatus && mlStatus.available) {{
        const accuracy = hasNumber(mlStatus.validation_accuracy)
          ? `${{Math.round(Number(mlStatus.validation_accuracy) * 100)}}%`
          : "n/a";
        parts.push(`ML ${{accuracy}}`);
      }}
      if (sourceInfo.dirty) parts.push("dirty source");
      if (sourceInfo.generated_at) parts.push(`generated ${{sourceInfo.generated_at}}`);
      el("status").textContent = parts.join(" | ");
      const titleParts = [];
      if (sourceInfo.remote_origin) titleParts.push(sourceInfo.remote_origin);
      if (sourceInfo.branch) titleParts.push(`branch ${{sourceInfo.branch}}`);
      if (sourceInfo.commit) titleParts.push(sourceInfo.commit);
      if (ruleset && ruleset.capability_count) {{
        const capabilityNames = (ruleset.capabilities || []).map((item) => item.label || item.key).filter(Boolean).slice(0, 8);
        titleParts.push(`Ruleset capabilities ${{ruleset.capability_count}}: ${{capabilityNames.join(", ")}}`);
      }}
      if (mlStatus && mlStatus.available) {{
        titleParts.push(`ML ${{mlStatus.model_type || "model"}}; feature set ${{mlStatus.feature_set || "custom"}}; training rows ${{mlStatus.training_rows || 0}}; feature rows ${{mlStatus.feature_rows || 0}}; feature hash ${{mlStatus.feature_sha256_short || "unknown"}}`);
      }}
      el("status").title = titleParts.join(" | ");
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
        metadata: state.metadata,
        edition_status: state.editionStatus,
        artifact_manifest: state.artifactManifest,
        verification_report: state.verificationReport,
        suspicious_weapon_summary: state.suspiciousWeaponSummary,
        unit_profile_summary: state.unitProfileSummary,
        loadout_summary: state.loadoutSummary,
        source_catalogue_summary: state.sourceCatalogueSummary,
        unit_variant_summary: state.unitVariantSummary,
        weapon_coverage_summary: state.weaponCoverageSummary,
        ability_modifier_summary: state.abilityModifierSummary,
        schema_summary: state.schemaSummary,
        update_report: state.updateReport,
        profile_review: state.profileReview,
        edition_readiness: state.editionReadiness,
        model_audit: state.modelAudit,
        model_comparison: state.modelComparison,
        review_files: state.reviewFiles,
        model_files: state.modelFiles
      }});
    }}

    function findUnit(name, unitId = null) {{
      if (unitId) {{
        const byId = state.units.find((candidate) => candidate.id === unitId);
        if (byId) return byId;
      }}
      const key = String(name || "").toLowerCase();
      return state.units.find((candidate) => candidate.name.toLowerCase() === key) || null;
    }}

    async function loadUnitDetail(name, field = null) {{
      const unitName = String(name || "").trim();
      const selectedId = field && state.selectedUnitIds[field] && el(field).value.trim() === unitName
        ? state.selectedUnitIds[field]
        : null;
      return findUnit(unitName, selectedId);
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

    function selectedUnit(field) {{
      const unitName = el(field).value.trim();
      if (!unitName) return null;
      const selectedId = state.selectedUnitIds[field];
      if (selectedId) {{
        const byId = state.units.find((unit) => unit.id === selectedId);
        if (byId) return byId;
        const cached = state.unitDetails[selectedId];
        if (cached) return cached;
      }}
      return state.units.find((unit) => unit.name === unitName) || null;
    }}

    function unitVariantLabel(unit) {{
      if (!unit) return "";
      const modelRange = unit.models_min && unit.models_max && unit.models_min !== unit.models_max
        ? `${{unit.models_min}}-${{unit.models_max}}`
        : (unit.models_min || unit.models_max || "unknown");
      const sourceFile = unit.source_file || unit.sourceFile || "";
      const parts = [];
      if (unit.faction) parts.push(unit.faction);
      if (unit.points) parts.push(`${{unit.points}} pts`);
      parts.push(`Models ${{modelRange}}`);
      if (sourceFile) parts.push(`Source ${{sourceFile}}`);
      if (unit.id) parts.push(`ID ${{unit.id}}`);
      return parts.join(" | ");
    }}

    function updateSelectedUnitInfo(field) {{
      const target = el(`${{field}}-selected`);
      const unit = selectedUnit(field);
      target.textContent = unit ? unitVariantLabel(unit) : "";
    }}

    function updateSelectedUnitInfos() {{
      updateSelectedUnitInfo("attacker");
      updateSelectedUnitInfo("defender");
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
        <button class="combo-option" type="button" role="option" data-unit="${{escapeHtml(unit.name)}}" data-unit-id="${{escapeHtml(unit.id || "")}}">
          ${{escapeHtml(unit.name)}}
          <span>${{escapeHtml(optionSubtitle(unit))}}</span>
        </button>
      `).join("");
      menu.querySelectorAll(".combo-option").forEach((button) => {{
        button.addEventListener("mousedown", (event) => {{
          event.preventDefault();
          el(field).value = button.dataset.unit;
          state.selectedUnitIds[field] = button.dataset.unitId || null;
          updateSelectedUnitInfo(field);
          closeDropdown(field);
          refreshWeaponSelectors().catch((error) => {{
            el("error").textContent = error.message;
          }});
        }});
      }});
    }}

    async function refreshWeaponSelectors() {{
      await Promise.all([
        populateWeaponSelect("outgoing-weapon", "attacker", el("attacker").value, el("mode").value),
        populateWeaponSelect("incoming-weapon", "defender", el("defender").value, el("mode").value)
      ]);
    }}

    async function populateWeaponSelect(selectId, field, unitName, mode) {{
      const select = el(selectId);
      const previous = select.value;
      select.innerHTML = `<option value="__all__">All matching weapons</option>`;
      const unit = await loadUnitDetail(unitName, field);
      if (!unit) {{
        select.disabled = true;
        return;
      }}
      const seen = new Set();
      const weapons = (unit.weapons || []).filter((weapon) => {{
        if (weapon.type !== mode || seen.has(weapon.name)) return false;
        seen.add(weapon.name);
        return true;
      }});
      for (const weapon of weapons) {{
        const option = document.createElement("option");
        option.value = weapon.name;
        option.textContent = `${{weapon.name}} | A${{weapon.attacks}} ${{weapon.skillLabel || weapon.skill}} S${{weapon.strength}} AP${{weapon.ap}} D${{weapon.damage}}`;
        select.appendChild(option);
      }}
      select.disabled = weapons.length === 0;
      select.value = [...select.options].some((option) => option.value === previous) ? previous : "__all__";
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

    function requireUnit(name, unitId = null) {{
      const unit = findUnit(name, unitId);
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

    function pointsBasisModels(unit) {{
      if (!unit) return null;
      if (unit.modelsMin && unit.modelsMax) return Math.max(1, Math.round((Number(unit.modelsMin) + Number(unit.modelsMax)) / 2));
      if (unit.modelsMax) return Math.max(1, Number(unit.modelsMax));
      if (unit.modelsMin) return Math.max(1, Number(unit.modelsMin));
      return 1;
    }}

    function pointsPerModel(unit) {{
      const models = pointsBasisModels(unit);
      return unit && unit.points && models ? Number(unit.points) / models : null;
    }}

    function pointsRemoved(unit, modelsDestroyed) {{
      const ppm = pointsPerModel(unit);
      return ppm === null || modelsDestroyed === null || modelsDestroyed === undefined ? null : Number(modelsDestroyed || 0) * ppm;
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

    function evaluateUnit(attacker, defender, mode, context, weaponName = null, multiplier = 1) {{
      const normalizedWeapon = String(weaponName || "").toLowerCase();
      const repeat = Math.max(1, Number(multiplier || 1));
      const filteredWeapons = attacker.weapons
        .filter((weapon) => weapon.type === mode)
        .filter((weapon) => !normalizedWeapon || normalizedWeapon === "__all__" || weapon.name.toLowerCase() === normalizedWeapon);
      if (normalizedWeapon && normalizedWeapon !== "__all__" && !filteredWeapons.length) {{
        throw new Error(`${{attacker.name}} has no ${{mode}} weapon named ${{weaponName}}`);
      }}
      const weapons = filteredWeapons
        .map((weapon) => scaleWeaponResult(evaluateWeapon(attacker, defender, weapon, context), repeat));
      return {{
        total_damage: weapons.reduce((sum, row) => sum + row.expected_damage, 0),
        total_unsaved_wounds: weapons.reduce((sum, row) => sum + row.unsaved_wounds, 0),
        expected_models_destroyed: weapons.reduce((sum, row) => sum + (row.expected_models_destroyed || 0), 0),
        estimated_points_removed: pointsRemoved(defender, weapons.reduce((sum, row) => sum + (row.expected_models_destroyed || 0), 0)),
        points_per_model: pointsPerModel(defender),
        feel_no_pain_applied: weapons.some((row) => false),
        weapons: weapons.map((row) => ({{
          ...row,
          estimated_points_removed: pointsRemoved(defender, row.expected_models_destroyed)
        }}))
      }};
    }}

    function scaleWeaponResult(row, multiplier) {{
      return {{
        ...row,
        attacks: row.attacks * multiplier,
        hits: row.hits * multiplier,
        wounds: row.wounds * multiplier,
        unsaved_wounds: row.unsaved_wounds * multiplier,
        expected_damage: row.expected_damage * multiplier,
        expected_models_destroyed: row.expected_models_destroyed * multiplier
      }};
    }}

    function attachMlJudgement(result, attacker, defender) {{
      const model = state.mlModel;
      if (!model || !model.feature_columns || !model.feature_stats) return result;
      const row = mlFeatureRow(result, attacker, defender);
      const prediction = predictMlRow(model, row);
      if (!prediction) return result;
      const label = prediction.label;
      const winner = label === "attacker" ? attacker.name : (label === "defender" ? defender.name : "");
      const accuracy = model.validation && hasNumber(model.validation.accuracy) ? Number(model.validation.accuracy) : null;
      const trainingSource = model.training_source || {{}};
      const featureHash = trainingSource.sha256 ? String(trainingSource.sha256).slice(0, 12) : "";
      const accuracyText = accuracy === null ? "unknown validation accuracy" : `${{Math.round(accuracy * 100)}}% validation accuracy`;
      const outcome = winner
        ? `The advisory model classifies ${{winner}} as favoured.`
        : "The advisory model classifies this as close.";
      const confidenceBasis = prediction.probabilities ? "probability-based" : "distance-based";
      result.ml_judgement = {{
        available: true,
        title: winner ? `ML advisory: ${{winner}} (${{Math.round(prediction.confidence * 100)}}%)` : `ML advisory: close matchup (${{Math.round(prediction.confidence * 100)}}%)`,
        body: `${{outcome}} Confidence is ${{confidenceBasis}} at ${{Math.round(prediction.confidence * 100)}}%; model has ${{accuracyText}}. Use this as an advisory signal only, not a rules result.`,
        winner_label: label,
        winner,
        confidence: prediction.confidence,
        model_type: model.model_type || "unknown",
        feature_set: model.feature_set || "custom",
        label_source: model.label_source || "",
        training_rows: model.training_rows || 0,
        feature_rows: trainingSource.rows || 0,
        feature_sha256_short: featureHash,
        validation_accuracy: accuracy
      }};
      return result;
    }}

    function mlFeatureRow(result, attacker, defender) {{
      const outgoing = result.outgoing || {{}};
      const incoming = result.incoming || {{}};
      const row = {{
        mode: result.mode,
        outgoing_damage: numberValue(outgoing.total_damage),
        outgoing_unsaved_wounds: numberValue(outgoing.total_unsaved_wounds),
        outgoing_models_destroyed: numberValue(outgoing.expected_models_destroyed),
        outgoing_points_removed: numberValue(outgoing.estimated_points_removed),
        incoming_damage: numberValue(incoming.total_damage),
        incoming_unsaved_wounds: numberValue(incoming.total_unsaved_wounds),
        incoming_models_destroyed: numberValue(incoming.expected_models_destroyed),
        incoming_points_removed: numberValue(incoming.estimated_points_removed)
      }};
      row.damage_delta = row.outgoing_damage - row.incoming_damage;
      row.points_removed_delta = row.outgoing_points_removed - row.incoming_points_removed;
      Object.assign(row, mlUnitFeatures(attacker, "attacker", result.mode));
      Object.assign(row, mlUnitFeatures(defender, "defender", result.mode));
      return row;
    }}

    function mlUnitFeatures(unit, prefix, mode) {{
      const models = pointsBasisModels(unit);
      const modeWeapons = (unit.weapons || []).filter((weapon) => weapon.type === mode);
      return {{
        [`${{prefix}}_points`]: unit.points || 0,
        [`${{prefix}}_models`]: models || 0,
        [`${{prefix}}_toughness`]: unit.toughness || 0,
        [`${{prefix}}_save`]: unit.save || 0,
        [`${{prefix}}_invulnerable_save`]: unit.invulnerableSave || 0,
        [`${{prefix}}_wounds`]: unit.wounds || 0,
        [`${{prefix}}_keywords_count`]: (unit.keywords || []).length,
        [`${{prefix}}_weapon_count`]: (unit.weapons || []).length,
        [`${{prefix}}_mode_weapon_count`]: modeWeapons.length,
        [`${{prefix}}_points_per_model`]: pointsPerModel(unit) || 0,
        [`${{prefix}}_mode_avg_attacks`]: average(modeWeapons.map((weapon) => weapon.attacksAverage)),
        [`${{prefix}}_mode_max_attacks`]: maximum(modeWeapons.map((weapon) => weapon.attacksAverage)),
        [`${{prefix}}_mode_avg_skill`]: average(modeWeapons.map((weapon) => weapon.skill)),
        [`${{prefix}}_mode_avg_strength`]: average(modeWeapons.map((weapon) => weapon.strength)),
        [`${{prefix}}_mode_max_strength`]: maximum(modeWeapons.map((weapon) => weapon.strength)),
        [`${{prefix}}_mode_avg_ap`]: average(modeWeapons.map((weapon) => weapon.ap)),
        [`${{prefix}}_mode_best_ap`]: minimum(modeWeapons.map((weapon) => weapon.ap)),
        [`${{prefix}}_mode_avg_damage`]: average(modeWeapons.map((weapon) => weapon.damageAverage)),
        [`${{prefix}}_mode_max_damage`]: maximum(modeWeapons.map((weapon) => weapon.damageAverage)),
        [`${{prefix}}_mode_keyword_count`]: modeWeapons.reduce((sum, weapon) => sum + (weapon.keywords || []).length, 0),
        [`${{prefix}}_mode_special_rule_count`]: modeWeapons.reduce((sum, weapon) => sum + specialRuleCount(weapon), 0)
      }};
    }}

    function average(values) {{
      const numbers = values.map(numberValue);
      return numbers.length ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : 0;
    }}

    function maximum(values) {{
      const numbers = values.map(numberValue);
      return numbers.length ? Math.max(...numbers) : 0;
    }}

    function minimum(values) {{
      const numbers = values.map(numberValue);
      return numbers.length ? Math.min(...numbers) : 0;
    }}

    function specialRuleCount(weapon) {{
      return [
        weapon.lethalHits,
        weapon.sustainedHits,
        weapon.devastatingWounds,
        weapon.autoHits,
        weapon.assault,
        weapon.heavy,
        weapon.torrent,
        weapon.twinLinked,
        weapon.ignoresCover,
        weapon.blast,
        weapon.melta,
        weapon.rapidFire,
        weapon.antiRules && weapon.antiRules.length
      ].filter(Boolean).length;
    }}

    function predictMlRow(model, row) {{
      const columns = model.feature_columns || [];
      const stats = model.feature_stats || {{}};
      const values = columns.map((column) => {{
        const stat = stats[column] || {{ mean: 0, std: 1 }};
        return (numberValue(row[column]) - Number(stat.mean || 0)) / (Number(stat.std || 1) || 1);
      }});
      if (model.model_type === "logistic_regression_classifier") {{
        const probabilities = logisticProbabilities(model, values);
        const entries = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);
        if (!entries.length) return null;
        return {{ label: entries[0][0], confidence: entries[0][1], probabilities }};
      }}
      const distances = {{}};
      for (const [label, centroid] of Object.entries(model.centroids || {{}})) {{
        distances[label] = Math.sqrt(values.reduce((sum, value, index) => sum + Math.pow(value - Number(centroid[index] || 0), 2), 0));
      }}
      const entries = Object.entries(distances).sort((a, b) => a[1] - b[1]);
      if (!entries.length) return null;
      const nearest = entries[0];
      const next = entries[1] ? entries[1][1] : nearest[1];
      const confidence = next > 0 ? Math.max(0, Math.min(1, (next - nearest[1]) / next)) : 1;
      return {{ label: nearest[0], confidence, distances }};
    }}

    function logisticProbabilities(model, values) {{
      const labels = (model.labels || []).map(String);
      const coefficients = model.coefficients || [];
      const intercepts = model.intercepts || [];
      if (labels.length === 2 && coefficients.length === 1) {{
        const logit = linearScore(values, coefficients[0], numberValue(intercepts[0]));
        const positive = 1 / (1 + Math.exp(-clipLogit(logit)));
        return {{ [labels[0]]: 1 - positive, [labels[1]]: positive }};
      }}
      const scores = labels.map((_, index) => linearScore(values, coefficients[index] || [], numberValue(intercepts[index])));
      const probabilities = softmax(scores);
      return Object.fromEntries(labels.map((label, index) => [label, probabilities[index] || 0]));
    }}

    function linearScore(values, coefficients, intercept) {{
      return values.reduce((sum, value, index) => sum + value * numberValue(coefficients[index]), intercept || 0);
    }}

    function softmax(scores) {{
      if (!scores.length) return [];
      const maxScore = Math.max(...scores);
      const exponents = scores.map((score) => Math.exp(clipLogit(score - maxScore)));
      const total = exponents.reduce((sum, value) => sum + value, 0) || 1;
      return exponents.map((value) => value / total);
    }}

    function clipLogit(value) {{
      return Math.max(-60, Math.min(60, numberValue(value)));
    }}

    function numberValue(value) {{
      const number = Number(value);
      return Number.isFinite(number) ? number : 0;
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
        const attacker = requireUnit(el("attacker").value, state.selectedUnitIds.attacker);
        const defender = requireUnit(el("defender").value, state.selectedUnitIds.defender);
        const mode = el("mode").value;
        const outgoingContext = normalizeContext(contextPayload("attacker-"));
        const incomingContext = normalizeContext(contextPayload("return-"));
        const result = {{
          attacker: unitSummary(attacker),
          defender: unitSummary(defender),
          edition: el("edition").value || state.rulesEdition,
          mode,
          weapon_filters: {{
            outgoing: el("outgoing-weapon").value === "__all__" ? null : el("outgoing-weapon").value,
            incoming: el("incoming-weapon").value === "__all__" ? null : el("incoming-weapon").value
          }},
          multipliers: {{
            outgoing: Number(el("outgoing-multiplier").value || 1),
            incoming: Number(el("incoming-multiplier").value || 1)
          }},
          outgoing: evaluateUnit(attacker, defender, mode, outgoingContext, el("outgoing-weapon").value, el("outgoing-multiplier").value),
          incoming: evaluateUnit(defender, attacker, mode, incomingContext, el("incoming-weapon").value, el("incoming-multiplier").value)
        }};
        renderResults(attachMlJudgement(result, attacker, defender));
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
      const sourceLine = unit.source_file ? `<div class="small">Source ${{escapeHtml(unit.source_file)}}</div>` : "";
      return `
        <div class="unit-pane">
          <div class="small">${{escapeHtml(label)}}</div>
          <div class="unit-name">${{escapeHtml(unit.name)}}</div>
          <div class="small">${{escapeHtml(unit.faction || "No faction")}} | T${{unit.toughness}} W${{unit.wounds}} Sv ${{escapeHtml(unit.save)}} | ${{unit.points || 0}} pts | Models ${{modelRange}}</div>
          ${{sourceLine}}
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
      const source = row.weapon.source_file ? ` | Source ${{escapeHtml(row.weapon.source_file)}}` : "";
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
          <div class="notes">${{notes}} | Points removed ${{fmt(row.estimated_points_removed)}}${{source}}</div>
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

    function scopeText(payload, side) {{
      const filters = payload.weapon_filters || {{}};
      const multipliers = payload.multipliers || {{}};
      const weapon = filters[side] || "all matching weapons";
      const count = Math.max(1, Number(multipliers[side] || 1));
      return `${{weapon}} x${{count}}`;
    }}

    function loadoutWarnings(payload) {{
      const filters = payload.weapon_filters || {{}};
      const rows = [];
      const outgoingCount = payload.outgoing && payload.outgoing.weapons ? payload.outgoing.weapons.length : 0;
      const incomingCount = payload.incoming && payload.incoming.weapons ? payload.incoming.weapons.length : 0;
      if (!filters.outgoing && outgoingCount >= 8) {{
        rows.push(`${{payload.attacker.name}} attack includes ${{outgoingCount}} imported ${{payload.mode}} weapon profiles. Select specific weapons for a real loadout.`);
      }}
      if (!filters.incoming && incomingCount >= 8) {{
        rows.push(`${{payload.defender.name}} return strike includes ${{incomingCount}} imported ${{payload.mode}} weapon profiles. Select specific weapons for a real loadout.`);
      }}
      return rows;
    }}

    function renderLoadoutWarnings(payload) {{
      const warnings = loadoutWarnings(payload);
      if (!warnings.length) return "";
      return `<div class="loadout-warning">${{warnings.map(escapeHtml).join("<br>")}}</div>`;
    }}

    function matchupJudgement(payload) {{
      if (payload.judgement) return payload.judgement;
      const hasPoints = hasNumber(payload.outgoing.estimated_points_removed) && hasNumber(payload.incoming.estimated_points_removed);
      const outgoingPoints = hasPoints ? Number(payload.outgoing.estimated_points_removed) : 0;
      const incomingPoints = hasPoints ? Number(payload.incoming.estimated_points_removed) : 0;
      const outgoing = hasPoints ? outgoingPoints : (payload.outgoing.total_damage || 0);
      const incoming = hasPoints ? incomingPoints : (payload.incoming.total_damage || 0);
      const attacker = payload.attacker;
      const defender = payload.defender;
      const basisLabel = hasPoints ? "estimated points removed" : "expected damage";
      const delta = outgoing - incoming;
      const total = Math.max(outgoing + incoming, 0.01);
      const edge = Math.abs(delta) / total;
      const winner = delta >= 0 ? attacker.name : defender.name;
      let confidence = "narrow";
      if (edge >= 0.45) confidence = "decisive";
      else if (edge >= 0.22) confidence = "clear";
      const loserScore = delta >= 0 ? incoming : outgoing;
      const winnerScore = delta >= 0 ? outgoing : incoming;
      const reason = hasPoints
        ? `${{winner}} is favored on estimated points removed, scoring ${{fmt(winnerScore)}} while giving up ${{fmt(loserScore)}} in return.`
        : `${{winner}} is projected to deal ${{fmt(winnerScore)}} damage while taking ${{fmt(loserScore)}} in the return strike.`;
      const efficiency = attacker.points && defender.points
        ? ` Points context: ${{attacker.name}} is ${{attacker.points}} pts and ${{defender.name}} is ${{defender.points}} pts.`
        : "";
      const damageContext = hasPoints
        ? ` Damage context: ${{attacker.name}} deals ${{fmt(payload.outgoing.total_damage)}} and ${{defender.name}} returns ${{fmt(payload.incoming.total_damage)}}.`
        : "";
      return {{
        title: edge < 0.08 ? "AI judgement: too close to call" : `AI judgement: ${{winner}} favored (${{confidence}})`,
        body: edge < 0.08
          ? `The exchange is nearly even on ${{basisLabel}}: ${{attacker.name}} scores ${{fmt(outgoing)}} and ${{defender.name}} returns ${{fmt(incoming)}}.${{hasPoints ? damageContext : efficiency}}`
          : `${{reason}}${{hasPoints ? damageContext : efficiency}}`
      }};
    }}

    function renderMlJudgement(payload) {{
      const judgement = payload.ml_judgement;
      if (!judgement || !judgement.available) return "";
      const accuracy = hasNumber(judgement.validation_accuracy)
        ? `${{Math.round(Number(judgement.validation_accuracy) * 100)}}%`
        : "n/a";
      return `
        <div class="judgement ml">
          <h3>${{escapeHtml(judgement.title || "ML advisory")}}</h3>
          <p>${{escapeHtml(judgement.body || "")}}</p>
          <p class="small">Model: ${{escapeHtml(judgement.model_type || "unknown")}} | Feature set: ${{escapeHtml(judgement.feature_set || "custom")}} | Training rows: ${{escapeHtml(judgement.training_rows || 0)}} | Feature rows: ${{escapeHtml(judgement.feature_rows || 0)}} | Feature hash: ${{escapeHtml(judgement.feature_sha256_short || "unknown")}} | Validation accuracy: ${{escapeHtml(accuracy)}}</p>
        </div>
      `;
    }}

    function renderResults(payload) {{
      state.lastResult = payload;
      const outgoing = payload.outgoing;
      const incoming = payload.incoming;
      const judgement = matchupJudgement(payload);
      el("results").innerHTML = `
        <div class="summary">
          ${{metric("Outgoing damage", fmt(outgoing.total_damage))}}
          ${{metric("Outgoing models", fmt(outgoing.expected_models_destroyed))}}
          ${{metric("Outgoing points", fmt(outgoing.estimated_points_removed))}}
          ${{metric("Return damage", fmt(incoming.total_damage))}}
          ${{metric("Return models", fmt(incoming.expected_models_destroyed))}}
          ${{metric("Return points", fmt(incoming.estimated_points_removed))}}
        </div>
        <div class="duel">
          ${{renderUnit(payload.attacker, "Attacker")}}
          ${{renderUnit(payload.defender, "Defender")}}
        </div>
        <div class="judgement">
          <h3>${{escapeHtml(judgement.title)}}</h3>
          <p>${{escapeHtml(judgement.body)}}</p>
          <p class="small">Edition: ${{escapeHtml(editionLabel(payload.edition || state.rulesEdition))}} | Attacker scope: ${{escapeHtml(scopeText(payload, "outgoing"))}} | Return scope: ${{escapeHtml(scopeText(payload, "incoming"))}}</p>
        </div>
        ${{renderMlJudgement(payload)}}
        ${{renderLoadoutWarnings(payload)}}
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
      const editionStatus = payload.edition_status;
      const artifactManifest = payload.artifact_manifest;
      const verificationReport = payload.verification_report;
      const suspiciousWeapons = payload.suspicious_weapon_summary;
      const unitProfiles = payload.unit_profile_summary;
      const loadouts = payload.loadout_summary;
      const sourceCatalogues = payload.source_catalogue_summary;
      const unitVariants = payload.unit_variant_summary;
      const weaponCoverage = payload.weapon_coverage_summary;
      const abilityModifiers = payload.ability_modifier_summary;
      const schema = payload.schema_summary;
      const updateReport = payload.update_report;
      const profileReview = payload.profile_review;
      const editionReadiness = payload.edition_readiness;
      const modelAudit = payload.model_audit;
      const modelComparison = payload.model_comparison;
      const reviewFiles = payload.review_files || [];
      const modelFiles = payload.model_files || [];
      if (!audit && !diff && !metadata && !editionStatus && !artifactManifest && !verificationReport && !suspiciousWeapons && !unitProfiles && !loadouts && !sourceCatalogues && !unitVariants && !weaponCoverage && !abilityModifiers && !schema && !updateReport && !profileReview && !editionReadiness && !modelAudit && !modelComparison) {{
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
          ${{editionStatus ? metric("Edition status", escapeHtml(editionStatus.status || "unknown")) : ""}}
          ${{verificationReport ? metric("Verified checks", `${{verificationReport.ok_count || 0}}/${{verificationReport.artifact_count || 0}}`) : ""}}
        </div>
        ${{renderProvenance(artifactManifest, verificationReport, metadata)}}
        ${{renderEditionStatus(editionStatus)}}
        ${{renderEditionReadiness(editionReadiness)}}
        ${{renderSchemaReview(schema)}}
        ${{renderSuspiciousWeapons(suspiciousWeapons)}}
        ${{renderUnitProfiles(unitProfiles)}}
        ${{renderLoadouts(loadouts)}}
        ${{renderSourceCatalogues(sourceCatalogues)}}
        ${{renderUnitVariants(unitVariants)}}
        ${{renderWeaponCoverage(weaponCoverage)}}
        ${{renderAbilityModifiers(abilityModifiers)}}
        ${{renderReviewFiles([...reviewFiles, ...modelFiles])}}
        ${{renderModelComparison(modelComparison)}}
        ${{renderModelAudit(modelAudit)}}
        ${{renderUpdateReport(updateReport)}}
        ${{renderProfileReview(profileReview)}}
        ${{renderDiff(diff)}}
        ${{renderAuditSections(audit)}}
      `;
    }}

    function renderSuspiciousWeapons(summary) {{
      if (!summary) return "";
      const severityCards = Object.entries(summary.by_severity || {{}}).map(([key, value]) => provenanceCard(`Severity: ${{key}}`, value, ""));
      const categoryCards = Object.entries(summary.by_category || {{}}).map(([key, value]) => provenanceCard(`Category: ${{key}}`, value, ""));
      const reasonRows = Object.entries(summary.by_reason || {{}}).slice(0, 8).map(([reason, count]) => `
        <div class="check-row">
          <div>${{escapeHtml(reason)}}</div>
          <div><span class="status-pill">${{escapeHtml(count)}}</span></div>
          <div></div>
        </div>
      `).join("");
      const weaponRows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.severity || "")}}</td>
          <td>${{escapeHtml(row.category || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.weapon_name || "")}}</td>
          <td>${{escapeHtml(`A${{row.attacks || "?"}} S${{row.strength || "?"}} AP${{row.ap || "?"}} D${{row.damage || "?"}}`)}}</td>
          <td>${{escapeHtml(row.raw_damage_throughput || "")}}</td>
          <td>${{escapeHtml(row.review_reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Suspicious Weapon Profiles</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Rows needing review", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{severityCards.join("")}}
            ${{categoryCards.join("")}}
          </div>
          ${{reasonRows ? `<p class="small">Most common review reasons</p><div class="check-list">${{reasonRows}}</div>` : ""}}
          <table class="report-table">
            <thead><tr><th>Severity</th><th>Category</th><th>Unit</th><th>Weapon</th><th>Profile</th><th>Raw</th><th>Reason</th></tr></thead>
            <tbody>${{weaponRows || `<tr><td colspan="7">No suspicious weapon profiles were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderSchemaReview(summary) {{
      if (!summary) return "";
      const statusCards = Object.entries(summary.by_status || {{}}).map(([key, value]) => provenanceCard(`Status: ${{key}}`, value, ""));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.status || "")}}</td>
          <td>${{escapeHtml(row.table || "")}}</td>
          <td>${{escapeHtml(row.file || "")}}</td>
          <td>${{escapeHtml(`${{row.required_count || "0"}} / ${{row.actual_count || "0"}}`)}}</td>
          <td>${{escapeHtml(row.missing_columns || "")}}</td>
          <td>${{escapeHtml(row.extra_columns || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Schema Review</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Tables reviewed", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{statusCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Status</th><th>Table</th><th>File</th><th>Required / Actual</th><th>Missing</th><th>Extra</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="6">No schema review rows were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitProfiles(summary) {{
      if (!summary) return "";
      const severityCards = Object.entries(summary.by_severity || {{}}).map(([key, value]) => provenanceCard(`Severity: ${{key}}`, value, ""));
      const categoryCards = Object.entries(summary.by_category || {{}}).map(([key, value]) => provenanceCard(`Category: ${{key}}`, value, ""));
      const reasonRows = Object.entries(summary.by_reason || {{}}).slice(0, 8).map(([reason, count]) => `
        <div class="check-row">
          <div>${{escapeHtml(reason)}}</div>
          <div><span class="status-pill">${{escapeHtml(count)}}</span></div>
          <div></div>
        </div>
      `).join("");
      const unitRows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.severity || "")}}</td>
          <td>${{escapeHtml(row.category || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(`T${{row.toughness || "?"}} Sv${{row.save || "?"}} W${{row.wounds || "?"}}`)}}</td>
          <td>${{escapeHtml(row.points || "")}}</td>
          <td>${{escapeHtml(`${{row.models_min || "?"}}-${{row.models_max || "?"}}`)}}</td>
          <td>${{escapeHtml(row.review_reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Unit Profile Validation</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Units reviewed", summary.total || 0, `${{summary.issue_total || 0}} rows need review`)}}
            ${{severityCards.join("")}}
            ${{categoryCards.join("")}}
          </div>
          ${{reasonRows ? `<p class="small">Most common review reasons</p><div class="check-list">${{reasonRows}}</div>` : ""}}
          <table class="report-table">
            <thead><tr><th>Severity</th><th>Category</th><th>Unit</th><th>Faction</th><th>Profile</th><th>Points</th><th>Models</th><th>Reason</th></tr></thead>
            <tbody>${{unitRows || `<tr><td colspan="8">No unit profile issues were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderLoadouts(summary) {{
      if (!summary) return "";
      const severityCards = Object.entries(summary.by_severity || {{}}).map(([key, value]) => provenanceCard(`Severity: ${{key}}`, value, ""));
      const categoryCards = Object.entries(summary.by_category || {{}}).map(([key, value]) => provenanceCard(`Category: ${{key}}`, value, ""));
      const reasonRows = Object.entries(summary.by_reason || {{}}).slice(0, 8).map(([reason, count]) => `
        <div class="check-row">
          <div>${{escapeHtml(reason)}}</div>
          <div><span class="status-pill">${{escapeHtml(count)}}</span></div>
          <div></div>
        </div>
      `).join("");
      const loadoutRows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.severity || "")}}</td>
          <td>${{escapeHtml(row.category || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(`${{row.total_weapons || "0"}} total / ${{row.ranged_weapons || "0"}} ranged / ${{row.melee_weapons || "0"}} melee`)}}</td>
          <td>${{escapeHtml(row.points || "")}}</td>
          <td>${{escapeHtml(row.review_reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Loadout Complexity</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Rows reviewed", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{severityCards.join("")}}
            ${{categoryCards.join("")}}
          </div>
          ${{reasonRows ? `<p class="small">Most common review reasons</p><div class="check-list">${{reasonRows}}</div>` : ""}}
          <table class="report-table">
            <thead><tr><th>Severity</th><th>Category</th><th>Unit</th><th>Faction</th><th>Weapons</th><th>Points</th><th>Reason</th></tr></thead>
            <tbody>${{loadoutRows || `<tr><td colspan="7">No loadout complexity rows were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderSourceCatalogues(summary) {{
      if (!summary) return "";
      const totals = summary.totals || {{}};
      const rows = (summary.rows || []).map((row) => {{
        const source = row.source_url
          ? `<a href="${{escapeAttr(row.source_url)}}" target="_blank" rel="noreferrer">${{escapeHtml(row.source_file || "")}}</a>`
          : escapeHtml(row.source_file || "");
        return `
          <tr>
            <td>${{source}}</td>
            <td>${{escapeHtml(row.units || "0")}}</td>
            <td>${{escapeHtml(row.weapon_profiles || "0")}}</td>
            <td>${{escapeHtml(row.suspicious_weapon_profiles || "0")}}</td>
            <td>${{escapeHtml(row.unit_profile_issue_rows || "0")}}</td>
            <td>${{escapeHtml(row.loadout_review_rows || "0")}}</td>
            <td>${{escapeHtml(row.no_weapon_units || "0")}}</td>
          </tr>
        `;
      }}).join("");
      return `
        <div class="review-section">
          <h3>Source Catalogue Coverage</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Catalogues", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{provenanceCard("Units", totals.units || 0, "")}}
            ${{provenanceCard("Weapon profiles", totals.weapon_profiles || 0, "")}}
            ${{provenanceCard("Suspicious weapons", totals.suspicious_weapon_profiles || 0, "")}}
            ${{provenanceCard("Unit profile issues", totals.unit_profile_issue_rows || 0, "")}}
            ${{provenanceCard("Loadout rows", totals.loadout_review_rows || 0, "")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Source</th><th>Units</th><th>Weapons</th><th>Suspicious</th><th>Unit Issues</th><th>Loadouts</th><th>No Weapons</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="7">No source catalogue review rows were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitVariants(summary) {{
      if (!summary) return "";
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.variant_count || "0")}}</td>
          <td>${{escapeHtml(row.factions || "")}}</td>
          <td>${{escapeHtml(row.points || "")}}</td>
          <td>${{escapeHtml(row.source_files || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Duplicate Unit Names</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Duplicate names", summary.duplicate_names || 0, `${{summary.total_rows || 0}} variant rows`)}}
            ${{provenanceCard("Largest variant set", summary.max_variant_count || 0, "")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Unit</th><th>Variants</th><th>Factions</th><th>Points</th><th>Sources</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="5">No duplicate unit names were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderWeaponCoverage(summary) {{
      if (!summary) return "";
      const coverageCards = Object.entries(summary.by_coverage || {{}}).map(([key, value]) => provenanceCard(`Coverage: ${{key}}`, value, ""));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(row.selection_type || "")}}</td>
          <td>${{escapeHtml(row.points || "")}}</td>
          <td>${{escapeHtml(`${{row.models_min || "?"}}-${{row.models_max || "?"}}`)}}</td>
          <td>${{escapeHtml(row.source_file || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Unit Weapon Coverage</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Units reviewed", summary.total || 0, `${{summary.no_weapon_total || 0}} without imported weapons`)}}
            ${{coverageCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Unit</th><th>Faction</th><th>Type</th><th>Points</th><th>Models</th><th>Source</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="6">No units without imported weapons were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderAbilityModifiers(summary) {{
      if (!summary) return "";
      const typeCards = Object.entries(summary.by_type || {{}}).map(([key, value]) => provenanceCard(`Type: ${{key}}`, value, ""));
      const grantCards = Object.entries(summary.by_grant || {{}}).map(([key, value]) => provenanceCard(`Grants: ${{key}}`, value, ""));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.modifier_type || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(row.source || "")}}</td>
          <td>${{escapeHtml(`Hit ${{row.hit_modifier || "0"}} / Wound ${{row.wound_modifier || "0"}}`)}}</td>
          <td>${{escapeHtml(row.reroll_hits || row.reroll_wounds || row.grants || row.anti_rules || row.damage_reduction || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Derived Ability Modifiers</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Rows reviewed", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{typeCards.join("")}}
            ${{grantCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Type</th><th>Unit</th><th>Faction</th><th>Source</th><th>Modifiers</th><th>Rules</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="6">No derived ability modifier rows were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderProvenance(manifest, verification, metadata) {{
      if (!manifest && !verification && !metadata) return "";
      const source = manifest && manifest.source ? manifest.source : {{}};
      const metadataSource = metadata && metadata.source_revisions && metadata.source_revisions[0] ? metadata.source_revisions[0] : {{}};
      const linked = manifest && manifest.linked_ml_artifacts ? manifest.linked_ml_artifacts : {{}};
      const artifacts = manifest && manifest.artifacts ? manifest.artifacts : {{}};
      const linkedArtifacts = linked.artifacts || {{}};
      const featureCsv = linkedArtifacts.feature_csv || {{}};
      const modelJson = linkedArtifacts.model_json || {{}};
      const auditJson = linkedArtifacts.model_audit || {{}};
      const comparisonJson = linkedArtifacts.model_comparison || {{}};
      const commit = source.commit || metadataSource.commit || "";
      const generatedAt = manifest && manifest.generated_at ? manifest.generated_at : (metadata && metadata.generated_at ? metadata.generated_at : "");
      return `
        <div class="review-section">
          <h3>Data & ML Provenance</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Source commit", commit ? commit.slice(0, 12) : "unknown", source.remote_origin || metadataSource.remote_origin || "")}}
            ${{provenanceCard("Generated", generatedAt || "unknown", source.branch ? `Branch ${{source.branch}}` : "")}}
            ${{provenanceCard("Artifact checks", verification ? `${{verification.ok_count || 0}}/${{verification.artifact_count || 0}} passing` : "not run", verification && verification.ok ? "All generated checks passed." : "Review failures below.")}}
            ${{provenanceCard("Generated artifacts", manifest ? (manifest.artifact_count || Object.keys(artifacts).length || 0) : "unknown", "Manifest-tracked data files")}}
            ${{provenanceCard("Linked ML artifacts", Object.keys(linkedArtifacts).length || 0, linked.model_type ? `Model type ${{linked.model_type}}` : "")}}
            ${{linked.model_type ? provenanceCard("ML model type", linked.model_type, linked.feature_set ? `Feature set ${{linked.feature_set}}` : "") : ""}}
            ${{provenanceCard("ML feature set", linked.feature_set || "unknown", `${{linked.feature_rows || 0}} feature rows`)}}
            ${{provenanceCard("Feature CSV", shortHash(featureCsv.sha256), featureCsv.path || "not linked")}}
            ${{provenanceCard("Model JSON", shortHash(modelJson.sha256), modelJson.path || "not linked")}}
            ${{auditJson.path ? provenanceCard("Model audit", shortHash(auditJson.sha256), auditJson.path) : ""}}
            ${{comparisonJson.path ? provenanceCard("Model comparison", shortHash(comparisonJson.sha256), comparisonJson.path) : ""}}
          </div>
          ${{renderVerificationChecks(verification)}}
        </div>
      `;
    }}

    function provenanceCard(title, value, detail = "") {{
      return `
        <div class="provenance-card">
          <b>${{escapeHtml(title)}}</b>
          <span>${{escapeHtml(value || "unknown")}}</span>
          ${{detail ? `<span>${{escapeHtml(detail)}}</span>` : ""}}
        </div>
      `;
    }}

    function shortHash(hash) {{
      return hash ? String(hash).slice(0, 12) : "unknown";
    }}

    function renderVerificationChecks(verification) {{
      if (!verification || !verification.results || !verification.results.length) return `<div class="empty">No artifact verification report is available.</div>`;
      const failed = verification.results.filter((item) => !item.ok);
      const rows = (failed.length ? failed : verification.results).map((item) => `
        <div class="check-row">
          <div>${{escapeHtml(item.filename || "unknown")}}</div>
          <div><span class="status-pill ${{item.ok ? "" : "fail"}}">${{escapeHtml(item.status || (item.ok ? "ok" : "failed"))}}</span></div>
          <div>${{escapeHtml(shortHash(item.actual_sha256 || item.expected_sha256 || ""))}}</div>
        </div>
      `).join("");
      const intro = failed.length
        ? `${{failed.length}} failed verification checks need attention.`
        : "All generated artifact and linked ML checks passed.";
      return `
        <p class="small">${{escapeHtml(intro)}}</p>
        <div class="check-list">${{rows}}</div>
      `;
    }}

    function renderEditionStatus(status) {{
      if (!status) return "";
      const blockers = status.blockers && status.blockers.length
        ? `<p><b>Blockers:</b> ${{status.blockers.map(escapeHtml).join(", ")}}</p>`
        : `<p>No calculation blockers recorded.</p>`;
      return `
        <div class="review-section">
          <h3>Edition Readiness</h3>
          <p><b>${{escapeHtml(String(status.edition || "unknown").toUpperCase())}}</b> calculations are ${{status.calculations_enabled ? "enabled" : "blocked"}}.</p>
          <p>Ruleset available: ${{status.rules_available ? "yes" : "no"}} | supported rulesets: ${{escapeHtml((status.supported_rules_editions || []).join(", ") || "none")}}</p>
          ${{blockers}}
          ${{renderRuleCapabilities(status.rule_capabilities)}}
        </div>
      `;
    }}

    function renderRuleCapabilities(capabilities) {{
      if (!capabilities || !capabilities.length) return "";
      const rows = capabilities.map((capability) => {{
        const notes = Array.isArray(capability.notes) ? capability.notes.join("; ") : "";
        return `
          <tr>
            <td>${{escapeHtml(capability.label || capability.key || "unknown")}}</td>
            <td>${{escapeHtml(capability.status || "unknown")}}</td>
            <td>${{escapeHtml(notes)}}</td>
          </tr>
        `;
      }}).join("");
      return `
        <h4>Ruleset Capability Coverage</h4>
        <table class="report-table">
          <thead><tr><th>Capability</th><th>Status</th><th>Notes</th></tr></thead>
          <tbody>${{rows}}</tbody>
        </table>
      `;
    }}

    function renderReviewFiles(files) {{
      if (!files || !files.length) return "";
      const links = files.map((file) => `
        <a class="review-link" href="${{escapeHtml(file.href)}}" download="${{escapeHtml(file.filename || "")}}">
          ${{escapeHtml(file.label || file.filename)}}
          <span>${{formatBytes(file.bytes)}}</span>
        </a>
      `).join("");
      return `
        <div class="review-section">
          <h3>Review Files</h3>
          <div class="review-links">${{links}}</div>
        </div>
      `;
    }}

    function formatBytes(bytes) {{
      const value = Number(bytes || 0);
      if (!value) return "";
      if (value < 1024) return `${{value}} B`;
      if (value < 1024 * 1024) return `${{Math.round(value / 1024)}} KB`;
      return `${{(value / (1024 * 1024)).toFixed(1)}} MB`;
    }}

    function renderProfileReview(profileReview) {{
      if (!profileReview) return "";
      return renderMarkdownReport("Profile Review", profileReview);
    }}

    function renderEditionReadiness(editionReadiness) {{
      if (!editionReadiness) return "";
      return renderMarkdownReport("Edition Readiness Report", editionReadiness);
    }}

    function renderUpdateReport(updateReport) {{
      if (!updateReport) return "";
      return renderMarkdownReport("Update Report", updateReport);
    }}

    function renderModelAudit(modelAudit) {{
      if (!modelAudit) return "";
      return renderMarkdownReport("ML Model Audit", modelAudit);
    }}

    function renderModelComparison(modelComparison) {{
      if (!modelComparison) return "";
      return renderMarkdownReport("ML Model Comparison", modelComparison);
    }}

    function renderMarkdownReport(title, markdown) {{
      return `
        <div class="review-section">
          <h3>${{escapeHtml(title)}}</h3>
          <div class="report-markdown">${{markdownToHtml(markdown)}}</div>
        </div>
      `;
    }}

    function markdownToHtml(markdown) {{
      const lines = String(markdown || "").split(/\\r?\\n/);
      const chunks = [];
      let listOpen = false;
      const closeList = () => {{
        if (listOpen) {{
          chunks.push("</ul>");
          listOpen = false;
        }}
      }};
      const cells = (line) => line.trim().replace(/^\\|/, "").replace(/\\|$/, "").split("|").map((cell) => cell.trim());
      const isDelimiter = (line) => /^\\s*\\|?\\s*:?-{{3,}}:?\\s*(\\|\\s*:?-{{3,}}:?\\s*)+\\|?\\s*$/.test(line);
      const inline = (text) => markdownInline(text);

      for (let index = 0; index < lines.length; index += 1) {{
        const line = lines[index];
        const trimmed = line.trim();
        if (!trimmed) {{
          closeList();
          continue;
        }}
        if (trimmed.startsWith("|") && lines[index + 1] && isDelimiter(lines[index + 1])) {{
          closeList();
          const headers = cells(trimmed);
          index += 2;
          const rows = [];
          while (index < lines.length && lines[index].trim().startsWith("|")) {{
            rows.push(cells(lines[index]));
            index += 1;
          }}
          index -= 1;
          chunks.push(`
            <table class="report-table">
              <thead><tr>${{headers.map((cell) => `<th>${{inline(cell)}}</th>`).join("")}}</tr></thead>
              <tbody>${{rows.map((row) => `<tr>${{row.map((cell) => `<td>${{inline(cell)}}</td>`).join("")}}</tr>`).join("")}}</tbody>
            </table>
          `);
          continue;
        }}
        if (trimmed.startsWith("#")) {{
          closeList();
          const text = trimmed.replace(/^#+\\s*/, "");
          chunks.push(`<h4>${{inline(text)}}</h4>`);
          continue;
        }}
        if (trimmed.startsWith("- ")) {{
          if (!listOpen) {{
            chunks.push("<ul>");
            listOpen = true;
          }}
          chunks.push(`<li>${{inline(trimmed.slice(2))}}</li>`);
          continue;
        }}
        closeList();
        chunks.push(`<p>${{inline(trimmed)}}</p>`);
      }}
      closeList();
      return chunks.join("");
    }}

    function markdownInline(text) {{
      const raw = String(text || "");
      const pattern = /\\[([^\\]]+)\\]\\((https?:\\/\\/[^)\\s]+)\\)/g;
      let html = "";
      let lastIndex = 0;
      raw.replace(pattern, (match, label, url, offset) => {{
        html += escapeHtml(raw.slice(lastIndex, offset));
        html += `<a href="${{escapeHtml(url)}}" target="_blank" rel="noreferrer">${{escapeHtml(label)}}</a>`;
        lastIndex = offset + match.length;
        return match;
      }});
      html += escapeHtml(raw.slice(lastIndex));
      return html;
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
      refreshWeaponSelectors().catch((error) => {{
        el("error").textContent = error.message;
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
        const attackerId = state.selectedUnitIds.attacker;
        state.selectedUnitIds.attacker = state.selectedUnitIds.defender;
        state.selectedUnitIds.defender = attackerId;
        updateSelectedUnitInfos();
        swapContexts();
        refreshWeaponSelectors().catch((error) => {{
          el("error").textContent = error.message;
        }});
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
          state.selectedUnitIds[id] = null;
          updateSelectedUnitInfo(id);
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
        el(id).addEventListener("blur", () => {{
          refreshWeaponSelectors().catch((error) => {{
            el("error").textContent = error.message;
          }});
        }});
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


def build_local_html(*, csv_dir: Path, template_path: Path, output_path: Path, model_path: Path = DEFAULT_MODEL) -> None:
    units = sorted(load_units_from_directory(csv_dir).values(), key=lambda unit: (unit.name.casefold(), unit.faction or ""))
    model_path = Path(model_path)
    data = {
        "units": [_unit_payload(unit) for unit in units],
        "factions": sorted({unit.faction for unit in units if unit.faction}, key=str.casefold),
        "auditReport": _load_json(csv_dir / "audit_report.json"),
        "importDiff": _load_json(csv_dir / "import_diff.json"),
        "metadata": _load_json(csv_dir / "metadata.json"),
        "editionStatus": _load_json(csv_dir / "edition_status.json"),
        "artifactManifest": _load_json(csv_dir / "artifact_manifest.json"),
        "verificationReport": artifact_verification_report(csv_dir),
        "suspiciousWeaponSummary": suspicious_weapon_summary(csv_dir / "suspicious_weapon_review.csv"),
        "unitProfileSummary": unit_profile_summary(csv_dir / "unit_profile_review.csv"),
        "loadoutSummary": loadout_summary(csv_dir / "loadout_review.csv"),
        "sourceCatalogueSummary": source_catalogue_summary(csv_dir / "source_catalogue_review.csv"),
        "unitVariantSummary": unit_variant_summary(csv_dir / "unit_variant_review.csv"),
        "weaponCoverageSummary": weapon_coverage_summary(csv_dir / "unit_weapon_coverage_review.csv"),
        "abilityModifierSummary": ability_modifier_summary(csv_dir / "ability_modifier_review.csv"),
        "schemaSummary": schema_summary(csv_dir / "schema_review.csv"),
        "updateReport": _load_text(csv_dir / "update_report.md"),
        "profileReview": _load_text(csv_dir / "profile_review.md"),
        "editionReadiness": _load_text(csv_dir / "edition_readiness.md"),
        "modelAudit": _load_text(model_path.with_suffix(".md")),
        "modelComparison": _load_text(model_path.parent / "model_comparison.md"),
        "reviewFiles": _review_files(csv_dir),
        "modelFiles": _model_files(model_path.parent, selected_model_path=model_path),
        "mlModel": _load_json(model_path),
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


def _load_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8") or None
    except OSError:
        return None


def _review_files(csv_dir: Path) -> list[dict[str, Any]]:
    labels = {
        "weapon_profile_review.csv": "Weapon profile review CSV",
        "suspicious_weapon_review.csv": "Suspicious weapon review CSV",
        "unit_profile_review.csv": "Unit profile review CSV",
        "ability_profile_review.csv": "Ability profile review CSV",
        "ability_modifier_review.csv": "Ability modifier review CSV",
        "unit_variant_review.csv": "Duplicate unit name review CSV",
        "unit_weapon_coverage_review.csv": "Unit weapon coverage review CSV",
        "loadout_review.csv": "Loadout review CSV",
        "source_catalogue_review.csv": "Source catalogue review CSV",
        "schema_review.csv": "Schema review CSV",
        "edition_status.json": "Edition status JSON",
        "edition_readiness.md": "Edition readiness report",
        "artifact_manifest.json": "Artifact manifest JSON",
        "profile_review.md": "Profile review summary",
        "update_report.md": "Update report",
    }
    files = []
    for filename, label in labels.items():
        path = csv_dir / filename
        if path.exists():
            files.append(
                {
                    "label": label,
                    "filename": filename,
                    "href": _review_file_href(csv_dir, filename),
                    "bytes": path.stat().st_size,
                }
            )
    return files


def _model_files(model_dir: Path, *, selected_model_path: Path | None = None) -> list[dict[str, Any]]:
    labels = {
        "matchup_centroid_model.md": "ML model audit report",
        "matchup_centroid_model.json": "ML model JSON",
        "matchup_logistic_model.md": "ML logistic model audit report",
        "matchup_logistic_model.json": "ML logistic model JSON",
        "model_comparison.md": "ML model comparison report",
    }
    if selected_model_path:
        labels.setdefault(selected_model_path.name, "Selected ML model JSON")
        selected_report = selected_model_path.with_suffix(".md")
        labels.setdefault(selected_report.name, "Selected ML model audit report")
    files = []
    for filename, label in labels.items():
        path = model_dir / filename
        if path.exists():
            files.append(
                {
                    "label": label,
                    "filename": filename,
                    "href": _relative_or_absolute_href(path),
                    "bytes": path.stat().st_size,
                }
            )
    return files


def _review_file_href(csv_dir: Path, filename: str) -> str:
    return _relative_or_absolute_href(csv_dir / filename)


def _relative_or_absolute_href(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return str(path.resolve())
    return relative.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a standalone local HTML calculator")
    parser.add_argument("--csv-dir", type=Path, default=_default_csv_dir())
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="ML model JSON to embed in the standalone HTML")
    args = parser.parse_args()
    build_local_html(csv_dir=args.csv_dir, template_path=args.template, output_path=args.output, model_path=args.model)
    print(f"Wrote {args.output}")


def _default_csv_dir() -> Path:
    if DEFAULT_CSV_DIR.exists():
        return DEFAULT_CSV_DIR
    return LEGACY_CSV_DIR


if __name__ == "__main__":
    main()
