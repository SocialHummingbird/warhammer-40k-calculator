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
    unit_footprint_queue_summary,
    unit_footprint_template_summary,
    unit_footprint_suggestion_summary,
    unit_footprint_summary,
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
        "range_inches": weapon.range_inches,
        "rangeInches": weapon.range_inches,
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
        "baseType": unit.base_type,
        "baseShape": unit.base_shape,
        "baseWidthMm": unit.base_width_mm,
        "baseDepthMm": unit.base_depth_mm,
        "footprintStatus": unit.footprint_status,
        "footprintSource": unit.footprint_source,
        "footprintConfidence": unit.footprint_confidence,
        "objectiveControl": unit.objective_control,
        "sourceFile": unit.source_file,
        "keywords": unit.keywords,
        "canAdvanceAndShoot": unit.can_advance_and_shoot,
        "abilityCount": len(unit.abilities),
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
      loadoutSummary: LOCAL_DATA.loadoutSummary || null,
      sourceCatalogueSummary: LOCAL_DATA.sourceCatalogueSummary || null,
      unitVariantSummary: LOCAL_DATA.unitVariantSummary || null,
      weaponCoverageSummary: LOCAL_DATA.weaponCoverageSummary || null,
      unitFootprintSummary: LOCAL_DATA.unitFootprintSummary || null,
      unitFootprintSuggestionSummary: LOCAL_DATA.unitFootprintSuggestionSummary || null,
      unitFootprintTemplateSummary: LOCAL_DATA.unitFootprintTemplateSummary || null,
      unitFootprintQueueSummary: LOCAL_DATA.unitFootprintQueueSummary || null,
      abilityModifierSummary: LOCAL_DATA.abilityModifierSummary || null,
      schemaSummary: LOCAL_DATA.schemaSummary || null,
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
      unitSearchResults: {{ attacker: [], defender: [] }},
      activeOptionIndex: {{ attacker: -1, defender: -1 }},
      searchTimer: {{ attacker: null, defender: null }},
      openMenu: null,
      rulesEdition: "10e",
      supportedRulesEditions: ["10e"],
      availableEditions: [],
      battlefield: {{
        templates: [],
        selectedTemplate: "strike_force_44x60",
        redUnitId: null,
        blueUnitId: null,
        redCount: 1,
        blueCount: 1,
        armyRows: {{ red: [], blue: [] }},
        state: null,
        plan: null,
        manualActions: [],
        manualUnavailableActions: [],
        autoplayTurns: 5,
        validation: null,
        dragging: null,
        selectedInstanceId: null,
        selectedUnitDetail: null
      }}
    }};

    const el = (id) => document.getElementById(id);
    const hasNumber = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
    const fmt = (value) => hasNumber(value) ? Number(value).toFixed(2) : "n/a";
    const signedFmt = (value) => hasNumber(value) ? `${{Number(value) > 0 ? "+" : ""}}${{Number(value).toFixed(2)}}` : "n/a";
    const pct = (value) => `${{Math.round(Number(value || 0) * 100)}}%`;
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({{
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\\"": "&quot;",
      "'": "&#39;"
    }}[char]));
    const escapeAttr = escapeHtml;

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
        base_type: unit.baseType,
        base_shape: unit.baseShape,
        base_width_mm: unit.baseWidthMm,
        base_depth_mm: unit.baseDepthMm,
        footprint_status: unit.footprintStatus,
        footprint_source: unit.footprintSource,
        footprint_confidence: unit.footprintConfidence,
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

    function factionSelectId(field) {{
      return field === "defender" ? "defender-faction" : "attacker-faction";
    }}

    function factionForField(field) {{
      if (field !== "attacker" && field !== "defender") return "";
      const select = el(factionSelectId(field));
      return select ? select.value : "";
    }}

    function renderFactions() {{
      for (const selectId of ["attacker-faction", "defender-faction"]) {{
        const select = el(selectId);
        if (!select) continue;
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
    }}

    function searchUnits(query = "", field = null) {{
      const needle = query.trim().toLowerCase();
      const faction = factionForField(field).toLowerCase();
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

    async function loadUnits(query = "", field = null) {{
      const units = await searchUnits(query, field);
      if (field === "attacker" || field === "defender") state.unitSearchResults[field] = units;
      if (state.openMenu) renderDropdown(state.openMenu, state.unitSearchResults[state.openMenu] || units);
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
        unit_footprint_summary: state.unitFootprintSummary,
        unit_footprint_suggestion_summary: state.unitFootprintSuggestionSummary,
        unit_footprint_template_summary: state.unitFootprintTemplateSummary,
        unit_footprint_queue_summary: state.unitFootprintQueueSummary,
        unit_footprint_review: state.unitFootprintReview,
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

    function localBattlefieldTemplates() {{
      return [
        {{ id: "strike_force_44x60", name: "Strike Force 44 x 60", width: 44, height: 60, rules_preset: "tactical_mvp_v1" }},
        {{ id: "onslaught_44x90", name: "Onslaught 44 x 90", width: 44, height: 90, rules_preset: "tactical_mvp_v1" }}
      ];
    }}

    function localGenerateMap(templateId = "strike_force_44x60") {{
      const height = templateId === "onslaught_44x90" ? 90 : 60;
      const width = 44;
      const dz = height <= 60 ? 10 : 14;
      return {{
        id: templateId,
        name: templateId === "onslaught_44x90" ? "Onslaught 44 x 90" : "Strike Force 44 x 60",
        width,
        height,
        rules_preset: "tactical_mvp_v1",
        deployment_zones: [
          {{ id: "red-dz", side: "red", x: 0, y: 0, width, height: dz }},
          {{ id: "blue-dz", side: "blue", x: 0, y: height - dz, width, height: dz }}
        ],
        terrain: [
          {{ id: "ruin-nw", name: "Northwest ruin", type: "ruin", x: 5, y: height * 0.22, width: 10, height: 8, shape: "rectangle", stories: 2, grants_cover: true, blocks_line_of_sight: true, movement_penalty: 2 }},
          {{ id: "ruin-se", name: "Southeast ruin", type: "ruin", x: width - 15, y: height * 0.64, width: 10, height: 8, shape: "rectangle", stories: 3, grants_cover: true, blocks_line_of_sight: true, movement_penalty: 2 }},
          {{ id: "forest-sw", name: "Southwest woods", type: "woods", x: 7, y: height * 0.68, width: 8, height: 7, shape: "ellipse", stories: 1, grants_cover: true, blocks_line_of_sight: false, movement_penalty: 1 }},
          {{ id: "forest-ne", name: "Northeast woods", type: "woods", x: width - 15, y: height * 0.2, width: 8, height: 7, shape: "ellipse", stories: 1, grants_cover: true, blocks_line_of_sight: false, movement_penalty: 1 }},
          {{ id: "crater-mid", name: "Central crater", type: "crater", x: width / 2 - 5, y: height / 2 - 4, width: 10, height: 8, shape: "ellipse", stories: 1, grants_cover: true, blocks_line_of_sight: false, movement_penalty: 0 }},
          {{ id: "barricade-west", name: "West barricade", type: "barricade", x: width * 0.18, y: height * 0.47, width: 7, height: 1.2, shape: "diamond", stories: 1, grants_cover: true, blocks_line_of_sight: false, movement_penalty: 0.5 }},
          {{ id: "barricade-east", name: "East barricade", type: "barricade", x: width * 0.66, y: height * 0.47, width: 7, height: 1.2, shape: "diamond", stories: 1, grants_cover: true, blocks_line_of_sight: false, movement_penalty: 0.5 }}
        ],
        objectives: [
          {{ id: "obj-home-red", name: "Red home", x: width / 2, y: dz / 2, radius: 3, points: 5 }},
          {{ id: "obj-home-blue", name: "Blue home", x: width / 2, y: height - dz / 2, radius: 3, points: 5 }},
          {{ id: "obj-west", name: "West midfield", x: width * 0.25, y: height / 2, radius: 3, points: 5 }},
          {{ id: "obj-centre", name: "Centre", x: width / 2, y: height / 2, radius: 3, points: 5 }},
          {{ id: "obj-east", name: "East midfield", x: width * 0.75, y: height / 2, radius: 3, points: 5 }}
        ]
      }};
    }}

    async function loadBattlefieldTemplates() {{
      if (!state.battlefield.templates.length) state.battlefield.templates = localBattlefieldTemplates();
      return state.battlefield.templates;
    }}

    async function loadBattlefieldUnits() {{
      if (!state.battlefield.units || !state.battlefield.units.length) state.battlefield.units = state.units;
      return state.battlefield.units;
    }}

    async function loadBattlefieldFactionUnits(faction) {{
      return loadBattlefieldUnits();
    }}

    async function showBattlefield() {{
      setAppMode("battlefield");
      el("error").textContent = "";
      await loadBattlefieldTemplates();
      await loadBattlefieldUnits();
      ensureBattlefieldUnitSelections();
      if (!state.battlefield.state) {{
        state.battlefield.state = localInitialBattleState();
        state.battlefield.plan = localBattlefieldPlan(6);
      }}
      renderBattlefield();
    }}

    function ensureBattlefieldUnitSelections() {{
      const units = battlefieldAvailableUnits();
      const redId = state.selectedUnitIds.attacker || state.battlefield.redUnitId || (units[0] && units[0].id) || null;
      const fallback = units.find((unit) => unit.id !== redId);
      const blueId = state.selectedUnitIds.defender || state.battlefield.blueUnitId || (fallback && fallback.id) || redId;
      if (!state.battlefield.armyRows.red.length && redId) state.battlefield.armyRows.red = [{{ unitId: redId, count: Math.max(1, Number(state.battlefield.redCount || 1)) }}];
      if (!state.battlefield.armyRows.blue.length && blueId) state.battlefield.armyRows.blue = [{{ unitId: blueId, count: Math.max(1, Number(state.battlefield.blueCount || 1)) }}];
      syncLegacyBattlefieldSelections();
    }}

    function battlefieldArmyRows(side) {{
      ensureBattlefieldRowsObject();
      return state.battlefield.armyRows[side] || [];
    }}

    function battlefieldAvailableUnits() {{
      return (state.battlefield.units && state.battlefield.units.length) ? state.battlefield.units : state.units;
    }}

    function battlefieldFactionOptions() {{
      if (state.factions && state.factions.length) return state.factions;
      return [...new Set(battlefieldAvailableUnits().map((unit) => unit.faction).filter(Boolean))].sort();
    }}

    function battlefieldFaction(side) {{
      const factions = state.battlefield.armyFactions || {{}};
      return factions[side] || "";
    }}

    function filteredBattlefieldUnits(side) {{
      const faction = battlefieldFaction(side);
      const units = battlefieldAvailableUnits();
      return faction ? units.filter((unit) => unit.faction === faction) : units;
    }}

    function ensureBattlefieldRowsObject() {{
      if (!state.battlefield.armyRows) state.battlefield.armyRows = {{ red: [], blue: [] }};
      if (!Array.isArray(state.battlefield.armyRows.red)) state.battlefield.armyRows.red = [];
      if (!Array.isArray(state.battlefield.armyRows.blue)) state.battlefield.armyRows.blue = [];
      if (!state.battlefield.armyFactions) state.battlefield.armyFactions = {{ red: "", blue: "" }};
    }}

    function syncLegacyBattlefieldSelections() {{
      const red = battlefieldArmyRows("red")[0] || {{}};
      const blue = battlefieldArmyRows("blue")[0] || {{}};
      state.battlefield.redUnitId = red.unitId || null;
      state.battlefield.blueUnitId = blue.unitId || null;
      state.battlefield.redCount = Math.max(1, Number(red.count || 1));
      state.battlefield.blueCount = Math.max(1, Number(blue.count || 1));
    }}

    function battlefieldArmies() {{
      ensureBattlefieldUnitSelections();
      return [
        {{ id: "red", name: "Red Army", side: "red", units: battlefieldArmyRows("red").filter((row) => row.unitId).map((row) => ({{ unit_id: row.unitId, count: Math.max(1, Number(row.count || 1)) }})) }},
        {{ id: "blue", name: "Blue Army", side: "blue", units: battlefieldArmyRows("blue").filter((row) => row.unitId).map((row) => ({{ unit_id: row.unitId, count: Math.max(1, Number(row.count || 1)) }})) }}
      ];
    }}

    function localInitialBattleState(importedMap = null) {{
      const battleMap = importedMap || localGenerateMap(state.battlefield.selectedTemplate);
      const units = [];
      const copyCounters = {{}};
      for (const army of battlefieldArmies()) {{
        const zone = battleMap.deployment_zones.find((row) => row.side === army.side);
        let index = 0;
        for (const entry of army.units) {{
          const profile = state.units.find((unit) => unit.id === entry.unit_id);
          if (!profile || !zone) continue;
          const models = defaultBattleModels(profile);
          const radius = defaultBattleRadius(profile);
          for (let copy = 0; copy < Math.max(1, Number(entry.count || 1)); copy += 1) {{
            const counterKey = `${{army.side}}:${{entry.unit_id}}`;
            copyCounters[counterKey] = (copyCounters[counterKey] || 0) + 1;
            units.push({{
              instance_id: `${{army.side}}-${{entry.unit_id}}-${{copyCounters[counterKey]}}`,
              unit_id: entry.unit_id,
              side: army.side,
              name: profile.name,
              x: Math.max(1, Math.min(battleMap.width - 1, zone.x + 4 + (index % 4) * 7)),
              y: Math.max(1, Math.min(battleMap.height - 1, army.side === "red" ? zone.y + 4 + Math.floor(index / 4) * 5 : zone.y + zone.height - 4 - Math.floor(index / 4) * 5)),
              radius,
              models_remaining: models,
              wounds_remaining: models * Math.max(1, Number(profile.wounds || 1)),
              status_flags: []
            }});
            index += 1;
          }}
        }}
      }}
      return {{ map: battleMap, armies: battlefieldArmies(), units, turn: 1, phase: "movement", active_side: "red", score: {{ red: 0, blue: 0 }}, log: [] }};
    }}

    function defaultBattleModels(unit) {{
      if (unit.modelsMin && unit.modelsMax) return Math.max(1, Math.round((Number(unit.modelsMin) + Number(unit.modelsMax)) / 2));
      return Math.max(1, Number(unit.modelsMin || unit.modelsMax || 1));
    }}

    function defaultBattleRadius(unit) {{
      const width = Number(unit.base_width_mm || unit.baseWidthMm || 0);
      const depth = Number(unit.base_depth_mm || unit.baseDepthMm || 0);
      if (width > 0 && depth > 0) {{
        return radiusFromBaseDimensions(defaultBattleModels(unit), width, depth);
      }}
      const estimate = battleBaseEstimate(unit);
      if (estimate.width && estimate.depth) {{
        return radiusFromBaseDimensions(defaultBattleModels(unit), estimate.width, estimate.depth);
      }}
      if (estimate.radius && defaultBattleModels(unit) <= 1) {{
        return estimate.radius;
      }}
      return Math.max(1, Math.min(6, Math.sqrt(defaultBattleModels(unit)) * 0.85));
    }}

    function radiusFromBaseDimensions(models, widthMm, depthMm) {{
      const largestBaseInches = Math.max(widthMm, depthMm) / 25.4;
      const singleModelRadius = Math.max(0.45, largestBaseInches / 2);
      return Math.max(0.75, Math.min(8, Math.sqrt(models) * (singleModelRadius + 0.2)));
    }}

    function battleBaseEstimate(profile = {{}}) {{
      const type = String(profile.base_type || profile.baseType || "");
      if (type === "small_flying_base") return {{ width: 32, depth: 32, label: "derived 32mm flying footprint" }};
      if (type === "large_flying_base") return {{ width: 60, depth: 60, label: "derived 60mm flying footprint" }};
      if (type === "hull") return {{ radius: 2.8, label: "derived hull footprint placeholder" }};
      if (type === "unique") return {{ radius: 2.8, label: "derived unique footprint placeholder" }};
      return {{}};
    }}

    function localBattlefieldPlan(limit = 6) {{
      const actions = localBattleActions().slice(0, limit);
      return {{ actions, assumptions: ["Local Battlefield mode uses circular unit blobs.", "AI planning is deterministic and heuristic."] }};
    }}

    function localBattleActions() {{
      const battleState = state.battlefield.state || localInitialBattleState();
      const phase = localNormalizedBattlePhase(battleState.phase);
      const actions = [];
      const active = (battleState.units || []).filter((unit) => unit.side === battleState.active_side && unit.models_remaining > 0 && !localUnitActedThisPhase(battleState, unit.instance_id));
      const enemies = (battleState.units || []).filter((unit) => unit.side !== battleState.active_side && unit.models_remaining > 0);
      const controlled = localControlledObjectivesForSide(battleState, battleState.active_side);
      if (controlled.length && active.length && !localSideScoredThisTurn(battleState, battleState.active_side)) {{
        const actor = localScoringActorForObjectives(active, controlled);
        const gained = controlled.reduce((sum, objective) => sum + Number(objective.points || 0), 0);
        actions.push({{
          id: `${{battleState.active_side}}:score:${{battleState.turn}}`,
          type: "score",
          side: battleState.active_side,
          actor_id: actor.instance_id,
          score: gained * 8,
          objective_value: gained,
          reason: `Score ${{gained}} VP from controlled objectives: ${{controlled.map((objective) => objective.name).join(", ")}}.`,
          expected_damage: 0,
          expected_return_damage: 0,
          assumptions: ["Objective scoring uses Objective Control from imported profiles.", "A side can take one explicit score action per turn in Battlefield mode."]
        }});
      }}
      for (const actor of active) {{
        const actorProfile = state.units.find((unit) => unit.id === actor.unit_id);
        if (!actorProfile) continue;
        actions.push({{ id: `${{actor.instance_id}}:hold`, type: "hold", side: actor.side, actor_id: actor.instance_id, score: 0.1, reason: "Hold position.", expected_damage: 0, expected_return_damage: 0, assumptions: ["No movement or attack selected."] }});
        const engagedEnemy = localNearestEngagedEnemy(battleState, actor);
        if (engagedEnemy) {{
          const movement = localMovementAllowance(battleState.map, actor, actorProfile);
          const moved = localFallBackDestination(battleState, actor, engagedEnemy, movement.allowance);
          actions.push({{
            id: `${{actor.instance_id}}:fall_back:${{engagedEnemy.instance_id}}`,
            type: "fall_back",
            side: actor.side,
            actor_id: actor.instance_id,
            destination: moved.destination,
            score: 4 + localAttackDistance(actor, engagedEnemy),
            reason: `Fall back from ${{engagedEnemy.name}} using ${{movement.allowance.toFixed(1)}}" movement; this prevents shooting and charging later this turn in Battlefield mode.`,
            expected_damage: 0,
            expected_return_damage: 0,
            assumptions: ["Battlefield mode uses circular unit blobs.", ...movement.assumptions, ...moved.assumptions]
          }});
        }}
        const objective = nearestBattleObjective(battleState, actor);
        if (objective && !engagedEnemy) {{
          const movement = localMovementAllowance(battleState.map, actor, actorProfile);
          const moved = localNonOverlappingDestination(battleState, actor, stepToward(actor.x, actor.y, objective.x, objective.y, movement.allowance));
          const destination = moved.destination;
          const progress = Math.max(0, distance(actor.x, actor.y, objective.x, objective.y) - distance(destination.x, destination.y, objective.x, objective.y));
          const controlBonus = distance(destination.x, destination.y, objective.x, objective.y) <= objective.radius + actor.radius
            ? objective.points * Math.min(2, localObjectiveControl(actor, actorProfile) / 5)
            : 0;
          const objectiveValue = progress * 0.9 + controlBonus;
          actions.push({{ id: `${{actor.instance_id}}:move:${{objective.id}}`, type: "move", side: actor.side, actor_id: actor.instance_id, destination, score: objectiveValue, objective_value: objectiveValue, reason: `Move toward ${{objective.name}} to improve objective control using ${{movement.allowance.toFixed(1)}}" movement.`, expected_damage: 0, expected_return_damage: 0, assumptions: ["Movement uses unit centre distance.", ...movement.assumptions, ...moved.assumptions] }});
          const advanceAllowance = movement.allowance + 3.5;
          const advanced = localNonOverlappingDestination(battleState, actor, stepToward(actor.x, actor.y, objective.x, objective.y, advanceAllowance));
          const advancedDestination = advanced.destination;
          const advanceProgress = Math.max(0, distance(actor.x, actor.y, objective.x, objective.y) - distance(advancedDestination.x, advancedDestination.y, objective.x, objective.y));
          const advanceControlBonus = distance(advancedDestination.x, advancedDestination.y, objective.x, objective.y) <= objective.radius + actor.radius
            ? objective.points * Math.min(2, localObjectiveControl(actor, actorProfile) / 5)
            : 0;
          const advanceValue = advanceProgress * 0.9 + advanceControlBonus;
          actions.push({{ id: `${{actor.instance_id}}:advance:${{objective.id}}`, type: "advance", side: actor.side, actor_id: actor.instance_id, destination: advancedDestination, score: advanceValue + 0.4, objective_value: advanceValue, reason: `Advance toward ${{objective.name}} using ${{advanceAllowance.toFixed(1)}}" expected movement; this improves board position but prevents charging later this turn.`, expected_damage: 0, expected_return_damage: 0, assumptions: ["Movement uses unit centre distance.", ...movement.assumptions, "Advance movement adds an expected D6 roll of 3.5 inches.", ...advanced.assumptions] }});
        }}
        for (const target of enemies) {{
          const targetProfile = state.units.find((unit) => unit.id === target.unit_id);
          if (!targetProfile) continue;
          if (!localUnitEngagedWithEnemy(battleState, actor) && !localUnitFellBackThisTurn(battleState, actor.instance_id) && localAttackDistance(actor, target) <= localRangedAttackReach(actorProfile)) {{
            const attack = localBattleAttack(actor, target, actorProfile, targetProfile, "ranged");
            const returned = localAttackDistance(target, actor) <= localRangedAttackReach(targetProfile)
              ? localBattleAttack(target, actor, targetProfile, actorProfile, "ranged")
              : {{ damage: 0 }};
            const visibilityNote = attack.context && attack.context.line_of_sight_blocked
              ? ` Line of sight is obscured by ${{(attack.context.intervening_terrain || ["terrain"]).join(", ")}}; ranged output is reduced.`
              : "";
            actions.push({{
              id: `${{actor.instance_id}}:shoot:${{target.instance_id}}`,
              type: "shoot",
              side: actor.side,
              actor_id: actor.instance_id,
              target_id: target.instance_id,
              score: attack.damage * 10 - returned.damage * 3.5,
              reason: `Attack ${{target.name}} at ${{localAttackDistance(actor, target).toFixed(1)}}" within ${{localRangedAttackReach(actorProfile).toFixed(0)}}" tactical range for ${{attack.damage.toFixed(2)}} expected damage.${{visibilityNote}}`,
              expected_damage: attack.damage,
              expected_return_damage: returned.damage,
              context: attack.context,
              assumptions: attack.assumptions
            }});
          }}
          if (!localUnitFellBackThisTurn(battleState, actor.instance_id) && !localUnitAdvancedThisTurn(battleState, actor.instance_id) && distance(actor.x, actor.y, target.x, target.y) <= 12 + Number(actor.radius || 0) + Number(target.radius || 0)) {{
            const melee = localBattleAttack(actor, target, actorProfile, targetProfile, "melee");
            if (phase === "fight" && localAttackDistance(actor, target) <= 1) {{
              actions.push({{
                id: `${{actor.instance_id}}:fight:${{target.instance_id}}`,
                type: "fight",
                side: actor.side,
                actor_id: actor.instance_id,
                target_id: target.instance_id,
                score: melee.damage * 10,
                reason: `Fight ${{target.name}} in engagement range for ${{melee.damage.toFixed(2)}} expected damage.`,
                expected_damage: melee.damage,
                expected_return_damage: 0,
                context: melee.context,
                assumptions: melee.assumptions
              }});
            }} else if (!localUnitEngagedWithEnemy(battleState, actor)) {{
              const probability = localChargeProbability(actor, target);
              const expectedDamage = melee.damage * probability;
              actions.push({{
                id: `${{actor.instance_id}}:charge:${{target.instance_id}}`,
                type: "charge",
                side: actor.side,
                actor_id: actor.instance_id,
                target_id: target.instance_id,
                score: expectedDamage * 10,
                reason: `Attempt a simplified charge into ${{target.name}}; ${{Math.round(probability * 100)}}% charge probability for ${{expectedDamage.toFixed(2)}} expected damage (${{melee.damage.toFixed(2)}} if it connects).`,
                expected_damage: expectedDamage,
                expected_return_damage: 0,
                context: {{ ...melee.context, charge_probability: probability, full_melee_damage_if_charge_connects: melee.damage }},
                assumptions: [...melee.assumptions, `Charge damage is expected melee damage multiplied by ${{Math.round(probability * 100)}}% simplified charge probability.`]
              }});
            }}
          }}
        }}
      }}
      return actions
        .filter((action) => localBattleActionAllowedInPhase(action, phase))
        .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id));
    }}

    function localUnavailableBattleActions() {{
      const battleState = state.battlefield.state || localInitialBattleState();
      const phase = localNormalizedBattlePhase(battleState.phase);
      const rows = [];
      const active = (battleState.units || []).filter((unit) => unit.side === battleState.active_side && unit.models_remaining > 0 && !(unit.status_flags || []).includes("destroyed"));
      const enemies = (battleState.units || []).filter((unit) => unit.side !== battleState.active_side && unit.models_remaining > 0 && !(unit.status_flags || []).includes("destroyed"));
      const push = (actor, type, reason) => rows.push({{ side: actor ? actor.side : battleState.active_side, phase, type, actor_id: actor ? actor.instance_id : null, actor: actor ? actor.name : null, reason }});
      if (phase === "scoring") {{
        const controlled = localControlledObjectivesForSide(battleState, battleState.active_side);
        if (localSideScoredThisTurn(battleState, battleState.active_side)) push(null, "score", "This side has already scored objectives this turn.");
        else if (!controlled.length) push(null, "score", "No objectives are currently controlled by the active side.");
      }}
      for (const actor of active) {{
        const profile = state.units.find((unit) => unit.id === actor.unit_id);
        if (localUnitActedThisPhase(battleState, actor.instance_id)) {{
          push(actor, "any", `${{actor.name}} has already acted in the ${{phase}} phase.`);
          continue;
        }}
        if (!profile) {{
          push(actor, "any", `${{actor.name}} has no loaded unit profile.`);
          continue;
        }}
        const engagedEnemy = localNearestEngagedEnemy(battleState, actor);
        if (phase === "movement") {{
          if (engagedEnemy) {{
            push(actor, "move", `${{actor.name}} is engaged with ${{engagedEnemy.name}}; use fall back instead of a normal move.`);
            push(actor, "advance", `${{actor.name}} is engaged with ${{engagedEnemy.name}}; use fall back instead of advancing.`);
          }} else {{
            push(actor, "fall_back", `${{actor.name}} is not engaged, so it cannot fall back.`);
          }}
        }} else if (phase === "shooting") {{
          if (engagedEnemy) push(actor, "shoot", `${{actor.name}} is engaged with ${{engagedEnemy.name}} and cannot make a normal shooting action.`);
          else if (localUnitFellBackThisTurn(battleState, actor.instance_id)) push(actor, "shoot", `${{actor.name}} fell back this turn and cannot shoot.`);
          else if (!enemies.length) push(actor, "shoot", "There are no live enemy units to target.");
          else if (localRangedAttackReach(profile) <= 0) push(actor, "shoot", `${{actor.name}} has no imported ranged weapon profile.`);
          else if (enemies.every((target) => localAttackDistance(actor, target) > localRangedAttackReach(profile))) push(actor, "shoot", `No live enemy unit is within ${{localRangedAttackReach(profile).toFixed(0)}}" tactical range.`);
        }} else if (phase === "charge") {{
          if (engagedEnemy) push(actor, "charge", `${{actor.name}} is already engaged with ${{engagedEnemy.name}}; fight in the Fight phase instead.`);
          else if (localUnitFellBackThisTurn(battleState, actor.instance_id)) push(actor, "charge", `${{actor.name}} fell back this turn and cannot charge.`);
          else if (localUnitAdvancedThisTurn(battleState, actor.instance_id)) push(actor, "charge", `${{actor.name}} advanced this turn and cannot charge.`);
          else if (!enemies.length) push(actor, "charge", "There are no live enemy units to charge.");
          else if (enemies.every((target) => localAttackDistance(actor, target) > 12)) push(actor, "charge", "No live enemy unit is within 12 inches for a charge.");
        }} else if (phase === "fight") {{
          if (!enemies.some((target) => localAttackDistance(actor, target) <= 1)) push(actor, "fight", `${{actor.name}} has no enemy unit in engagement range.`);
        }}
      }}
      return rows;
    }}

    function localNormalizedBattlePhase(phase) {{
      const value = String(phase || "movement").toLowerCase();
      return ["movement", "shooting", "charge", "fight", "scoring", "battlefield_ai"].includes(value) ? value : "movement";
    }}

    function localBattleActionAllowedInPhase(action, phase) {{
      if (action.type === "hold" || phase === "battlefield_ai") return true;
      const allowed = {{
        movement: ["move", "advance", "fall_back"],
        shooting: ["shoot"],
        charge: ["charge"],
        fight: ["fight"],
        scoring: ["score"]
      }};
      return (allowed[phase] || ["move"]).includes(action.type);
    }}

    function localUnitActedThisPhase(battleState, instanceId) {{
      const phase = localNormalizedBattlePhase(battleState.phase);
      return (battleState.log || []).some((entry) =>
        entry.turn === battleState.turn
        && localNormalizedBattlePhase(entry.phase) === phase
        && entry.actor_id === instanceId
        && entry.action !== "advance_phase"
      );
    }}

    function localUnitEngagedWithEnemy(battleState, actor) {{
      return (battleState.units || []).some((unit) =>
        unit.instance_id !== actor.instance_id
        && unit.side !== actor.side
        && unit.models_remaining > 0
        && localAttackDistance(actor, unit) <= 1
      );
    }}

    function localNearestEngagedEnemy(battleState, actor) {{
      return (battleState.units || [])
        .filter((unit) => unit.side !== actor.side && unit.models_remaining > 0 && localAttackDistance(actor, unit) <= 1)
        .sort((left, right) => localAttackDistance(actor, left) - localAttackDistance(actor, right) || String(left.instance_id).localeCompare(String(right.instance_id)))[0] || null;
    }}

    function localUnitFellBackThisTurn(battleState, instanceId) {{
      const unit = (battleState.units || []).find((row) => row.instance_id === instanceId);
      return Boolean(unit && (unit.status_flags || []).includes(`fell_back_turn_${{battleState.turn}}`));
    }}

    function localUnitAdvancedThisTurn(battleState, instanceId) {{
      const unit = (battleState.units || []).find((row) => row.instance_id === instanceId);
      return Boolean(unit && (unit.status_flags || []).includes(`advanced_turn_${{battleState.turn}}`));
    }}

    function localUnitMovedThisTurn(battleState, instanceId) {{
      const unit = (battleState.units || []).find((row) => row.instance_id === instanceId);
      return Boolean(unit && (unit.status_flags || []).includes(`moved_turn_${{battleState.turn}}`));
    }}

    function localBattleAttack(actor, target, attacker, defender, mode) {{
      const dist = localAttackDistance(actor, target);
      const visibility = localBattleVisibility(state.battlefield.state.map, actor, target);
      const reach = mode === "ranged" ? localRangedAttackReach(attacker) : 1;
      const inRange = mode !== "ranged" || dist <= reach;
      const context = normalizeContext({{ attacker_moved: localUnitMovedThisTurn(state.battlefield.state, actor.instance_id), attacker_advanced: localUnitAdvancedThisTurn(state.battlefield.state, actor.instance_id), target_in_cover: visibility.target_in_cover, target_within_half_range: dist <= Math.max(0, reach / 2), target_model_count: target.models_remaining }});
      const result = evaluateUnit(attacker, defender, mode, context);
      const damageMultiplier = mode === "ranged" ? visibility.damage_multiplier : 1;
      const assumptions = ["Damage uses the same local calculator engine.", mode === "melee" ? "Melee/charge is approximate in v1." : "Ranges use centre-to-centre distance."];
      if (mode === "ranged") assumptions.push(...localRangedAttackAssumptions(attacker));
      if (mode === "ranged" && !inRange) assumptions.push(`Target is ${{dist.toFixed(1)}}" away after footprints; no ranged weapon is assumed to reach beyond ${{reach.toFixed(1)}}".`);
      if (mode === "ranged" && visibility.line_of_sight_blocked) assumptions.push(`Intervening terrain obscures line of sight; ranged damage is multiplied by ${{damageMultiplier.toFixed(2)}}.`);
      return {{
        damage: inRange ? (result.total_damage || 0) * damageMultiplier : 0,
        context: {{ ...visibility, attacker_moved: context.attacker_moved, attacker_advanced: context.attacker_advanced, target_within_half_range: dist <= Math.max(0, reach / 2), target_model_count: target.models_remaining, attack_distance: Number(dist.toFixed(2)), weapon_range: mode === "ranged" ? Number(reach.toFixed(2)) : null, attack_in_range: inRange }},
        assumptions
      }};
    }}

    async function battlefieldGenerate() {{
      state.battlefield.state = localInitialBattleState();
      state.battlefield.plan = localBattlefieldPlan(6);
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield();
    }}

    function battlefieldPhase() {{
      return (state.battlefield.state && state.battlefield.state.phase) || "movement";
    }}

    function resetBattlefieldManualActions() {{
      state.battlefield.manualActions = [];
      state.battlefield.manualUnavailableActions = [];
      state.battlefield.manualActionNotice = "";
    }}

    async function refreshBattlefieldSelectedActions() {{
      const selected = battleUnitByInstance(state.battlefield.selectedInstanceId);
      if (!selected || !state.battlefield.state) {{
        state.battlefield.selectedInstanceId = null;
        state.battlefield.selectedUnitDetail = null;
        resetBattlefieldManualActions();
        return;
      }}
      await battlefieldLoadSelectedActions();
    }}

    async function setBattlefieldPhase(phase) {{
      if (!state.battlefield.state) return;
      state.battlefield.state.phase = phase || "movement";
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield();
    }}

    async function battlefieldRedeploy() {{
      const battleMap = state.battlefield.state && state.battlefield.state.map ? state.battlefield.state.map : null;
      state.battlefield.state = localInitialBattleState(battleMap);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      state.battlefield.validation = null;
      state.battlefield.selectedInstanceId = null;
      state.battlefield.selectedUnitDetail = null;
      renderBattlefield();
    }}

    async function battlefieldValidate() {{
      const validate = (army) => {{
        const errors = [];
        const warnings = [];
        let points = 0;
        const unitCount = army.units.reduce((sum, entry) => sum + Math.max(1, Number(entry.count || 1)), 0);
        const names = [];
        for (const [index, entry] of army.units.entries()) {{
          const count = Math.max(1, Number(entry.count || 1));
          const unit = state.units.find((row) => row.id === entry.unit_id);
          if (!entry.unit_id) {{
            errors.push(`Unit row ${{index + 1}} has no unit id.`);
            continue;
          }}
          if (!unit) {{
            errors.push(`Unknown unit id ${{entry.unit_id}}.`);
            continue;
          }}
          if (unit.points === null || unit.points === undefined || unit.points === "") {{
            warnings.push(`${{unit.name}} has no points value.`);
          }} else {{
            points += Number(unit.points || 0) * count;
          }}
          names.push(unit.name);
          if (!unit.weapons || !unit.weapons.length) warnings.push(`${{unit.name}} has no imported weapons.`);
          if (Number(unit.abilityCount || 0) > 0) warnings.push(`${{unit.name}} may have unsupported special rules in battlefield mode.`);
        }}
        for (const name of [...new Set(names)]) {{
          if (names.filter((row) => row === name).length > 1) warnings.push(`Duplicate unit name in list: ${{name}}.`);
        }}
        return {{ ok: errors.length === 0, points, unit_count: unitCount, warnings, errors }};
      }};
      const stateErrors = localStateValidationErrors(state.battlefield.state || localInitialBattleState());
      state.battlefield.validation = {{ red: validate(battlefieldArmies()[0]), blue: validate(battlefieldArmies()[1]), state: {{ ok: stateErrors.length === 0, warnings: ["Local state validation checks bounds, known unit ids, and blob overlaps."], errors: stateErrors }} }};
      renderBattlefield();
    }}

    async function battlefieldSuggest() {{
      if (!state.battlefield.state) state.battlefield.state = localInitialBattleState();
      state.battlefield.plan = localBattlefieldPlan(6);
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield();
    }}

    async function battlefieldAutoplay() {{
      if (!state.battlefield.state) state.battlefield.state = localInitialBattleState();
      const replay = [];
      localAutoplayOneTurn(replay);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield(replay);
    }}

    async function battlefieldAutoplayBattle() {{
      if (!state.battlefield.state) state.battlefield.state = localInitialBattleState();
      const turns = battleAutoplayTurnCount();
      const replay = [];
      for (let turn = 0; turn < turns; turn += 1) {{
        if (localBattleComplete()) break;
        localAutoplayOneTurn(replay);
      }}
      state.battlefield.state.phase = "movement";
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield(replay);
    }}

    function localAutoplayOneTurn(replay) {{
      const phases = ["movement", "shooting", "charge", "fight", "scoring"];
      if (localBattleComplete()) return 0;
      for (const side of ["red", "blue"]) {{
        if (localBattleComplete()) break;
        state.battlefield.state.active_side = side;
        for (const phase of phases) {{
          if (localBattleComplete()) break;
          state.battlefield.state.phase = phase;
          const actors = [...state.battlefield.state.units].filter((unit) => unit.side === side && unit.models_remaining > 0);
          for (const actor of actors) {{
            if (localBattleComplete()) break;
            const actions = localBattleActions().filter((row) => row.actor_id === actor.instance_id);
            const action = actions.find((row) => row.type !== "hold") || null;
            if (!action) continue;
            const outcome = localResolveBattleAction(action);
            replay.push({{ chosen: action, outcome }});
            if (localBattleComplete()) {{
              const entry = localBattleCompletionLogEntry();
              state.battlefield.state.log.push(entry);
              replay.push({{ chosen: null, outcome: entry }});
              break;
            }}
            if (phase === "scoring" && action.type === "score") break;
          }}
        }}
      }}
      if (!localBattleComplete()) {{
        state.battlefield.state.turn += 1;
        state.battlefield.state.active_side = "red";
        state.battlefield.state.phase = "movement";
      }}
      return 1;
    }}

    async function battlefieldNextPhase() {{
      if (!state.battlefield.state) return;
      const phases = ["movement", "shooting", "charge", "fight", "scoring"];
      const current = phases.includes(state.battlefield.state.phase) ? state.battlefield.state.phase : "movement";
      const phaseIndex = phases.indexOf(current);
      if (phaseIndex < phases.length - 1) {{
        state.battlefield.state.phase = phases[phaseIndex + 1];
      }} else if (state.battlefield.state.active_side === "red") {{
        state.battlefield.state.active_side = "blue";
        state.battlefield.state.phase = "movement";
      }} else {{
        state.battlefield.state.active_side = "red";
        state.battlefield.state.phase = "movement";
        state.battlefield.state.turn += 1;
      }}
      const entry = {{
        turn: state.battlefield.state.turn,
        phase: state.battlefield.state.phase,
        side: state.battlefield.state.active_side,
        action: "advance_phase",
        reason: `Advance to ${{state.battlefield.state.active_side}} ${{state.battlefield.state.phase}} phase.`
      }};
      state.battlefield.state.log.push(entry);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield([{{ outcome: entry }}]);
    }}

    function battleAutoplayTurnCount() {{
      const input = el("battle-autoplay-turns");
      const value = Math.max(1, Math.min(20, Number((input && input.value) || state.battlefield.autoplayTurns || 5)));
      state.battlefield.autoplayTurns = value;
      return value;
    }}

    function localBattleComplete() {{
      const liveSides = new Set((state.battlefield.state?.units || []).filter((unit) => unit.models_remaining > 0).map((unit) => unit.side));
      return !liveSides.has("red") || !liveSides.has("blue");
    }}

    function localBattleWinner() {{
      const liveSides = new Set((state.battlefield.state?.units || []).filter((unit) => unit.models_remaining > 0).map((unit) => unit.side));
      if (liveSides.size === 1 && liveSides.has("red")) return "red";
      if (liveSides.size === 1 && liveSides.has("blue")) return "blue";
      return "";
    }}

    function localBattleCompletionLogEntry() {{
      const winner = localBattleWinner();
      return {{
        turn: state.battlefield.state.turn,
        phase: state.battlefield.state.phase,
        side: winner || state.battlefield.state.active_side,
        action: "battle_complete",
        winner,
        reason: winner ? `${{titleCase(winner)}} wins; opposing side has no live battlefield units remaining.` : "Battle ended with no live battlefield units remaining."
      }};
    }}

    async function battlefieldResolvePlannedAction(index) {{
      const action = state.battlefield.plan && state.battlefield.plan.actions
        ? state.battlefield.plan.actions[Number(index)]
        : null;
      if (!action) throw new Error("No planned action found.");
      const outcome = localResolveBattleAction(action);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield([{{ chosen: action, outcome }}]);
    }}

    async function battlefieldLoadSelectedActions() {{
      const selected = battleUnitByInstance(state.battlefield.selectedInstanceId);
      if (!selected || !state.battlefield.state) {{
        resetBattlefieldManualActions();
        return;
      }}
      if (Number(selected.models_remaining || 0) <= 0 || (selected.status_flags || []).includes("destroyed")) {{
        resetBattlefieldManualActions();
        state.battlefield.manualActionNotice = `${{selected.name || "Selected unit"}} has no live models and cannot act.`;
        return;
      }}
      if (selected.side !== state.battlefield.state.active_side) {{
        resetBattlefieldManualActions();
        state.battlefield.manualActionNotice = `${{titleCase(selected.side)}} is waiting; ${{titleCase(state.battlefield.state.active_side)}} is active.`;
        return;
      }}
      state.battlefield.manualActionNotice = "";
      state.battlefield.manualActions = localBattleActions().filter((action) => action.actor_id === selected.instance_id);
      state.battlefield.manualUnavailableActions = localUnavailableBattleActions().filter((action) => action.actor_id === selected.instance_id);
    }}

    async function battlefieldResolveManualAction(index) {{
      const action = state.battlefield.manualActions ? state.battlefield.manualActions[Number(index)] : null;
      if (!action) throw new Error("No selected-unit action found.");
      const outcome = localResolveBattleAction(action);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      await refreshBattlefieldSelectedActions();
      renderBattlefield([{{ chosen: action, outcome }}]);
    }}

    function battlefieldExportPayload(kind = "state") {{
      const battleState = state.battlefield.state;
      const replayEntries = battleState && Array.isArray(battleState.log) ? battleState.log : [];
      const payload = {{
        format: kind === "armies" ? "army_list_v1" : (kind === "replay" ? "battle_replay_v1" : (kind === "map" ? "battle_map_v1" : "battle_state_v1")),
        schema_version: 1,
        rules_edition: el("edition").value || state.rulesEdition,
        rules_preset: (battleState && battleState.map && battleState.map.rules_preset) || "tactical_mvp_v1",
        template_id: state.battlefield.selectedTemplate,
        armies: battlefieldArmies(),
        exported_at: new Date().toISOString()
      }};
      if (kind === "map") {{
        payload.map = battleState ? battleState.map : null;
        return payload;
      }}
      if (kind === "replay") {{
        payload.replay_entries = replayEntries;
        payload.final_state = battleState;
        return payload;
      }}
      if (kind !== "armies") payload.state = state.battlefield.state;
      return payload;
    }}

    function battlefieldDownloadJson(payload, prefix) {{
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: "application/json" }});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${{prefix}}-${{Date.now()}}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    }}

    function battlefieldExportJson() {{
      battlefieldDownloadJson(battlefieldExportPayload("state"), "battlefield-state");
    }}

    function battlefieldExportArmiesJson() {{
      battlefieldDownloadJson(battlefieldExportPayload("armies"), "army-list");
    }}

    function battlefieldExportMapJson() {{
      battlefieldDownloadJson(battlefieldExportPayload("map"), "battle-map");
    }}

    function battlefieldExportReplayJson() {{
      battlefieldDownloadJson(battlefieldExportPayload("replay"), "battle-replay");
    }}

    async function battlefieldImportJson(file) {{
      const text = await file.text();
      const payload = JSON.parse(text);
      validateBattlefieldImportMetadata(payload);
      if (payload.format === "battle_replay_v1") {{
        const importedState = payload.final_state || payload.state;
        if (!importedState || !importedState.map || !Array.isArray(importedState.units)) {{
          throw new Error("Battlefield replay import must contain a final_state battle state.");
        }}
        validateImportedBattleState(importedState);
        if (!Array.isArray(importedState.log) || !importedState.log.length) {{
          importedState.log = Array.isArray(payload.replay_entries) ? payload.replay_entries : [];
        }}
        state.battlefield.state = importedState;
        state.battlefield.selectedTemplate = importedState.map.id || payload.template_id || state.battlefield.selectedTemplate;
        applyBattlefieldArmies(payload.armies || importedState.armies || []);
        state.battlefield.plan = null;
        resetBattlefieldManualActions();
        state.battlefield.validation = null;
        state.battlefield.selectedInstanceId = null;
        state.battlefield.selectedUnitDetail = null;
        const replayRows = (payload.replay_entries || importedState.log || []).map((entry) => ({{ outcome: entry }}));
        renderBattlefield(replayRows);
        return;
      }}
      if (payload.format === "battle_map_v1") {{
        const importedMap = payload.map || payload;
        if (!importedMap || !Array.isArray(importedMap.deployment_zones) || !Array.isArray(importedMap.objectives)) {{
          throw new Error("Battlefield map import must contain a battle_map_v1 map object.");
        }}
        const mapErrors = localMapValidationErrors(importedMap);
        if (mapErrors.length) throw new Error(mapErrors.join("; "));
        state.battlefield.selectedTemplate = importedMap.id || payload.template_id || state.battlefield.selectedTemplate;
        state.battlefield.state = localInitialBattleState(importedMap);
        state.battlefield.plan = null;
        resetBattlefieldManualActions();
        state.battlefield.validation = null;
        state.battlefield.selectedInstanceId = null;
        state.battlefield.selectedUnitDetail = null;
        renderBattlefield();
        return;
      }}
      if (payload.format === "army_list_v1" || (Array.isArray(payload.armies) && !payload.state && !payload.map)) {{
        applyBattlefieldArmies(payload.armies || []);
        state.battlefield.selectedTemplate = payload.template_id || state.battlefield.selectedTemplate;
        state.battlefield.state = null;
        state.battlefield.plan = null;
        resetBattlefieldManualActions();
        state.battlefield.validation = null;
        state.battlefield.selectedInstanceId = null;
        state.battlefield.selectedUnitDetail = null;
        renderBattlefield();
        return;
      }}
      const importedState = payload.state || payload;
      if (!importedState || !importedState.map || !Array.isArray(importedState.units)) {{
        throw new Error("Battlefield import must contain a battle_state_v1 state object or army_list_v1 armies.");
      }}
      validateImportedBattleState(importedState);
      state.battlefield.state = importedState;
      state.battlefield.selectedTemplate = importedState.map.id || payload.template_id || state.battlefield.selectedTemplate;
      applyBattlefieldArmies(payload.armies || importedState.armies || []);
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      state.battlefield.validation = null;
      state.battlefield.selectedInstanceId = null;
      state.battlefield.selectedUnitDetail = null;
      renderBattlefield();
    }}

    function validateBattlefieldImportMetadata(payload) {{
      const currentEdition = el("edition").value || state.rulesEdition;
      if (payload.schema_version && Number(payload.schema_version) > 1) {{
        throw new Error(`Battlefield file schema ${{payload.schema_version}} is newer than this app supports.`);
      }}
      if (payload.rules_edition && payload.rules_edition !== currentEdition) {{
        throw new Error(`Battlefield file uses ${{editionLabel(payload.rules_edition)}} data, but the app is using ${{editionLabel(currentEdition)}}.`);
      }}
      if (payload.rules_preset && payload.rules_preset !== "tactical_mvp_v1") {{
        throw new Error(`Battlefield file uses unsupported rules preset ${{payload.rules_preset}}.`);
      }}
    }}

    function validateImportedBattleState(importedState) {{
      const errors = localStateValidationErrors(importedState);
      if (errors.length) throw new Error(errors.join("; "));
    }}

    function applyBattlefieldArmies(armies) {{
      const red = armies.find((army) => army.side === "red");
      const blue = armies.find((army) => army.side === "blue");
      state.battlefield.armyRows = {{
        red: red && red.units ? red.units.map((row) => ({{ unitId: row.unit_id, count: Math.max(1, Number(row.count || 1)) }})) : [],
        blue: blue && blue.units ? blue.units.map((row) => ({{ unitId: row.unit_id, count: Math.max(1, Number(row.count || 1)) }})) : []
      }};
      syncLegacyBattlefieldSelections();
    }}

    function localResolveBattleAction(action) {{
      const battleState = state.battlefield.state;
      const actor = battleState.units.find((unit) => unit.instance_id === action.actor_id);
      if (!actor) throw new Error(`Unknown actor ${{action.actor_id}}`);
      const phase = localNormalizedBattlePhase(battleState.phase);
      if (Number(actor.models_remaining || 0) <= 0 || (actor.status_flags || []).includes("destroyed")) throw new Error(`${{actor.name}} cannot act because it has no live models.`);
      if (action.side && action.side !== actor.side) throw new Error(`Action side ${{action.side}} does not match actor side ${{actor.side}}.`);
      if (phase !== "battlefield_ai" && actor.side !== battleState.active_side) throw new Error(`${{actor.name}} cannot act during ${{battleState.active_side}}'s turn.`);
      if (!localBattleActionAllowedInPhase(action, phase)) throw new Error(`${{action.type}} actions are not available in the ${{phase}} phase.`);
      if (localUnitActedThisPhase(battleState, actor.instance_id)) throw new Error(`${{actor.name}} has already acted in the ${{phase}} phase.`);
      if (["move", "advance", "fall_back"].includes(action.type) && !action.destination) throw new Error(`${{action.type}} actions require a destination.`);
      if (["move", "advance"].includes(action.type) && localUnitEngagedWithEnemy(battleState, actor)) throw new Error(`${{actor.name}} cannot ${{action.type}} while engaged; fall back instead.`);
      if (action.type === "fall_back" && !localNearestEngagedEnemy(battleState, actor)) throw new Error(`${{actor.name}} can only fall back while engaged with an enemy unit.`);
      if (["shoot", "charge"].includes(action.type) && localUnitFellBackThisTurn(battleState, actor.instance_id)) throw new Error(`${{actor.name}} cannot ${{action.type}} after falling back this turn.`);
      if (action.type === "charge" && localUnitAdvancedThisTurn(battleState, actor.instance_id)) throw new Error(`${{actor.name}} cannot charge after advancing this turn.`);
      if (action.type === "shoot" && localUnitEngagedWithEnemy(battleState, actor)) throw new Error(`${{actor.name}} cannot make a normal shooting action while engaged.`);
      if (action.type === "charge" && localUnitEngagedWithEnemy(battleState, actor)) throw new Error(`${{actor.name}} cannot charge while already engaged.`);
      if (["shoot", "charge", "fight"].includes(action.type)) {{
        if (!action.target_id) throw new Error(`${{action.type}} actions require a target.`);
        const target = battleState.units.find((unit) => unit.instance_id === action.target_id);
        if (!target) throw new Error(`Unknown target ${{action.target_id}}.`);
        if (target.side === actor.side) throw new Error(`${{actor.name}} cannot target a friendly unit.`);
        if (Number(target.models_remaining || 0) <= 0 || (target.status_flags || []).includes("destroyed")) throw new Error(`${{actor.name}} cannot target ${{target.name}} because it has no live models.`);
        if (action.type === "fight" && localAttackDistance(actor, target) > 1) throw new Error(`${{actor.name}} can only fight targets within engagement range.`);
        if (action.type === "charge" && localAttackDistance(actor, target) > 12) throw new Error(`${{actor.name}} cannot charge a target more than 12 inches away.`);
      }}
      const entry = {{ turn: battleState.turn, phase: battleState.phase, side: action.side, actor_id: actor.instance_id, actor: actor ? actor.name : action.actor_id, action: action.type, reason: action.reason, assumptions: action.assumptions || [] }};
      if (["move", "advance", "fall_back"].includes(action.type) && action.destination && actor) {{
        const profile = state.units.find((unit) => unit.id === actor.unit_id);
        const limited = profile ? localMovementLimitedDestination(battleState, actor, profile, action.destination, action.type === "advance" ? 3.5 : 0, action.type === "advance" ? ["Advance movement uses an expected D6 roll of 3.5 inches."] : []) : {{ destination: action.destination, assumptions: [] }};
        const moved = localNonOverlappingDestination(battleState, actor, limited.destination);
        actor.x = moved.destination.x;
        actor.y = moved.destination.y;
        actor.status_flags = [...new Set([...(actor.status_flags || []), `moved_turn_${{battleState.turn}}`])].sort();
        entry.status_flags = actor.status_flags;
        if (action.type === "advance") {{
          actor.status_flags = [...new Set([...(actor.status_flags || []), `advanced_turn_${{battleState.turn}}`])].sort();
          entry.status_flags = actor.status_flags;
          entry.assumptions = [...entry.assumptions, "Advancing prevents this unit from charging later in the same turn.", "Ranged attacks after advancing are resolved through the calculator's attacker_advanced context."];
        }}
        if (action.type === "fall_back") {{
          actor.status_flags = [...new Set([...(actor.status_flags || []), `fell_back_turn_${{battleState.turn}}`])].sort();
          entry.status_flags = actor.status_flags;
          entry.assumptions = [...entry.assumptions, "Falling back prevents this unit from shooting or charging later in the same turn."];
        }}
        if (limited.assumptions.length || moved.assumptions.length) entry.assumptions = [...entry.assumptions, ...limited.assumptions, ...moved.assumptions];
      }} else if (action.type === "score" && actor) {{
        const controlled = localSideScoredThisTurn(battleState, actor.side) ? [] : localControlledObjectivesForSide(battleState, actor.side);
        const gained = controlled.reduce((sum, objective) => sum + Number(objective.points || 0), 0);
        battleState.score[actor.side] = Number(battleState.score[actor.side] || 0) + gained;
        entry.score_delta = {{ [actor.side]: gained }};
        entry.objectives = controlled.map((objective) => objective.name);
      }} else if (["shoot", "charge", "fight"].includes(action.type)) {{
        const target = battleState.units.find((unit) => unit.instance_id === action.target_id);
        const targetProfile = target && state.units.find((unit) => unit.id === target.unit_id);
        const actorProfile = actor && state.units.find((unit) => unit.id === actor.unit_id);
        if (target && targetProfile && actorProfile) {{
          const mode = action.type === "shoot" ? "ranged" : "melee";
          const calculated = action.expected_damage ? null : localBattleAttack(actor, target, actorProfile, targetProfile, mode);
          const probability = action.type === "charge" ? localChargeProbability(actor, target) : 1;
          const fullDamage = calculated ? calculated.damage : Number(action.expected_damage || 0) / probability;
          const expectedFollowupDamage = action.type === "charge"
            ? (calculated ? calculated.damage * probability : Number(action.expected_damage || 0))
            : 0;
          const expectedDamage = action.type === "charge" ? 0 : (calculated ? calculated.damage : Number(action.expected_damage || 0));
          let chargeMoveAssumptions = [];
          target.wounds_remaining = Math.max(0, target.wounds_remaining - expectedDamage);
          target.models_remaining = Math.max(0, Math.ceil(target.wounds_remaining / Math.max(1, Number(targetProfile.wounds || 1))));
          if (target.models_remaining <= 0) target.status_flags = ["destroyed"];
          if (action.type === "charge" && target.models_remaining > 0) {{
            const moved = localChargeEngagementDestination(battleState, actor, target);
            actor.x = moved.destination.x;
            actor.y = moved.destination.y;
            entry.destination = {{ x: Number(actor.x.toFixed(2)), y: Number(actor.y.toFixed(2)) }};
            chargeMoveAssumptions = moved.assumptions;
          }}
          entry.target = target.name;
          entry.damage = expectedDamage;
          entry.models_remaining = target.models_remaining;
          entry.context = action.context || calculated.context || {{}};
          if (calculated) entry.assumptions = calculated.assumptions;
          if (action.type === "charge") {{
            entry.context.charge_probability = probability;
            entry.context.full_melee_damage_if_charge_connects = fullDamage;
            entry.context.expected_followup_fight_damage = expectedFollowupDamage;
            entry.assumptions = [
              ...entry.assumptions,
              ...chargeMoveAssumptions,
              "Charge resolution moves the unit into engagement range; melee damage is resolved in the Fight phase.",
              `AI scoring still values the charge using ${{Math.round(probability * 100)}}% simplified charge probability for follow-up fight damage.`
            ];
          }}
        }}
      }}
      battleState.log.push(entry);
      return entry;
    }}

    function localChargeEngagementDestination(battleState, actor, target) {{
      if (localAttackDistance(actor, target) <= 1) {{
        return {{
          destination: {{ x: Number(actor.x.toFixed(2)), y: Number(actor.y.toFixed(2)) }},
          assumptions: ["Charge movement already ends in engagement range."]
        }};
      }}
      const centreDistance = distance(actor.x, actor.y, target.x, target.y);
      const directionX = centreDistance > 0 ? (actor.x - target.x) / centreDistance : -1;
      const directionY = centreDistance > 0 ? (actor.y - target.y) / centreDistance : 0;
      const desiredDistance = Number(actor.radius || 0) + Number(target.radius || 0) + 0.5;
      const moved = localNonOverlappingDestination(battleState, actor, {{
        x: target.x + directionX * desiredDistance,
        y: target.y + directionY * desiredDistance
      }});
      return {{
        destination: moved.destination,
        assumptions: ["Successful charge movement is modeled deterministically into engagement range after expected damage.", ...moved.assumptions]
      }};
    }}

    function renderBattlefield(replay = null) {{
      const battleState = state.battlefield.state;
      const templates = state.battlefield.templates.length ? state.battlefield.templates : localBattlefieldTemplates();
      el("results").dataset.view = "battlefield";
      el("results").innerHTML = `
        <div class="battlefield" data-testid="battlefield-view">
          <div class="battlefield-toolbar" data-testid="battlefield-toolbar">
            <div class="battlefield-control-group" data-testid="battlefield-map-controls">
              <h3>Map</h3>
              <div class="battlefield-control-row">
                <div><label for="battle-template">Map template</label><select id="battle-template">${{templates.map((template) => `<option value="${{escapeHtml(template.id)}}">${{escapeHtml(template.name)}}</option>`).join("")}}</select></div>
                <button id="battle-generate" type="button">Generate map</button>
                <button id="battle-redeploy" class="secondary" type="button">Redeploy armies</button>
              </div>
            </div>
            <div class="battlefield-control-group" data-testid="battlefield-turn-controls">
              <h3>Turn and AI</h3>
              <div class="battlefield-control-row">
                <div><label for="battle-phase">Phase</label><select id="battle-phase" ${{battleState ? "" : "disabled"}}>${{["movement", "shooting", "charge", "fight", "scoring"].map((phase) => `<option value="${{phase}}" ${{battlefieldPhase() === phase ? "selected" : ""}}>${{escapeHtml(titleCase(phase))}}</option>`).join("")}}</select></div>
                <button id="battle-next-phase" class="secondary" type="button" ${{battleState ? "" : "disabled"}}>Next phase</button>
                <button id="battle-suggest" class="secondary" type="button">Suggest AI action</button>
                <button id="battle-autoplay" class="secondary" type="button">Run one AI turn</button>
                <div><label for="battle-autoplay-turns">AI turns</label><input id="battle-autoplay-turns" type="number" min="1" max="20" step="1" value="${{escapeHtml(state.battlefield.autoplayTurns || 5)}}"></div>
                <button id="battle-autoplay-battle" class="secondary" type="button">Autoplay turns</button>
              </div>
            </div>
            <div class="battlefield-control-group" data-testid="battlefield-file-controls">
              <h3>Files</h3>
              <div class="battlefield-control-row">
                <button id="battle-export" class="tertiary" type="button">Export JSON</button>
                <button id="battle-export-armies" class="tertiary" type="button">Export armies</button>
                <button id="battle-export-map" class="tertiary" type="button">Export map</button>
                <button id="battle-export-replay" class="tertiary" type="button">Export replay</button>
                <button id="battle-import" class="tertiary" type="button">Import JSON</button>
              </div>
              <input id="battle-import-file" type="file" accept="application/json,.json" hidden>
            </div>
          </div>
          <div class="battlefield-armies">${{renderArmyBuilder("red", battlefieldArmyRows("red"))}}${{renderArmyBuilder("blue", battlefieldArmyRows("blue"))}}</div>
          <button id="battle-validate" class="tertiary" type="button">Validate armies and state</button>
          ${{renderBattleTurnTracker(battleState)}}
          ${{renderBattleOutcomeSummary(battleState)}}
          <div class="battlefield-main-grid">
            <div>${{battleState ? renderBattleBoard(battleState) : renderBattlefieldEmptyState()}}</div>
            <div class="battlefield-side-panels battlefield-panels"><div class="battle-panel"><h3>Selected unit</h3>${{renderSelectedBattleUnit(battleState)}}${{renderManualBattleActions()}}</div><div class="battle-panel"><h3>AI planner</h3>${{renderBattlePlan(state.battlefield.plan)}}</div><div class="battle-panel"><h3>Battle log</h3>${{renderBattleLog(battleState, replay)}}</div></div>
          </div>
          ${{renderBattleValidation(state.battlefield.validation)}}
        </div>
      `;
      el("battle-template").value = state.battlefield.selectedTemplate;
      if (el("battle-autoplay-turns")) el("battle-autoplay-turns").value = state.battlefield.autoplayTurns || 5;
      if (el("battle-phase")) el("battle-phase").value = battlefieldPhase();
      wireBattlefieldEvents();
    }}

    function renderBattlefieldEmptyState() {{
      return `<div class="battlefield-empty" data-testid="battlefield-empty-state"><svg class="battlefield-empty-art" data-testid="battlefield-empty-art" viewBox="0 0 260 180" role="img" aria-label="Generated battlefield preview"><defs><pattern id="empty-grid" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M 16 0 L 0 0 0 16" fill="none" stroke="#dfe7ee" stroke-width="1"></path></pattern><linearGradient id="empty-board" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#f7fafc"></stop><stop offset="1" stop-color="#eef4f1"></stop></linearGradient></defs><rect x="28" y="16" width="204" height="148" rx="10" fill="url(#empty-board)" stroke="#cfd8e3"></rect><rect x="28" y="16" width="204" height="148" rx="10" fill="url(#empty-grid)" opacity=".75"></rect><rect x="42" y="30" width="176" height="26" rx="6" fill="rgba(165,36,44,.09)" stroke="rgba(165,36,44,.35)" stroke-dasharray="5 4"></rect><rect x="42" y="124" width="176" height="26" rx="6" fill="rgba(33,99,159,.09)" stroke="rgba(33,99,159,.35)" stroke-dasharray="5 4"></rect><rect x="58" y="72" width="44" height="28" rx="3" fill="#d9dde3" stroke="#667483" stroke-width="2"></rect><rect x="158" y="72" width="44" height="28" rx="3" fill="#d5e0cf" stroke="#81906f" stroke-width="2"></rect><circle cx="130" cy="90" r="15" fill="rgba(170,122,30,.2)" stroke="#aa7a1e" stroke-width="3"></circle><circle cx="72" cy="45" r="7" fill="#a5242c"></circle><circle cx="188" cy="137" r="7" fill="#21639f"></circle><path d="M 78 45 C 104 66, 128 65, 130 90 C 137 111, 164 118, 181 137" fill="none" stroke="#6b7b8d" stroke-width="3" stroke-dasharray="7 6" stroke-linecap="round"></path></svg><div class="battlefield-empty-copy"><h3>Ready for deployment</h3><p>Generate a map to place the selected armies, then drag units, ask for AI suggestions, or autoplay a turn.</p></div></div>`;
    }}

    function renderBattleTurnTracker(battleState) {{
      if (!battleState) return "";
      const redLive = (battleState.units || []).filter((unit) => unit.side === "red" && Number(unit.models_remaining || 0) > 0).length;
      const blueLive = (battleState.units || []).filter((unit) => unit.side === "blue" && Number(unit.models_remaining || 0) > 0).length;
      const status = battleCompleteStatus(battleState);
      return `<div class="battle-turn-tracker" data-testid="battle-turn-tracker"><div class="turn-chip"><b>Turn</b><span>${{escapeHtml(battleState.turn || 1)}}</span></div><div class="turn-chip"><b>Active side</b><span>${{escapeHtml(titleCase(battleState.active_side || "red"))}}</span></div><div class="turn-chip"><b>Phase</b><span>${{escapeHtml(titleCase(battlefieldPhase()))}}</span></div><div class="turn-chip"><b>Score</b><span>Red ${{escapeHtml((battleState.score || {{}}).red || 0)}} | Blue ${{escapeHtml((battleState.score || {{}}).blue || 0)}}</span></div><div class="turn-chip"><b>Live units</b><span>Red ${{redLive}} | Blue ${{blueLive}}</span></div><div class="turn-chip"><b>Status</b><span>${{escapeHtml(status.label)}}</span></div></div>`;
    }}

    function battleCompleteStatus(battleState) {{
      const redLive = (battleState.units || []).some((unit) => unit.side === "red" && Number(unit.models_remaining || 0) > 0);
      const blueLive = (battleState.units || []).some((unit) => unit.side === "blue" && Number(unit.models_remaining || 0) > 0);
      if (redLive && !blueLive) return {{ complete: true, winner: "red", label: "Battle complete: Red wins" }};
      if (blueLive && !redLive) return {{ complete: true, winner: "blue", label: "Battle complete: Blue wins" }};
      if (!redLive && !blueLive) return {{ complete: true, winner: "", label: "Battle complete: no live units" }};
      return {{ complete: false, winner: "", label: "In progress" }};
    }}

    function renderBattleOutcomeSummary(battleState) {{
      if (!battleState) return "";
      const summary = battleOutcomeSummary(battleState);
      return `<div class="summary battle-summary" data-testid="battle-outcome-summary">${{metric("Battlefield judgement", escapeHtml(summary.judgement))}}${{metric("VP", `Red ${{summary.redScore}} | Blue ${{summary.blueScore}}`)}}${{metric("Live units", `Red ${{summary.redLive}} | Blue ${{summary.blueLive}}`)}}${{metric("Points remaining", `Red ${{fmt(summary.redPoints)}} | Blue ${{fmt(summary.bluePoints)}}`)}}</div><div class="small">${{escapeHtml(summary.reason)}}</div>`;
    }}

    function battleOutcomeSummary(battleState) {{
      const redUnits = (battleState.units || []).filter((unit) => unit.side === "red");
      const blueUnits = (battleState.units || []).filter((unit) => unit.side === "blue");
      const redLive = redUnits.filter((unit) => Number(unit.models_remaining || 0) > 0).length;
      const blueLive = blueUnits.filter((unit) => Number(unit.models_remaining || 0) > 0).length;
      const redScore = Number((battleState.score || {{}}).red || 0);
      const blueScore = Number((battleState.score || {{}}).blue || 0);
      const redPoints = remainingBattlePoints(redUnits);
      const bluePoints = remainingBattlePoints(blueUnits);
      let judgement = "Close";
      let reason = "The battle is currently close on VP and remaining force.";
      if (redLive === 0 && blueLive > 0) {{
        judgement = "Blue winning";
        reason = "Red has no live battlefield units remaining.";
      }} else if (blueLive === 0 && redLive > 0) {{
        judgement = "Red winning";
        reason = "Blue has no live battlefield units remaining.";
      }} else if (redScore !== blueScore) {{
        judgement = redScore > blueScore ? "Red ahead" : "Blue ahead";
        reason = `${{judgement}} on mission score by ${{Math.abs(redScore - blueScore)}} VP.`;
      }} else if (Math.abs(redPoints - bluePoints) >= 25) {{
        judgement = redPoints > bluePoints ? "Red ahead" : "Blue ahead";
        reason = `${{judgement}} on remaining army value with tied VP.`;
      }}
      return {{ judgement, reason, redScore, blueScore, redLive, blueLive, redPoints, bluePoints }};
    }}

    function remainingBattlePoints(units) {{
      return units.reduce((total, unit) => {{
        const profile = battlefieldAvailableUnits().find((row) => row.id === unit.unit_id) || state.unitDetails[unit.unit_id] || {{}};
        const startingModels = defaultBattleModels(profile, unit.models_remaining || 1);
        const points = Number(profile.points || 0);
        return total + (points ? points * Math.max(0, Number(unit.models_remaining || 0)) / startingModels : 0);
      }}, 0);
    }}

    function defaultBattleModels(profile, fallback = 1) {{
      const min = Number(profile.models_min || profile.modelsMin || 0);
      const max = Number(profile.models_max || profile.modelsMax || 0);
      if (min && max) return Math.max(1, Math.round((min + max) / 2));
      if (min) return Math.max(1, min);
      return Math.max(1, Number(fallback || 1));
    }}

    function renderArmyBuilder(side, rows) {{
      const armyRows = rows.length ? rows : [{{ unitId: "", count: 1 }}];
      const faction = battlefieldFaction(side);
      const factionOptions = battlefieldFactionOptions();
      const visibleUnits = filteredBattlefieldUnits(side).length;
      return `<div class="army-card ${{side}}"><h3>${{side === "red" ? "Red army" : "Blue army"}}</h3><label for="battle-${{side}}-faction">Faction</label><select id="battle-${{side}}-faction" class="battle-army-faction" data-side="${{side}}"><option value="">All factions</option>${{factionOptions.map((name) => `<option value="${{escapeHtml(name)}}" ${{name === faction ? "selected" : ""}}>${{escapeHtml(name)}}</option>`).join("")}}</select><div class="small">${{visibleUnits}} selectable units</div>${{armyRows.map((row, index) => renderArmyRow(side, row, index)).join("")}}<button class="tertiary battle-add-unit" type="button" data-side="${{side}}">Add unit</button><div class="small">${{escapeHtml(armySummaryText(armyRows))}}</div></div>`;
    }}

    function renderArmyRow(side, row, index) {{
      const filteredUnits = filteredBattlefieldUnits(side);
      const selectedUnit = battlefieldAvailableUnits().find((unit) => unit.id === row.unitId);
      const options = selectedUnit && !filteredUnits.some((unit) => unit.id === selectedUnit.id)
        ? [selectedUnit, ...filteredUnits]
        : filteredUnits;
      return `<div class="army-row" data-side="${{side}}" data-index="${{index}}"><div><label for="battle-${{side}}-unit-${{index}}">Unit ${{index + 1}}</label><select id="battle-${{side}}-unit-${{index}}" class="battle-army-unit" data-side="${{side}}" data-index="${{index}}"><option value="">Choose unit</option>${{options.map((unit) => `<option value="${{escapeHtml(unit.id || "")}}">${{escapeHtml(unit.name)}}${{unit.points ? ` (${{unit.points}} pts)` : ""}}</option>`).join("")}}</select></div><div><label for="battle-${{side}}-count-${{index}}">Copies</label><input id="battle-${{side}}-count-${{index}}" class="battle-army-count" data-side="${{side}}" data-index="${{index}}" type="number" min="1" max="12" step="1" value="${{Math.max(1, Number(row.count || 1))}}"></div><button class="army-remove" type="button" data-side="${{side}}" data-index="${{index}}" aria-label="Remove unit row">X</button></div>`;
    }}

    function renderBattleBoard(battleState) {{
      const battleMap = battleState.map;
      const redLive = (battleState.units || []).filter((unit) => unit.side === "red" && Number(unit.models_remaining || 0) > 0).length;
      const blueLive = (battleState.units || []).filter((unit) => unit.side === "blue" && Number(unit.models_remaining || 0) > 0).length;
      const deploymentZones = (battleMap.deployment_zones || []).map((zone) => `<g class="bf-deployment-zone" data-side="${{escapeHtml(zone.side || "")}}"><rect class="bf-deployment ${{escapeHtml(zone.side || "")}}" x="${{zone.x}}" y="${{zone.y}}" width="${{zone.width}}" height="${{zone.height}}"><title>${{escapeHtml(titleCase(zone.side || "Unknown"))}} deployment zone</title></rect><text class="bf-deployment-label" x="${{Number(zone.x || 0) + Number(zone.width || 0) / 2}}" y="${{Number(zone.y || 0) + Number(zone.height || 0) / 2}}">${{escapeHtml(titleCase(zone.side || ""))}} DZ</text></g>`).join("");
      const terrain = (battleMap.terrain || []).map((feature) => renderTerrainFeature(feature)).join("");
      const objectives = (battleMap.objectives || []).map((objective, index) => `<circle class="bf-objective" cx="${{objective.x}}" cy="${{objective.y}}" r="${{objective.radius}}" data-objective-index="${{index}}" data-hover-text="${{escapeHtml(objectiveTooltip(objective, index))}}"></circle><text class="bf-objective-label" x="${{objective.x}}" y="${{objective.y}}">${{escapeHtml(battleObjectiveLabel(objective, index))}}</text>`).join("");
      const overlays = renderBattleOverlays(battleState);
      const units = (battleState.units || []).map((unit) => {{
        const profile = battleUnitProfile(unit);
        const radius = Number(unit.radius || 1);
        const selected = state.battlefield.selectedInstanceId === unit.instance_id;
        const badgeRadius = Math.max(0.72, Math.min(1.25, radius * 0.42));
        const badgeX = Number(unit.x || 0) + radius * 0.68;
        const badgeY = Number(unit.y || 0) - radius * 0.68;
        const statY = Number(unit.y || 0) + radius * 0.42;
        const nameLabel = selected ? `<text class="bf-unit-name-label" x="${{unit.x}}" y="${{Number(unit.y || 0) + radius + 1.5}}" textLength="${{battleUnitNameLabelWidth(unit)}}" lengthAdjust="spacingAndGlyphs">${{escapeHtml(shortUnitLabel(unit.name))}}</text>` : "";
        return `<g class="bf-unit-marker ${{escapeHtml(unit.side)}}" data-unit-id="${{escapeHtml(unit.instance_id)}}" data-hover-text="${{escapeHtml(battleUnitTooltip(unit, profile, battleState))}}"><circle class="bf-unit ${{escapeHtml(unit.side)}} ${{(unit.status_flags || []).includes("destroyed") ? "destroyed" : ""}} ${{selected ? "selected" : ""}}" cx="${{unit.x}}" cy="${{unit.y}}" r="${{unit.radius}}" data-unit-id="${{escapeHtml(unit.instance_id)}}"></circle><text class="bf-label" x="${{unit.x}}" y="${{Number(unit.y || 0) - radius * 0.18}}" font-size="${{battleLabelFontSize(unit)}}">${{escapeHtml(unitInitials(unit.name))}}</text><text class="bf-unit-stat-label" x="${{unit.x}}" y="${{statY}}" textLength="${{battleUnitStatLabelWidth(unit)}}" lengthAdjust="spacingAndGlyphs">${{escapeHtml(battleUnitStatText(unit))}}</text><circle class="bf-unit-badge" cx="${{badgeX}}" cy="${{badgeY}}" r="${{badgeRadius}}"></circle><text class="bf-unit-badge-text" x="${{badgeX}}" y="${{badgeY}}">${{escapeHtml(battleUnitBadgeText(unit))}}</text>${{nameLabel}}</g>`;
      }}).join("");
      return `<div class="battlefield-board-wrap"><div class="battlefield-board-header" data-testid="battlefield-board-header"><div class="battlefield-board-title"><h3>${{escapeHtml(battleMap.name || "Battlefield")}}</h3><div class="small">${{escapeHtml(battleMap.width)}}" x ${{escapeHtml(battleMap.height)}}" | ${{escapeHtml(titleCase(battleState.phase || "movement"))}} phase | Red ${{redLive}} live, Blue ${{blueLive}} live</div></div><div class="battlefield-board-legend" aria-label="Battlefield legend">${{renderTerrainLegend(battleMap)}}${{renderObjectiveLegend(battleMap)}}<span><i class="legend-swatch red"></i>Red unit</span><span><i class="legend-swatch blue"></i>Blue unit</span></div></div><svg class="battlefield-board" id="battle-board" viewBox="0 0 ${{battleMap.width}} ${{battleMap.height}}" data-width="${{battleMap.width}}" data-height="${{battleMap.height}}" role="img" aria-label="${{escapeHtml(battleMap.name)}} battlefield"><defs><pattern id="bf-grid" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M 4 0 L 0 0 0 4" fill="none" stroke="#dfe7ee" stroke-width="0.08"></path></pattern></defs><rect class="bf-board-bg" x="0" y="0" width="${{battleMap.width}}" height="${{battleMap.height}}"></rect><rect x="0" y="0" width="${{battleMap.width}}" height="${{battleMap.height}}" fill="url(#bf-grid)" opacity=".8"></rect>${{renderBoardRuler(battleMap)}}${{deploymentZones}}${{terrain}}${{objectives}}${{overlays}}${{units}}</svg><div class="battle-hover-card" id="battle-hover-card" data-testid="battle-hover-card" aria-hidden="true"></div></div><div class="small">Phase: ${{escapeHtml(titleCase(battleState.phase || "movement"))}} | Score: Red ${{battleState.score?.red || 0}} | Blue ${{battleState.score?.blue || 0}}. Drag unit blobs to adjust the current state before asking the AI.</div>`;
    }}

    function renderBoardRuler(battleMap) {{
      const width = Number(battleMap.width || 44);
      const height = Number(battleMap.height || 60);
      const xMarks = rulerMarks(width);
      const yMarks = rulerMarks(height);
      const xTicks = xMarks.map((mark) => {{
        const x = clamp(mark, 1.15, width - 1.15);
        return `<line class="bf-ruler-line" x1="${{mark}}" y1="0" x2="${{mark}}" y2="1.05"></line><text class="bf-ruler-text" x="${{x}}" y="2.25">${{compactNumber(mark)}}"</text>`;
      }}).join("");
      const yTicks = yMarks.map((mark) => {{
        const y = clamp(mark, 1.2, height - 1.2);
        return `<line class="bf-ruler-line" x1="0" y1="${{mark}}" x2="1.05" y2="${{mark}}"></line><text class="bf-ruler-text" x="2.25" y="${{y}}">${{compactNumber(mark)}}"</text>`;
      }}).join("");
      const scaleX1 = Math.max(2, width - 8);
      const scaleX2 = Math.max(scaleX1 + 1, width - 2);
      const scaleY = Math.max(2, height - 2);
      return `<g class="bf-board-ruler" aria-label="Board measurement ruler">${{xTicks}}${{yTicks}}<line class="bf-ruler-scale" x1="${{scaleX1}}" y1="${{scaleY}}" x2="${{scaleX2}}" y2="${{scaleY}}"></line><line class="bf-ruler-scale" x1="${{scaleX1}}" y1="${{scaleY - .55}}" x2="${{scaleX1}}" y2="${{scaleY + .55}}"></line><line class="bf-ruler-scale" x1="${{scaleX2}}" y1="${{scaleY - .55}}" x2="${{scaleX2}}" y2="${{scaleY + .55}}"></line><text class="bf-ruler-text" x="${{(scaleX1 + scaleX2) / 2}}" y="${{scaleY - 1.15}}">6" scale</text></g>`;
    }}

    function rulerMarks(size) {{
      const marks = [0];
      for (let mark = 12; mark < Number(size || 0); mark += 12) marks.push(mark);
      if (!marks.includes(Number(size))) marks.push(Number(size));
      return marks;
    }}

    function clamp(value, min, max) {{
      return Math.max(min, Math.min(max, Number(value)));
    }}

    function renderTerrainFeature(feature) {{
      const x = Number(feature.x || 0);
      const y = Number(feature.y || 0);
      const width = Number(feature.width || 0);
      const height = Number(feature.height || 0);
      const cx = x + width / 2;
      const cy = y + height / 2;
      const shape = String(feature.shape || "rectangle").toLowerCase();
      const title = terrainTitle(feature);
      let shapeHtml = "";
      if (shape === "ellipse" || shape === "oval" || shape === "circle") {{
        shapeHtml = `<ellipse class="bf-terrain ${{escapeHtml(feature.type)}}" cx="${{cx}}" cy="${{cy}}" rx="${{width / 2}}" ry="${{height / 2}}" data-hover-text="${{title}}"></ellipse>`;
      }} else if (shape === "diamond") {{
        shapeHtml = `<polygon class="bf-terrain ${{escapeHtml(feature.type)}}" points="${{cx}},${{y}} ${{x + width}},${{cy}} ${{cx}},${{y + height}} ${{x}},${{cy}}" data-hover-text="${{title}}"></polygon>`;
      }} else {{
        shapeHtml = `<rect class="bf-terrain ${{escapeHtml(feature.type)}}" x="${{x}}" y="${{y}}" width="${{width}}" height="${{height}}" data-hover-text="${{title}}"></rect>`;
      }}
      return `<g class="bf-terrain-feature" data-terrain-id="${{escapeHtml(feature.id || "")}}">${{shapeHtml}}<text class="bf-terrain-label" x="${{cx}}" y="${{cy}}">${{escapeHtml(terrainShortLabel(feature))}}</text></g>`;
    }}

    function terrainTitle(feature) {{
      return escapeHtml(terrainTooltip(feature));
    }}

    function terrainTooltip(feature) {{
      const parts = [
        feature.name || "Terrain",
        terrainTypeLabel(feature.type),
        `${{Number(feature.stories || 1)}} storey${{Number(feature.stories || 1) === 1 ? "" : "s"}}`,
        feature.grants_cover ? "grants cover" : "no cover",
        feature.blocks_line_of_sight ? "blocks LOS" : "does not block LOS",
        Number(feature.movement_penalty || 0) ? `-${{fmt(feature.movement_penalty)}}" movement` : "no movement penalty"
      ];
      return parts.join("\\n");
    }}

    function objectiveTooltip(objective, index) {{
      const vp = objective.vp ?? objective.points ?? 0;
      return [
        objectiveDisplayName(objective, index),
        `Label ${{battleObjectiveLabel(objective, index)}}`,
        `Radius ${{compactNumber(objective.radius || 0)}}"`,
        `VP ${{compactNumber(vp)}}`,
        `Position x ${{fmt(objective.x)}}, y ${{fmt(objective.y)}}`
      ].join("\\n");
    }}

    function terrainShortLabel(feature) {{
      const type = terrainTypeLabel(feature.type).split(/\\s+/)[0];
      const stories = Number(feature.stories || 1);
      return `${{type}}${{stories > 1 ? ` ${{stories}}S` : ""}}`;
    }}

    function terrainTypeLabel(type) {{
      const value = String(type || "terrain").toLowerCase();
      if (value === "ruin") return "Ruin";
      if (value === "woods" || value === "forest") return "Woods";
      if (value === "crater") return "Crater";
      if (value === "barricade") return "Barricade";
      return titleCase(value);
    }}

    function renderTerrainLegend(battleMap) {{
      return (battleMap.terrain || []).map((feature) => {{
        const type = String(feature.type || "terrain").toLowerCase();
        const label = [
          feature.name || terrainTypeLabel(type),
          `${{terrainTypeLabel(type)}} ${{terrainShapeLabel(feature.shape)}}`,
          `${{Number(feature.stories || 1)}} storey${{Number(feature.stories || 1) === 1 ? "" : "s"}}`,
          terrainRulesLabel(feature)
        ].filter(Boolean).join(": ");
        return `<span title="${{terrainTitle(feature)}}"><i class="legend-swatch ${{escapeHtml(type)}}"></i><span class="legend-text">${{escapeHtml(label)}}</span></span>`;
      }}).join("");
    }}

    function renderObjectiveLegend(battleMap) {{
      return (battleMap.objectives || []).map((objective, index) => {{
        const vp = objective.vp ?? objective.points ?? 0;
        const label = [
          `${{battleObjectiveLabel(objective, index)}}: ${{objectiveDisplayName(objective, index)}}`,
          `${{compactNumber(objective.radius || 0)}}" radius`,
          `${{compactNumber(vp)}} VP`
        ].join(": ");
        return `<span title="${{escapeHtml(objectiveTooltip(objective, index))}}"><i class="legend-swatch objective"></i><span class="legend-text">${{escapeHtml(label)}}</span></span>`;
      }}).join("");
    }}

    function objectiveDisplayName(objective, index) {{
      const name = String((objective && objective.name) || `Objective ${{index + 1}}`).trim();
      return name.toLowerCase().includes("objective") ? name : `${{name}} objective`;
    }}

    function terrainShapeLabel(shape) {{
      const value = String(shape || "rectangle").toLowerCase();
      if (value === "ellipse" || value === "oval") return "oval";
      if (value === "circle") return "circle";
      if (value === "diamond") return "diamond";
      return "rectangle";
    }}

    function terrainRulesLabel(feature) {{
      const rules = [
        feature.grants_cover ? "cover" : "no cover",
        feature.blocks_line_of_sight ? "blocks LOS" : "open LOS",
        Number(feature.movement_penalty || 0) ? `-${{fmt(feature.movement_penalty)}}" move` : "normal move"
      ];
      return rules.join(", ");
    }}

    function battleObjectiveLabel(objective, index) {{
      const name = String(objective && objective.name || "").toLowerCase();
      if (name.includes("red")) return "R";
      if (name.includes("blue")) return "B";
      if (name.includes("west")) return "W";
      if (name.includes("east")) return "E";
      if (name.includes("centre") || name.includes("center")) return "C";
      return String(index + 1);
    }}

    function renderBattleOverlays(battleState) {{
      if (!battleState || !state.battlefield.selectedInstanceId) return "";
      const selected = battleUnitByInstance(state.battlefield.selectedInstanceId);
      if (!selected) return "";
      const detail = state.battlefield.selectedUnitDetail || state.units.find((row) => row.id === selected.unit_id) || {{}};
      const move = Math.max(1, Number(detail.move || 6));
      const nearestEnemy = nearestBattleUnit(selected, (battleState.units || []).filter((row) => row.side !== selected.side && row.models_remaining > 0));
      const nearestObjective = nearestBattleObjective(battleState, selected);
      return `<circle class="bf-move-radius" cx="${{selected.x}}" cy="${{selected.y}}" r="${{move}}"><title>${{escapeHtml(selected.name)}} move radius: ${{fmt(move)}}"</title></circle>${{nearestEnemy ? `<line class="bf-target-line" x1="${{selected.x}}" y1="${{selected.y}}" x2="${{nearestEnemy.x}}" y2="${{nearestEnemy.y}}"><title>Nearest enemy: ${{escapeHtml(nearestEnemy.name)}} at ${{fmt(nearestEnemy.distance)}}"</title></line>` : ""}}${{nearestObjective ? `<line class="bf-objective-line" x1="${{selected.x}}" y1="${{selected.y}}" x2="${{nearestObjective.x}}" y2="${{nearestObjective.y}}"><title>Nearest objective: ${{escapeHtml(nearestObjective.name)}}</title></line>` : ""}}`;
    }}

    function renderBattlePlan(plan) {{
      const actions = (plan && plan.actions) || [];
      if (!actions.length) return `<div class="empty">No AI actions available yet.</div>`;
      return `<div class="battle-log" data-testid="battle-ai-plan">${{actions.map((action, index) => `<div class="battle-log-entry ${{escapeHtml(action.side)}}"><b>${{escapeHtml(action.type)}}: ${{escapeHtml(unitNameByInstance(action.actor_id))}}</b><br>${{escapeHtml(action.reason)}}<br><span class="small">Phase ${{escapeHtml(titleCase(battlefieldPhase()))}} | Score ${{fmt(action.score)}} | Damage ${{fmt(action.expected_damage)}} | Return ${{fmt(action.expected_return_damage)}}</span><div><button class="tertiary battle-resolve-action" type="button" data-action-index="${{index}}">Resolve this action</button></div></div>`).join("")}}</div>`;
    }}

    function renderManualBattleActions() {{
      if (!state.battlefield.selectedInstanceId) return "";
      const actions = state.battlefield.manualActions || [];
      const unavailable = state.battlefield.manualUnavailableActions || [];
      const unavailableHtml = renderUnavailableBattleActions(unavailable);
      if (!actions.length) return `${{unavailableHtml}}<div class="empty">${{escapeHtml(state.battlefield.manualActionNotice || "No selected-unit actions available in this phase.")}}</div>`;
      return `<div class="battle-log selected-actions-log">${{actions.map((action, index) => `<div class="battle-log-entry ${{escapeHtml(action.side)}}"><b>${{escapeHtml(action.type)}}${{action.target_id ? `: ${{escapeHtml(unitNameByInstance(action.target_id))}}` : ""}}</b><br>${{escapeHtml(action.reason || "Manual action")}}<br><span class="small">Phase ${{escapeHtml(titleCase(battlefieldPhase()))}} | Score ${{fmt(action.score)}} | Damage ${{fmt(action.expected_damage)}} | Return ${{fmt(action.expected_return_damage)}}</span><div><button class="tertiary battle-resolve-manual-action" type="button" data-action-index="${{index}}">Resolve selected action</button></div></div>`).join("")}}</div>${{unavailableHtml}}`;
    }}

    function renderUnavailableBattleActions(rows) {{
      if (!rows || !rows.length) return "";
      return `<div class="battle-log selected-actions-log" data-testid="battle-unavailable-actions">${{rows.map((row) => `<div class="battle-log-entry"><b>Unavailable: ${{escapeHtml(row.type || "action")}}</b><br>${{escapeHtml(row.reason || "This action is not currently legal.")}}<br><span class="small">Phase ${{escapeHtml(titleCase(row.phase || battlefieldPhase()))}}</span></div>`).join("")}}</div>`;
    }}

    function renderSelectedBattleUnit(battleState) {{
      if (!battleState || !state.battlefield.selectedInstanceId) return `<div class="empty">Select a unit blob on the board.</div>`;
      const unit = battleUnitByInstance(state.battlefield.selectedInstanceId);
      if (!unit) return `<div class="empty">Selected unit is no longer on the board.</div>`;
      const detail = state.battlefield.selectedUnitDetail;
      const profile = detail || battlefieldAvailableUnits().find((row) => row.id === unit.unit_id) || {{}};
      const nearestEnemy = nearestBattleUnit(unit, (battleState.units || []).filter((row) => row.side !== unit.side && row.models_remaining > 0));
      const nearestObjective = nearestBattleObjective(battleState, unit);
      const weapons = (profile.weapons || []).slice(0, 8).map((weapon) => `<div class="inspector-weapon"><b>${{escapeHtml(weapon.name)}}</b><br>${{escapeHtml(weapon.type || "")}}${{weapon.range_inches ? ` | R${{escapeHtml(weapon.range_inches)}}"` : ""}} | A${{escapeHtml(weapon.attacks || "?")}} | ${{escapeHtml(weapon.skillLabel || weapon.skill || "?")}} | S${{escapeHtml(weapon.strength || "?")}} | AP${{escapeHtml(weapon.ap ?? 0)}} | D${{escapeHtml(weapon.damage || "?")}}</div>`).join("");
      const footprintSource = battleFootprintSourceLabel(profile);
      return `<div class="unit-inspector" data-testid="battle-unit-inspector"><div><b>${{escapeHtml(unit.name)}}</b> <span class="small">${{escapeHtml(unit.side)}}</span></div><div class="small">${{escapeHtml(profile.faction || "No faction")}} | T${{escapeHtml(profile.toughness || "?")}} W${{escapeHtml(profile.wounds || "?")}} Sv ${{escapeHtml(profile.saveLabel || profile.save || "?")}} | OC ${{escapeHtml(profile.objectiveControl ?? profile.objective_control ?? "?")}} | ${{escapeHtml(profile.points || 0)}} pts</div><div class="small">Board: x ${{fmt(unit.x)}}, y ${{fmt(unit.y)}} | Models ${{escapeHtml(unit.models_remaining)}} | Wounds remaining ${{fmt(unit.wounds_remaining)}}</div><div class="small">${{escapeHtml(battleFootprintLabel(unit, profile))}}</div>${{footprintSource ? `<div class="small">${{escapeHtml(footprintSource)}}</div>` : ""}}<div class="small">Nearest enemy: ${{nearestEnemy ? `${{escapeHtml(nearestEnemy.name)}} at ${{fmt(nearestEnemy.distance)}}"` : "none"}}</div><div class="small">Nearest objective: ${{nearestObjective ? `${{escapeHtml(nearestObjective.name)}} at ${{fmt(distance(unit.x, unit.y, nearestObjective.x, nearestObjective.y))}}"` : "none"}}</div><div class="inspector-weapons">${{weapons || `<div class="empty">Weapon details not loaded.</div>`}}</div></div>`;
    }}

    function renderBattleLog(battleState, replay) {{
      const entries = replay ? replay.map((row) => row.outcome) : ((battleState && battleState.log) || []);
      if (!entries.length) return `<div class="empty">No actions resolved yet.</div>`;
      return `<div class="battle-log battle-history-log">${{entries.slice(-12).reverse().map((entry) => {{
        const details = [battleDamageText(entry), battleScoreText(entry), battleContextText(entry)].filter(Boolean);
        return `<div class="battle-log-entry ${{escapeHtml(entry.side || "")}}"><b>Turn ${{entry.turn || "?"}}: ${{escapeHtml(entry.actor || entry.side || "Battlefield")}} ${{escapeHtml(entry.action || "")}}</b><br>${{escapeHtml(entry.reason || entry.detail || "")}}${{details.length ? `<br><span class="small">${{details.map(escapeHtml).join(" | ")}}</span>` : ""}}</div>`;
      }}).join("")}}</div>`;
    }}

    function battleDamageText(entry) {{
      if (!hasNumber(entry.damage) && !hasNumber(entry.points_removed)) return "";
      const parts = [];
      if (hasNumber(entry.damage)) parts.push(`Damage ${{fmt(entry.damage)}}`);
      if (hasNumber(entry.points_removed)) parts.push(`Points removed ${{fmt(entry.points_removed)}}`);
      return parts.join(" | ");
    }}

    function battleScoreText(entry) {{
      const delta = entry.score_delta || {{}};
      const scoreParts = Object.entries(delta)
        .filter(([, value]) => Number(value) !== 0)
        .map(([side, value]) => `Score ${{titleCase(side)}} +${{fmt(value)}}`);
      const objectives = (entry.objectives || []).filter(Boolean);
      if (objectives.length) scoreParts.push(`Objectives ${{objectives.join(", ")}}`);
      return scoreParts.join(" | ");
    }}

    function battleContextText(entry) {{
      const context = entry.context || {{}};
      const parts = [];
      if (hasNumber(context.charge_probability)) parts.push(`Charge ${{Math.round(Number(context.charge_probability) * 100)}}%`);
      if (hasNumber(context.expected_followup_fight_damage)) parts.push(`Follow-up fight ${{fmt(context.expected_followup_fight_damage)}} expected damage`);
      if (hasNumber(context.attack_distance) && hasNumber(context.weapon_range)) parts.push(`${{context.attack_in_range === false ? "Out of range" : "Range"}} ${{fmt(context.attack_distance)}}/${{fmt(context.weapon_range)}}"`);
      if (context.line_of_sight_blocked) {{
        const terrain = (context.intervening_terrain || []).join(", ");
        parts.push(`LOS obscured${{terrain ? ` by ${{terrain}}` : ""}}`);
      }}
      if ((context.cover_sources || []).length) parts.push(`Cover ${{context.cover_sources.join(", ")}}`);
      if (hasNumber(context.damage_multiplier) && Number(context.damage_multiplier) !== 1) parts.push(`Damage multiplier x${{fmt(context.damage_multiplier)}}`);
      return parts.join(" | ");
    }}

    function titleCase(value) {{
      const text = String(value || "");
      return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
    }}

    function battleBaseLabel(profile = {{}}) {{
      const width = Number(profile.baseWidthMm ?? profile.base_width_mm);
      const depth = Number(profile.baseDepthMm ?? profile.base_depth_mm);
      const shape = String(profile.baseShape ?? profile.base_shape ?? "").replaceAll("_", " ");
      const type = String(profile.baseType ?? profile.base_type ?? "").replaceAll("_", " ");
      if (Number.isFinite(width) && width > 0) {{
        const size = Number.isFinite(depth) && depth > 0 && Math.abs(depth - width) > 0.1
          ? `${{fmt(width)}}x${{fmt(depth)}}mm`
          : `${{fmt(width)}}mm`;
        return `Base ${{size}}${{shape ? ` ${{shape}}` : ""}}`;
      }}
      const estimate = battleBaseEstimate(profile);
      if (type && estimate.label) return `Base ${{titleCase(type)}} (${{estimate.label}})`;
      if (type) return `Base ${{titleCase(type)}}`;
      return "Base unknown";
    }}

    function battleFootprintLabel(unit, profile = {{}}) {{
      return `Footprint ${{fmt(unit.radius)}}" | ${{battleBaseLabel(profile)}}`;
    }}

    function battleFootprintSourceLabel(profile = {{}}) {{
      const status = profile.footprintStatus ?? profile.footprint_status;
      const source = profile.footprintSource ?? profile.footprint_source;
      const confidence = profile.footprintConfidence ?? profile.footprint_confidence;
      const parts = [];
      if (status) parts.push(String(status));
      if (source) parts.push(String(source));
      if (hasNumber(confidence)) parts.push(`confidence ${{fmt(confidence)}}`);
      const estimate = battleBaseEstimate(profile);
      if (estimate.label) parts.push(estimate.label);
      return parts.length ? `Footprint source: ${{parts.join(", ")}}` : "";
    }}

    function renderBattleValidation(validation) {{
      if (!validation) return "";
      return `<div class="battlefield-panels">${{["red", "blue", "state"].map((key) => {{ const row = validation[key] || {{}}; const totals = key === "state" ? "" : `<div class="small">${{escapeHtml(row.unit_count || 0)}} units | ${{escapeHtml(row.points || 0)}} pts</div>`; const errors = (row.errors || []).map((item) => `<li><b>Error:</b> ${{escapeHtml(item)}}</li>`).join(""); const warnings = (row.warnings || []).map((item) => `<li><b>Warning:</b> ${{escapeHtml(item)}}</li>`).join(""); return `<div class="battle-panel"><h3>${{escapeHtml(key)}} validation</h3><div class="small">${{row.ok ? "Valid" : "Needs attention"}}</div>${{totals}}<ul>${{errors}}${{warnings}}</ul></div>`; }}).join("")}}</div>`;
    }}

    function wireBattlefieldEvents() {{
      el("battle-template").addEventListener("change", (event) => {{ state.battlefield.selectedTemplate = event.target.value; state.battlefield.state = null; state.battlefield.plan = null; resetBattlefieldManualActions(); }});
      document.querySelectorAll(".battle-army-faction").forEach((select) => {{
        select.addEventListener("change", (event) => {{
          updateBattlefieldArmyFaction(event.target.dataset.side, event.target.value).catch(showBattlefieldError);
        }});
      }});
      document.querySelectorAll(".battle-army-unit").forEach((select) => {{
        const rows = battlefieldArmyRows(select.dataset.side);
        const row = rows[Number(select.dataset.index)] || {{}};
        select.value = row.unitId || "";
        select.addEventListener("change", (event) => {{
          updateBattlefieldArmyRow(event.target.dataset.side, Number(event.target.dataset.index), {{ unitId: event.target.value }});
        }});
      }});
      document.querySelectorAll(".battle-army-count").forEach((input) => {{
        input.addEventListener("change", (event) => {{
          updateBattlefieldArmyRow(event.target.dataset.side, Number(event.target.dataset.index), {{ count: Math.max(1, Number(event.target.value || 1)) }});
        }});
      }});
      document.querySelectorAll(".army-remove").forEach((button) => {{
        button.addEventListener("click", () => removeBattlefieldArmyRow(button.dataset.side, Number(button.dataset.index)));
      }});
      document.querySelectorAll(".battle-add-unit").forEach((button) => {{
        button.addEventListener("click", () => addBattlefieldArmyRow(button.dataset.side));
      }});
      el("battle-generate").addEventListener("click", () => battlefieldGenerate().catch(showBattlefieldError));
      el("battle-redeploy").addEventListener("click", () => battlefieldRedeploy().catch(showBattlefieldError));
      el("battle-next-phase").addEventListener("click", () => battlefieldNextPhase().catch(showBattlefieldError));
      el("battle-phase").addEventListener("change", (event) => setBattlefieldPhase(event.target.value).catch(showBattlefieldError));
      el("battle-validate").addEventListener("click", () => battlefieldValidate().catch(showBattlefieldError));
      el("battle-suggest").addEventListener("click", () => battlefieldSuggest().catch(showBattlefieldError));
      el("battle-autoplay").addEventListener("click", () => battlefieldAutoplay().catch(showBattlefieldError));
      el("battle-autoplay-battle").addEventListener("click", () => battlefieldAutoplayBattle().catch(showBattlefieldError));
      el("battle-autoplay-turns").addEventListener("change", () => battleAutoplayTurnCount());
      document.querySelectorAll(".battle-resolve-action").forEach((button) => {{
        button.addEventListener("click", () => battlefieldResolvePlannedAction(button.dataset.actionIndex).catch(showBattlefieldError));
      }});
      document.querySelectorAll(".battle-resolve-manual-action").forEach((button) => {{
        button.addEventListener("click", () => battlefieldResolveManualAction(button.dataset.actionIndex).catch(showBattlefieldError));
      }});
      el("battle-export").addEventListener("click", battlefieldExportJson);
      el("battle-export-armies").addEventListener("click", battlefieldExportArmiesJson);
      el("battle-export-map").addEventListener("click", battlefieldExportMapJson);
      el("battle-export-replay").addEventListener("click", battlefieldExportReplayJson);
      el("battle-import").addEventListener("click", () => el("battle-import-file").click());
      el("battle-import-file").addEventListener("change", (event) => {{
        const file = event.target.files && event.target.files[0];
        if (file) battlefieldImportJson(file).catch(showBattlefieldError);
        event.target.value = "";
      }});
      wireBattleBoardDrag();
    }}

    async function updateBattlefieldArmyFaction(side, faction) {{
      if (!state.battlefield.armyFactions) state.battlefield.armyFactions = {{ red: "", blue: "" }};
      state.battlefield.armyFactions[side] = faction || "";
      await loadBattlefieldFactionUnits(faction || "");
      state.battlefield.state = null;
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      renderBattlefield();
    }}

    function updateBattlefieldArmyRow(side, index, patch) {{
      const rows = battlefieldArmyRows(side);
      rows[index] = {{ ...(rows[index] || {{ unitId: "", count: 1 }}), ...patch }};
      rows[index].count = Math.max(1, Number(rows[index].count || 1));
      state.battlefield.state = null;
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      syncLegacyBattlefieldSelections();
      renderBattlefield();
    }}

    function addBattlefieldArmyRow(side) {{
      const rows = battlefieldArmyRows(side);
      const units = filteredBattlefieldUnits(side);
      const fallback = units.find((unit) => !rows.some((row) => row.unitId === unit.id)) || units[0] || battlefieldAvailableUnits()[0];
      rows.push({{ unitId: fallback ? fallback.id : "", count: 1 }});
      state.battlefield.state = null;
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      syncLegacyBattlefieldSelections();
      renderBattlefield();
    }}

    function removeBattlefieldArmyRow(side, index) {{
      const rows = battlefieldArmyRows(side);
      rows.splice(index, 1);
      if (!rows.length) rows.push({{ unitId: "", count: 1 }});
      state.battlefield.state = null;
      state.battlefield.plan = null;
      resetBattlefieldManualActions();
      syncLegacyBattlefieldSelections();
      renderBattlefield();
    }}

    function wireBattleBoardDrag() {{
      const board = el("battle-board");
      if (!board) return;
      board.querySelectorAll(".bf-terrain").forEach((node) => {{
        node.addEventListener("pointerenter", (event) => {{ showBattleHoverText(node.dataset.hoverText || "Terrain", event); }});
        node.addEventListener("pointermove", (event) => {{ showBattleHoverText(node.dataset.hoverText || "Terrain", event); }});
        node.addEventListener("pointerleave", hideBattleHoverCard);
      }});
      board.querySelectorAll(".bf-objective").forEach((node) => {{
        node.addEventListener("pointerenter", (event) => {{ showBattleHoverText(node.dataset.hoverText || "Objective", event); }});
        node.addEventListener("pointermove", (event) => {{ showBattleHoverText(node.dataset.hoverText || "Objective", event); }});
        node.addEventListener("pointerleave", hideBattleHoverCard);
      }});
      board.querySelectorAll(".bf-unit").forEach((node) => {{
        node.addEventListener("pointerenter", (event) => {{ showBattleHoverCard(node.dataset.unitId, event); }});
        node.addEventListener("pointerdown", (event) => {{ event.preventDefault(); node.setPointerCapture(event.pointerId); state.battlefield.dragging = node.dataset.unitId; showBattleHoverCard(node.dataset.unitId, event); }});
        node.addEventListener("click", () => {{
          selectBattleUnit(node.dataset.unitId).catch(showBattlefieldError);
        }});
        node.addEventListener("pointermove", (event) => {{
          showBattleHoverCard(node.dataset.unitId, event);
          if (state.battlefield.dragging !== node.dataset.unitId) return;
          const point = svgPoint(board, event.clientX, event.clientY);
          updateBattleUnitPosition(node.dataset.unitId, point.x, point.y);
          const unit = battleUnitByInstance(node.dataset.unitId);
          node.setAttribute("cx", unit.x);
          node.setAttribute("cy", unit.y);
          const label = node.parentElement.querySelector(".bf-label");
          const nameLabel = node.parentElement.querySelector(".bf-unit-name-label");
          if (label) {{ label.setAttribute("x", unit.x); label.setAttribute("y", unit.y); }}
          if (nameLabel) {{ nameLabel.setAttribute("x", unit.x); nameLabel.setAttribute("y", Number(unit.y || 0) + Number(unit.radius || 1) + 1.5); }}
        }});
        node.addEventListener("pointerleave", () => {{ if (state.battlefield.dragging !== node.dataset.unitId) hideBattleHoverCard(); }});
        node.addEventListener("pointerup", () => {{ state.battlefield.dragging = null; hideBattleHoverCard(); state.battlefield.plan = null; resetBattlefieldManualActions(); refreshBattlefieldSelectedActions().then(() => renderBattlefield()).catch(showBattlefieldError); }});
      }});
    }}

    function showBattleHoverCard(instanceId, event) {{
      const card = el("battle-hover-card");
      const board = el("battle-board");
      if (!card || !board || !state.battlefield.state) return;
      const unit = battleUnitByInstance(instanceId);
      if (!unit) return;
      const profile = battleUnitProfile(unit);
      card.textContent = battleUnitTooltip(unit, profile, state.battlefield.state);
      showPositionedBattleHoverCard(card, board, event);
    }}

    function showBattleHoverText(text, event) {{
      const card = el("battle-hover-card");
      const board = el("battle-board");
      if (!card || !board) return;
      card.textContent = text;
      showPositionedBattleHoverCard(card, board, event);
    }}

    function showPositionedBattleHoverCard(card, board, event) {{
      card.classList.add("visible");
      card.setAttribute("aria-hidden", "false");
      positionBattleHoverCard(card, board, event);
    }}

    function positionBattleHoverCard(card, board, event) {{
      const wrap = board.closest(".battlefield-board-wrap");
      if (!wrap) return;
      const bounds = wrap.getBoundingClientRect();
      const x = Math.min(bounds.width - card.offsetWidth - 12, Math.max(12, event.clientX - bounds.left + 14));
      const y = Math.min(bounds.height - card.offsetHeight - 12, Math.max(12, event.clientY - bounds.top + 14));
      card.style.left = `${{x}}px`;
      card.style.top = `${{y}}px`;
    }}

    function hideBattleHoverCard() {{
      const card = el("battle-hover-card");
      if (!card) return;
      card.classList.remove("visible");
      card.setAttribute("aria-hidden", "true");
    }}

    async function selectBattleUnit(instanceId) {{
      const unit = battleUnitByInstance(instanceId);
      if (!unit) return;
      state.battlefield.selectedInstanceId = instanceId;
      state.battlefield.selectedUnitDetail = await loadUnitDetailById(unit.unit_id, unit.name);
      await battlefieldLoadSelectedActions();
      renderBattlefield();
    }}

    function svgPoint(svg, clientX, clientY) {{
      const width = Number(svg.dataset.width || 44);
      const height = Number(svg.dataset.height || 60);
      const ctm = svg.getScreenCTM?.();
      if (ctm) {{
        const point = svg.createSVGPoint();
        point.x = clientX;
        point.y = clientY;
        const mapped = point.matrixTransform(ctm.inverse());
        return {{ x: Math.max(0, Math.min(width, mapped.x)), y: Math.max(0, Math.min(height, mapped.y)) }};
      }}
      const rect = svg.getBoundingClientRect();
      const scale = Math.min(rect.width / width, rect.height / height);
      const renderedWidth = width * scale;
      const renderedHeight = height * scale;
      const offsetX = (rect.width - renderedWidth) / 2;
      const offsetY = (rect.height - renderedHeight) / 2;
      return {{ x: Math.max(0, Math.min(width, (clientX - rect.left - offsetX) / scale)), y: Math.max(0, Math.min(height, (clientY - rect.top - offsetY) / scale)) }};
    }}

    function updateBattleUnitPosition(instanceId, x, y) {{
      const unit = battleUnitByInstance(instanceId);
      const battleMap = state.battlefield.state && state.battlefield.state.map;
      if (!unit || !battleMap) return;
      unit.x = Math.max(unit.radius, Math.min(Number(battleMap.width) - unit.radius, Number(x)));
      unit.y = Math.max(unit.radius, Math.min(Number(battleMap.height) - unit.radius, Number(y)));
    }}

    function battleUnitByInstance(instanceId) {{
      return state.battlefield.state && (state.battlefield.state.units || []).find((unit) => unit.instance_id === instanceId);
    }}

    function unitNameByInstance(instanceId) {{
      const unit = battleUnitByInstance(instanceId);
      return unit ? unit.name : instanceId;
    }}

    function battleUnitProfile(unit) {{
      if (!unit) return {{}};
      return battlefieldAvailableUnits().find((row) => row.id === unit.unit_id)
        || state.units.find((row) => row.id === unit.unit_id)
        || {{}};
    }}

    function compactNumber(value) {{
      if (!hasNumber(value)) return "?";
      const number = Number(value);
      return Number.isInteger(number) ? String(number) : number.toFixed(1);
    }}

    function battleUnitStatText(unit) {{
      if ((unit.status_flags || []).includes("destroyed") || Number(unit.models_remaining || 0) <= 0) return "OUT";
      return `M${{compactNumber(unit.models_remaining)}} W${{compactNumber(unit.wounds_remaining)}}`;
    }}

    function battleUnitBadgeText(unit) {{
      const models = Number(unit.models_remaining || 0);
      if (models > 99) return "99+";
      return compactNumber(models);
    }}

    function battleUnitTooltip(unit, profile = {{}}, battleState = null) {{
      const objectiveControl = profile.objectiveControl ?? profile.objective_control ?? "?";
      const points = hasNumber(profile.points) ? `${{profile.points}} pts` : "points unknown";
      const faction = profile.faction || "No faction";
      const status = (unit.status_flags || []).length ? (unit.status_flags || []).join(", ") : "active";
      const nearestEnemy = battleState ? nearestBattleUnit(unit, (battleState.units || []).filter((row) => row.side !== unit.side && row.models_remaining > 0)) : null;
      const nearestObjective = battleState ? nearestBattleObjective(battleState, unit) : null;
      const parts = [
        `${{unit.name}} (${{titleCase(unit.side)}})`,
        `${{faction}} | ${{points}}`,
        `Models ${{compactNumber(unit.models_remaining)}} | wounds remaining ${{compactNumber(unit.wounds_remaining)}} | status ${{status}}`,
        `T${{profile.toughness || "?"}} W${{profile.wounds || "?"}} Sv ${{profile.saveLabel || profile.save || "?"}} OC ${{objectiveControl}}`,
        `Position x ${{fmt(unit.x)}}, y ${{fmt(unit.y)}} | ${{battleFootprintLabel(unit, profile)}}`,
      ];
      const footprintSource = battleFootprintSourceLabel(profile);
      if (footprintSource) parts.push(footprintSource);
      if (nearestEnemy) parts.push(`Nearest enemy: ${{nearestEnemy.name}} at ${{fmt(nearestEnemy.distance)}}"`);
      if (nearestObjective) parts.push(`Nearest objective: ${{nearestObjective.name}} at ${{fmt(distance(unit.x, unit.y, nearestObjective.x, nearestObjective.y))}}"`);
      return parts.join("\\n");
    }}

    function nearestBattleUnit(unit, candidates) {{
      const nearest = candidates
        .map((candidate) => ({{ ...candidate, distance: distance(unit.x, unit.y, candidate.x, candidate.y) }}))
        .sort((left, right) => left.distance - right.distance)[0];
      return nearest || null;
    }}

    function unitLabelById(unitId) {{
      const unit = battlefieldAvailableUnits().find((row) => row.id === unitId);
      if (!unit) return "No unit selected.";
      return [unit.faction, unit.points ? `${{unit.points}} pts` : "", unit.modelsMin ? `${{unit.modelsMin}}-${{unit.modelsMax || unit.modelsMin}} models` : ""].filter(Boolean).join(" | ");
    }}

    function armySummaryText(rows) {{
      const selectedRows = rows.filter((row) => row.unitId);
      const unitTotal = selectedRows.reduce((sum, row) => sum + Math.max(1, Number(row.count || 1)), 0);
      const points = selectedRows.reduce((sum, row) => {{
        const unit = battlefieldAvailableUnits().find((candidate) => candidate.id === row.unitId);
        return sum + (unit && unit.points ? Number(unit.points) * Math.max(1, Number(row.count || 1)) : 0);
      }}, 0);
      return `${{unitTotal}} battlefield units | ${{points}} pts before unsupported options`;
    }}

    function shortUnitLabel(name) {{
      return String(name || "Unit").split(/\\s+/).slice(0, 2).join(" ");
    }}

    function unitInitials(name) {{
      const words = String(name || "U").match(/[A-Za-z0-9]+/g) || ["U"];
      const significant = words.filter((word) => !["the", "of", "and"].includes(word.toLowerCase()));
      const picked = (significant.length ? significant : words).slice(0, 2);
      return picked.map((word) => word.charAt(0).toUpperCase()).join("") || "U";
    }}

    function battleLabelFontSize(unit) {{
      return Math.max(1.4, Math.min(2.4, Number(unit.radius || 2) * 0.7)).toFixed(2);
    }}

    function battleLabelWidth(unit) {{
      return Math.max(1.2, Number(unit.radius || 2) * 1.15).toFixed(2);
    }}

    function battleUnitNameLabelWidth(unit) {{
      return Math.max(3.5, Math.min(10, Number(unit.radius || 2) * 3.8)).toFixed(2);
    }}

    function battleUnitStatLabelWidth(unit) {{
      return Math.max(2.4, Math.min(5.8, Number(unit.radius || 2) * 1.95)).toFixed(2);
    }}

    function showBattlefieldError(error) {{
      el("error").textContent = error.message;
    }}

    function nearestBattleObjective(battleState, actor) {{
      return (battleState.map.objectives || []).slice().sort((left, right) => distance(actor.x, actor.y, left.x, left.y) - distance(actor.x, actor.y, right.x, right.y))[0] || null;
    }}

    function stepToward(x1, y1, x2, y2, maxDistance) {{
      const dist = distance(x1, y1, x2, y2);
      if (dist <= maxDistance || dist === 0) return {{ x: x2, y: y2 }};
      const ratio = maxDistance / dist;
      return {{ x: x1 + (x2 - x1) * ratio, y: y1 + (y2 - y1) * ratio }};
    }}

    function localMovementAllowance(battleMap, actor, profile) {{
      const base = Number(profile.move || 6);
      const penalties = (battleMap.terrain || [])
        .filter((feature) => feature.movement_penalty && actor.x >= feature.x - actor.radius && actor.x <= feature.x + feature.width + actor.radius && actor.y >= feature.y - actor.radius && actor.y <= feature.y + feature.height + actor.radius)
        .map((feature) => Number(feature.movement_penalty || 0));
      const penalty = penalties.length ? Math.max(...penalties) : 0;
      if (!penalty) return {{ allowance: base, assumptions: [] }};
      return {{ allowance: Math.max(1, base - penalty), assumptions: [`Terrain movement penalty: -${{penalty}}" from current terrain.`] }};
    }}

    function localObjectiveControl(actor, profile) {{
      return Math.max(0, Number(profile.objectiveControl || profile.objective_control || 1) * Math.max(0, Number(actor.models_remaining || 0)));
    }}

    function localControlledObjectivesForSide(battleState, side) {{
      return (battleState.map.objectives || []).filter((objective) => localObjectiveController(battleState, objective) === side);
    }}

    function localObjectiveController(battleState, objective) {{
      const control = {{ red: 0, blue: 0 }};
      for (const unit of (battleState.units || []).filter((row) => row.models_remaining > 0 && !(row.status_flags || []).includes("destroyed"))) {{
        if (distance(unit.x, unit.y, objective.x, objective.y) <= Number(objective.radius || 3) + Number(unit.radius || 0)) {{
          const profile = state.units.find((row) => row.id === unit.unit_id);
          control[unit.side] += profile ? localObjectiveControl(unit, profile) : 0;
        }}
      }}
      if (control.red === control.blue) return null;
      return control.red > control.blue ? "red" : "blue";
    }}

    function localScoringActorForObjectives(active, objectives) {{
      return [...active].sort((left, right) => {{
        const leftDistance = Math.min(...objectives.map((objective) => distance(left.x, left.y, objective.x, objective.y)));
        const rightDistance = Math.min(...objectives.map((objective) => distance(right.x, right.y, objective.x, objective.y)));
        return leftDistance - rightDistance || String(left.instance_id).localeCompare(String(right.instance_id));
      }})[0];
    }}

    function localSideScoredThisTurn(battleState, side) {{
      return (battleState.log || []).some((entry) => entry.turn === battleState.turn && entry.side === side && entry.action === "score" && Number((entry.score_delta || {{}})[side] || 0) > 0);
    }}

    function localStateValidationErrors(battleState) {{
      if (!battleState || typeof battleState !== "object") return ["Battle state must be an object."];
      const errors = localMapValidationErrors(battleState.map || {{}});
      const phase = String(battleState.phase || "").toLowerCase();
      if (!["movement", "shooting", "charge", "fight", "scoring", "battlefield_ai"].includes(phase)) {{
        errors.push(`Battle phase ${{battleState.phase}} is not supported.`);
      }}
      const turn = Number(battleState.turn);
      if (!Number.isInteger(turn) || turn < 1) errors.push("Battle turn must be a positive integer.");
      const activeSide = String(battleState.active_side || "").toLowerCase();
      if (!["red", "blue"].includes(activeSide)) {{
        errors.push(`Battle active side must be red or blue, not ${{battleState.active_side}}.`);
      }}
      const score = battleState.score;
      if (!score || typeof score !== "object" || Array.isArray(score)) {{
        errors.push("Battle score must include red and blue numeric values.");
      }} else {{
        for (const side of ["red", "blue"]) {{
          if (!(side in score)) {{
            errors.push(`Battle score is missing ${{side}}.`);
          }} else if (!Number.isFinite(Number(score[side]))) {{
            errors.push(`Battle score for ${{side}} must be numeric.`);
          }} else if (Number(score[side]) < 0) {{
            errors.push(`Battle score for ${{side}} cannot be negative.`);
          }}
        }}
      }}
      if (!Array.isArray(battleState.units)) errors.push("Battle state units must be a list.");
      const allUnits = Array.isArray(battleState.units) ? battleState.units : [];
      const units = allUnits.filter((unit) => unit.models_remaining > 0 && !(unit.status_flags || []).includes("destroyed"));
      const map = battleState.map || {{}};
      const width = Number(map.width || 0);
      const height = Number(map.height || 0);
      const knownUnitIds = new Set((state.units || []).map((unit) => unit.id));
      const seenIds = new Set();
      for (const unit of allUnits) {{
        const label = unit.name || unit.instance_id || unit.unit_id || "Unit";
        if (!unit.instance_id) errors.push(`${{label}} is missing a battlefield unit id.`);
        if (unit.instance_id && seenIds.has(unit.instance_id)) errors.push(`Duplicate battlefield unit id ${{unit.instance_id}}.`);
        seenIds.add(unit.instance_id);
        if (!knownUnitIds.has(unit.unit_id)) errors.push(`${{label}} has unknown unit id ${{unit.unit_id}}.`);
        if (!["red", "blue"].includes(unit.side)) errors.push(`${{label}} has invalid side ${{unit.side}}.`);
        if (Number(unit.radius || 0) <= 0) errors.push(`${{label}} must have a positive footprint radius.`);
      }}
      for (const unit of units) {{
        if (unit.x < unit.radius || unit.x > width - unit.radius || unit.y < unit.radius || unit.y > height - unit.radius) {{
          errors.push(`${{unit.name}} is outside the battlefield.`);
        }}
      }}
      for (let index = 0; index < units.length; index += 1) {{
        for (let otherIndex = index + 1; otherIndex < units.length; otherIndex += 1) {{
          if (localUnitsOverlap(units[index], units[otherIndex])) {{
            errors.push(`${{units[index].name}} overlaps ${{units[otherIndex].name}}; move one blob so footprints do not overlap.`);
          }}
        }}
      }}
      return errors;
    }}

    function localMapValidationErrors(battleMap) {{
      const errors = [];
      const width = Number(battleMap.width || 0);
      const height = Number(battleMap.height || 0);
      if (width <= 0 || height <= 0) errors.push("Battle map dimensions must be positive.");
      const zones = battleMap.deployment_zones || [];
      if (!zones.length) errors.push("Battle map must include deployment zones.");
      if (!zones.some((zone) => zone.side === "red")) errors.push("Battle map is missing a red deployment zone.");
      if (!zones.some((zone) => zone.side === "blue")) errors.push("Battle map is missing a blue deployment zone.");
      for (const zone of zones) {{
        const label = zone.id || `${{zone.side || "unknown"}} deployment zone`;
        const zoneWidth = Number(zone.width || 0);
        const zoneHeight = Number(zone.height || 0);
        if (zoneWidth <= 0 || zoneHeight <= 0) errors.push(`Deployment zone ${{label}} must have positive width and height.`);
        if (!["red", "blue"].includes(zone.side)) errors.push(`Deployment zone ${{label}} has invalid side ${{zone.side}}.`);
        if (!localRectInBounds(width, height, Number(zone.x || 0), Number(zone.y || 0), zoneWidth, zoneHeight)) errors.push(`Deployment zone ${{label}} is outside the battlefield.`);
      }}
      for (const feature of battleMap.terrain || []) {{
        const label = feature.name || feature.id || "terrain";
        const featureWidth = Number(feature.width || 0);
        const featureHeight = Number(feature.height || 0);
        if (featureWidth <= 0 || featureHeight <= 0) errors.push(`Terrain feature ${{label}} must have positive width and height.`);
        if (!localRectInBounds(width, height, Number(feature.x || 0), Number(feature.y || 0), featureWidth, featureHeight)) errors.push(`Terrain feature ${{label}} is outside the battlefield.`);
        if (Number(feature.movement_penalty || 0) < 0) errors.push(`Terrain feature ${{label}} has an invalid negative movement penalty.`);
        if (Number(feature.stories || 1) < 1) errors.push(`Terrain feature ${{label}} must have at least one storey.`);
      }}
      for (const objective of battleMap.objectives || []) {{
        const label = objective.name || objective.id || "objective";
        const radius = Number(objective.radius || 0);
        if (radius <= 0) errors.push(`Objective ${{label}} must have a positive radius.`);
        if (Number(objective.points || 0) < 0) errors.push(`Objective ${{label}} has invalid negative points.`);
        if (!localCircleInBounds(width, height, Number(objective.x || 0), Number(objective.y || 0), radius)) errors.push(`Objective ${{label}} is outside the battlefield.`);
      }}
      return errors;
    }}

    function localRectInBounds(boardWidth, boardHeight, x, y, width, height) {{
      return x >= 0 && y >= 0 && x + width <= boardWidth && y + height <= boardHeight;
    }}

    function localCircleInBounds(boardWidth, boardHeight, x, y, radius) {{
      return radius >= 0 && radius <= x && x <= boardWidth - radius && radius <= y && y <= boardHeight - radius;
    }}

    function localMovementLimitedDestination(battleState, actor, profile, destination, extraAllowance = 0, extraAssumptions = []) {{
      const movement = localMovementAllowance(battleState.map, actor, profile);
      movement.allowance += Math.max(0, Number(extraAllowance || 0));
      movement.assumptions = [...movement.assumptions, ...extraAssumptions];
      const bounded = {{
        x: Math.max(actor.radius, Math.min(battleState.map.width - actor.radius, Number(destination.x))),
        y: Math.max(actor.radius, Math.min(battleState.map.height - actor.radius, Number(destination.y)))
      }};
      const dist = distance(actor.x, actor.y, bounded.x, bounded.y);
      if (dist <= movement.allowance) {{
        return {{ destination: {{ x: Number(bounded.x.toFixed(2)), y: Number(bounded.y.toFixed(2)) }}, assumptions: movement.assumptions }};
      }}
      return {{
        destination: stepToward(actor.x, actor.y, bounded.x, bounded.y, movement.allowance),
        assumptions: [...movement.assumptions, `Move destination clamped to ${{movement.allowance.toFixed(1)}}" movement allowance.`]
      }};
    }}

    function localNonOverlappingDestination(battleState, actor, destination) {{
      const proposed = {{
        x: Math.max(actor.radius, Math.min(battleState.map.width - actor.radius, Number(destination.x))),
        y: Math.max(actor.radius, Math.min(battleState.map.height - actor.radius, Number(destination.y)))
      }};
      if (!localCollidesAt(battleState, actor, proposed.x, proposed.y)) return {{ destination: proposed, assumptions: [] }};
      for (let step = 23; step >= 0; step -= 1) {{
        const ratio = step / 24;
        const candidate = {{
          x: actor.x + (proposed.x - actor.x) * ratio,
          y: actor.y + (proposed.y - actor.y) * ratio
        }};
        if (!localCollidesAt(battleState, actor, candidate.x, candidate.y)) {{
          return {{
            destination: {{ x: Number(candidate.x.toFixed(2)), y: Number(candidate.y.toFixed(2)) }},
            assumptions: ["Movement destination adjusted to avoid overlapping another unit footprint."]
          }};
        }}
      }}
      return {{
        destination: {{ x: Number(actor.x.toFixed(2)), y: Number(actor.y.toFixed(2)) }},
        assumptions: ["Movement blocked because no non-overlapping destination was available along that path."]
      }};
    }}

    function localFallBackDestination(battleState, actor, enemy, allowance) {{
      const centreDistance = distance(actor.x, actor.y, enemy.x, enemy.y);
      const directionX = centreDistance > 0 ? (actor.x - enemy.x) / centreDistance : 1;
      const directionY = centreDistance > 0 ? (actor.y - enemy.y) / centreDistance : 0;
      const moved = localNonOverlappingDestination(battleState, actor, {{
        x: actor.x + directionX * allowance,
        y: actor.y + directionY * allowance
      }});
      return {{
        destination: moved.destination,
        assumptions: ["Fall Back movement is approximated as a direct move away from the nearest engaged enemy.", ...moved.assumptions]
      }};
    }}

    function localCollidesAt(battleState, actor, x, y) {{
      const moved = {{ ...actor, x, y }};
      return (battleState.units || [])
        .filter((unit) => unit.instance_id !== actor.instance_id && unit.models_remaining > 0 && !(unit.status_flags || []).includes("destroyed"))
        .some((unit) => localUnitsOverlap(moved, unit));
    }}

    function localUnitsOverlap(left, right) {{
      return distance(left.x, left.y, right.x, right.y) < Number(left.radius || 0) + Number(right.radius || 0);
    }}

    function localChargeProbability(actor, target) {{
      const required = Math.max(2, distance(actor.x, actor.y, target.x, target.y) - Number(actor.radius || 0) - Number(target.radius || 0));
      if (required <= 3) return 0.85;
      if (required <= 6) return 0.58;
      if (required <= 9) return 0.28;
      return 0.12;
    }}

    function localAttackDistance(actor, target) {{
      return Math.max(0, distance(actor.x, actor.y, target.x, target.y) - Number(actor.radius || 0) - Number(target.radius || 0));
    }}

    function localRangedAttackReach(unit) {{
      const ranges = (unit.weapons || [])
        .filter((weapon) => weapon.type === "ranged")
        .map(localWeaponRange);
      return ranges.length ? Math.max(...ranges) : 0;
    }}

    function localRangedAttackAssumptions(unit) {{
      if (!(unit.weapons || []).some((weapon) => weapon.type === "ranged")) return ["This unit has no imported ranged weapon profiles."];
      if ((unit.weapons || []).some((weapon) => weapon.type === "ranged" && weapon.range_inches)) return [];
      return ["Weapon ranges are not present in the current imported CSV; Battlefield mode uses tactical range estimates."];
    }}

    function localWeaponRange(weapon) {{
      if (weapon.range_inches) return Math.max(0, Number(weapon.range_inches || 0));
      const text = `${{weapon.name || ""}} ${{(weapon.keywords || []).join(" ")}}`.toLowerCase();
      if (text.includes("grenade")) return 8;
      if (text.includes("pistol")) return 12;
      if (text.includes("torrent") || text.includes("flamer") || text.includes("flame")) return 12;
      if (text.includes("melta")) return 18;
      if (["lascannon", "missile", "mortar", "battle cannon", "railgun", "volcano"].some((term) => text.includes(term))) return 48;
      return 36;
    }}

    function distance(x1, y1, x2, y2) {{
      return Math.hypot(Number(x2) - Number(x1), Number(y2) - Number(y1));
    }}

    function localTargetInCover(battleMap, unit) {{
      return (battleMap.terrain || []).some((feature) => feature.grants_cover && unit.x >= feature.x - unit.radius && unit.x <= feature.x + feature.width + unit.radius && unit.y >= feature.y - unit.radius && unit.y <= feature.y + feature.height + unit.radius);
    }}

    function localBattleVisibility(battleMap, actor, target) {{
      const coverSources = [];
      const interveningTerrain = [];
      const targetCover = localTargetInCover(battleMap, target);
      for (const feature of battleMap.terrain || []) {{
        if (!localSegmentIntersectsFeature(actor.x, actor.y, target.x, target.y, feature)) continue;
        const actorInside = localPointInFeature(actor.x, actor.y, feature);
        const targetInside = localPointInFeature(target.x, target.y, feature);
        if (feature.grants_cover && (targetInside || !actorInside)) coverSources.push(feature.name);
        if (feature.blocks_line_of_sight && !actorInside && !targetInside) interveningTerrain.push(feature.name);
      }}
      const blocked = interveningTerrain.length > 0;
      return {{
        target_in_cover: targetCover || coverSources.length > 0,
        line_of_sight_blocked: blocked,
        intervening_terrain: [...new Set(interveningTerrain)].sort(),
        cover_sources: [...new Set(coverSources)].sort(),
        damage_multiplier: blocked ? 0.25 : 1
      }};
    }}

    function localPointInFeature(x, y, feature) {{
      return x >= feature.x && x <= feature.x + feature.width && y >= feature.y && y <= feature.y + feature.height;
    }}

    function localSegmentIntersectsFeature(x1, y1, x2, y2, feature) {{
      const left = Number(feature.x);
      const right = Number(feature.x) + Number(feature.width);
      const top = Number(feature.y);
      const bottom = Number(feature.y) + Number(feature.height);
      if (localPointInFeature(x1, y1, feature) || localPointInFeature(x2, y2, feature)) return true;
      return localSegmentsIntersect(x1, y1, x2, y2, left, top, right, top)
        || localSegmentsIntersect(x1, y1, x2, y2, right, top, right, bottom)
        || localSegmentsIntersect(x1, y1, x2, y2, right, bottom, left, bottom)
        || localSegmentsIntersect(x1, y1, x2, y2, left, bottom, left, top);
    }}

    function localSegmentsIntersect(ax, ay, bx, by, cx, cy, dx, dy) {{
      const orientation = (px, py, qx, qy, rx, ry) => (qy - py) * (rx - qx) - (qx - px) * (ry - qy);
      const onSegment = (px, py, qx, qy, rx, ry) => Math.min(px, rx) <= qx && qx <= Math.max(px, rx) && Math.min(py, ry) <= qy && qy <= Math.max(py, ry);
      const o1 = orientation(ax, ay, bx, by, cx, cy);
      const o2 = orientation(ax, ay, bx, by, dx, dy);
      const o3 = orientation(cx, cy, dx, dy, ax, ay);
      const o4 = orientation(cx, cy, dx, dy, bx, by);
      if ((o1 > 0) !== (o2 > 0) && (o3 > 0) !== (o4 > 0)) return true;
      const epsilon = 1e-9;
      return Math.abs(o1) <= epsilon && onSegment(ax, ay, cx, cy, bx, by)
        || Math.abs(o2) <= epsilon && onSegment(ax, ay, dx, dy, bx, by)
        || Math.abs(o3) <= epsilon && onSegment(cx, cy, ax, ay, dx, dy)
        || Math.abs(o4) <= epsilon && onSegment(cx, cy, bx, by, dx, dy);
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

    async function loadUnitDetailById(unitId, name = "") {{
      if (unitId) return state.units.find((unit) => unit.id === unitId) || null;
      return findUnit(name);
    }}

    function queueUnitSearch(field, value = "") {{
      window.clearTimeout(state.searchTimer[field]);
      state.searchTimer[field] = window.setTimeout(() => {{
        loadUnits(value, field).catch((error) => {{
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
      const fieldUnits = state.unitSearchResults[field] || [];
      if (selectedId) {{
        const byId = fieldUnits.find((unit) => unit.id === selectedId) || state.units.find((unit) => unit.id === selectedId);
        if (byId) return byId;
        const cached = state.unitDetails[selectedId];
        if (cached) return cached;
      }}
      return fieldUnits.find((unit) => unit.name === unitName) || state.units.find((unit) => unit.name === unitName) || null;
    }}

    function unitVariantLabel(unit) {{
      if (!unit) return "";
      const modelRange = unitModelRange(unit);
      const parts = [];
      if (unit.faction) parts.push(unit.faction);
      if (unit.points) parts.push(`${{unit.points}} pts`);
      parts.push(`Models ${{modelRange}}`);
      return parts.join(" | ");
    }}

    function unitModelRange(unit) {{
      const min = unit.models_min ?? unit.modelsMin;
      const max = unit.models_max ?? unit.modelsMax;
      return min && max && min !== max ? `${{min}}-${{max}}` : (min || max || "unknown");
    }}

    function unitSourceFile(unit) {{
      return unit ? (unit.source_file || unit.sourceFile || "") : "";
    }}

    function unitAuditLabel(unit) {{
      if (!unit) return "";
      const sourceFile = unitSourceFile(unit);
      const parts = [];
      if (sourceFile) parts.push(`Source ${{sourceFile}}`);
      if (unit.id) parts.push(`ID ${{unit.id}}`);
      return parts.join(" | ");
    }}

    function updateSelectedUnitInfo(field) {{
      const target = el(`${{field}}-selected`);
      const unit = selectedUnit(field);
      if (!unit) {{
        target.textContent = "";
        return;
      }}
      const audit = unitAuditLabel(unit);
      target.innerHTML = `${{escapeHtml(unitVariantLabel(unit))}}${{audit ? ` <details><summary>Details</summary><span>${{escapeHtml(audit)}}</span></details>` : ""}}`;
    }}

    function updateSelectedUnitInfos() {{
      updateSelectedUnitInfo("attacker");
      updateSelectedUnitInfo("defender");
    }}

    function closeDropdown(field = state.openMenu) {{
      if (!field) return;
      el(`${{field}}-menu`).classList.remove("open");
      el(`${{field}}-menu`).closest(".unit-combo")?.classList.remove("menu-open");
      el(field).setAttribute("aria-expanded", "false");
      document.querySelector(`.combo-toggle[data-target="${{field}}"]`)?.setAttribute("aria-expanded", "false");
      el(field).removeAttribute("aria-activedescendant");
      state.activeOptionIndex[field] = -1;
      if (state.openMenu === field) state.openMenu = null;
    }}

    function dropdownOptions(field) {{
      return [...el(`${{field}}-options`).querySelectorAll(".combo-option:not([aria-disabled='true'])")];
    }}

    function setActiveOption(field, index) {{
      const options = dropdownOptions(field);
      if (!options.length) {{
        state.activeOptionIndex[field] = -1;
        el(field).removeAttribute("aria-activedescendant");
        return;
      }}
      const bounded = Math.max(0, Math.min(options.length - 1, index));
      state.activeOptionIndex[field] = bounded;
      options.forEach((option, optionIndex) => {{
        const active = optionIndex === bounded;
        option.classList.toggle("active", active);
        option.setAttribute("aria-selected", active ? "true" : "false");
      }});
      el(field).setAttribute("aria-activedescendant", options[bounded].id);
      options[bounded].scrollIntoView({{ block: "nearest" }});
    }}

    function selectDropdownOption(field, button) {{
      el(field).value = button.dataset.unit;
      state.selectedUnitIds[field] = button.dataset.unitId || null;
      updateSelectedUnitInfo(field);
      closeDropdown(field);
      refreshWeaponSelectors().catch((error) => {{
        el("error").textContent = error.message;
      }});
    }}

    function renderDropdown(field, units) {{
      const menu = el(`${{field}}-options`);
      const rows = units.slice(0, 80);
      const count = el(`${{field}}-menu-count`);
      if (count) {{
        count.textContent = units.length > rows.length
          ? `Showing first ${{rows.length}} of ${{units.length}} matches. Type to narrow.`
          : `${{units.length}} matching ${{units.length === 1 ? "unit" : "units"}}`;
      }}
      if (!rows.length) {{
        menu.innerHTML = `<div class="combo-option" role="option" aria-disabled="true">No matching units</div>`;
        return;
      }}
      menu.innerHTML = rows.map((unit, index) => `
        <div class="combo-option" id="${{field}}-option-${{index}}" role="option" aria-selected="false" tabindex="-1" data-unit="${{escapeHtml(unit.name)}}" data-unit-id="${{escapeHtml(unit.id || "")}}">
          ${{escapeHtml(unit.name)}}
          <span>${{escapeHtml(optionSubtitle(unit))}}</span>
        </div>
      `).join("");
      menu.querySelectorAll(".combo-option").forEach((option) => {{
        option.addEventListener("mousedown", (event) => {{
          event.preventDefault();
          selectDropdownOption(field, option);
        }});
      }});
      const selectedIndex = rows.findIndex((unit) => unit.id && unit.id === state.selectedUnitIds[field]);
      setActiveOption(field, selectedIndex >= 0 ? selectedIndex : 0);
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
        option.textContent = `${{weapon.name}}${{weapon.range_inches ? ` | R${{weapon.range_inches}}"` : ""}} | A${{weapon.attacks}} ${{weapon.skillLabel || weapon.skill}} S${{weapon.strength}} AP${{weapon.ap}} D${{weapon.damage}}`;
        select.appendChild(option);
      }}
      select.disabled = weapons.length === 0;
      select.value = [...select.options].some((option) => option.value === previous) ? previous : "__all__";
    }}

    async function openDropdown(field) {{
      if (state.openMenu && state.openMenu !== field) closeDropdown(state.openMenu);
      state.openMenu = field;
      el(field).setAttribute("aria-expanded", "true");
      document.querySelector(`.combo-toggle[data-target="${{field}}"]`)?.setAttribute("aria-expanded", "true");
      el(`${{field}}-menu`).closest(".unit-combo")?.classList.add("menu-open");
      const units = await searchUnits(el(field).value, field);
      state.unitSearchResults[field] = units;
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
      const confidenceText = `${{Math.round(prediction.confidence * 100)}}% model confidence`;
      result.ml_judgement = {{
        available: true,
        title: winner ? `ML advisory: ${{winner}} favoured (${{confidenceText}})` : `ML advisory: close matchup (${{confidenceText}})`,
        body: `${{outcome}} Model confidence is ${{confidenceBasis}} at ${{Math.round(prediction.confidence * 100)}}%; model has ${{accuracyText}}. Use this as an advisory signal only, not a rules result.`,
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
      setAppMode("calculator");
      el("error").textContent = "";
      closeDropdown();
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
        if (window.matchMedia("(max-width: 840px)").matches) {{
          el("results").scrollIntoView({{ behavior: "smooth", block: "start" }});
        }}
      }} catch (error) {{
        el("error").textContent = error.message;
      }} finally {{
        button.disabled = false;
      }}
    }}

    function renderUnit(unit, label) {{
      const keywords = (unit.keywords || []).slice(0, 8).map((keyword) => `<span class="chip">${{escapeHtml(keyword)}}</span>`).join("");
      const modelRange = unitModelRange(unit);
      const sourceFile = unitSourceFile(unit);
      const sourceLine = sourceFile ? `<div class="small">Source ${{escapeHtml(sourceFile)}}</div>` : "";
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
      const netDamage = Number(outgoing.total_damage || 0) - Number(incoming.total_damage || 0);
      const netPoints = Number(outgoing.estimated_points_removed || 0) - Number(incoming.estimated_points_removed || 0);
      el("results").dataset.view = "calculator";
      el("results").innerHTML = `
        <div class="judgement primary">
          <h3>${{escapeHtml(judgement.title)}}</h3>
          <p>${{escapeHtml(judgement.body)}}</p>
          <p class="small">Edition: ${{escapeHtml(editionLabel(payload.edition || state.rulesEdition))}} | Attacker scope: ${{escapeHtml(scopeText(payload, "outgoing"))}} | Return scope: ${{escapeHtml(scopeText(payload, "incoming"))}}</p>
        </div>
        ${{renderMlJudgement(payload)}}
        <div class="summary">
          ${{metric("Net points", signedFmt(netPoints))}}
          ${{metric("Net damage", signedFmt(netDamage))}}
          ${{metric("Outgoing damage", fmt(outgoing.total_damage))}}
          ${{metric("Return damage", fmt(incoming.total_damage))}}
          ${{metric("Outgoing models", fmt(outgoing.expected_models_destroyed))}}
          ${{metric("Return models", fmt(incoming.expected_models_destroyed))}}
        </div>
        <div class="duel">
          ${{renderUnit(payload.attacker, "Attacker")}}
          ${{renderUnit(payload.defender, "Defender")}}
        </div>
        ${{renderLoadoutWarnings(payload)}}
        ${{renderWeaponList(outgoing, `${{payload.attacker.name}} attack`, `No ${{payload.mode}} weapons found for ${{payload.attacker.name}}.`)}}
        ${{renderWeaponList(incoming, `${{payload.defender.name}} return strike`, `No ${{payload.mode}} weapons found for ${{payload.defender.name}}.`)}}
      `;
    }}

    async function showDataReview() {{
      setAppMode("data-review");
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
      const unitFootprints = payload.unit_footprint_summary;
      const unitFootprintSuggestions = payload.unit_footprint_suggestion_summary;
      const unitFootprintTemplate = payload.unit_footprint_template_summary;
      const unitFootprintQueue = payload.unit_footprint_queue_summary;
      const unitFootprintReview = payload.unit_footprint_review;
      const abilityModifiers = payload.ability_modifier_summary;
      const schema = payload.schema_summary;
      const updateReport = payload.update_report;
      const profileReview = payload.profile_review;
      const editionReadiness = payload.edition_readiness;
      const modelAudit = payload.model_audit;
      const modelComparison = payload.model_comparison;
      const reviewFiles = payload.review_files || [];
      const modelFiles = payload.model_files || [];
      if (!audit && !diff && !metadata && !editionStatus && !artifactManifest && !verificationReport && !suspiciousWeapons && !unitProfiles && !loadouts && !sourceCatalogues && !unitVariants && !weaponCoverage && !unitFootprints && !unitFootprintSuggestions && !unitFootprintTemplate && !unitFootprintQueue && !unitFootprintReview && !abilityModifiers && !schema && !updateReport && !profileReview && !editionReadiness && !modelAudit && !modelComparison) {{
        el("results").dataset.view = "data-review";
        el("results").innerHTML = renderDataReviewEmptyState();
        return;
      }}
      const source = metadata && metadata.source_revisions && metadata.source_revisions[0]
        ? metadata.source_revisions[0]
        : null;
      const generatedAt = metadata && metadata.generated_at ? metadata.generated_at : (audit && audit.generated_at ? audit.generated_at : "unknown");
      const commit = source && source.commit ? source.commit.slice(0, 12) : "unknown";
      const remote = source && source.remote_origin ? source.remote_origin : "unknown source";
      const summary = audit && audit.summary ? audit.summary : {{ error: 0, warning: 0, info: 0, total: 0 }};
      el("results").dataset.view = "data-review";
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
        ${{renderReviewNav()}}
        ${{renderReviewTools()}}
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
        ${{renderUnitFootprintReview(unitFootprintReview)}}
        ${{renderUnitFootprints(unitFootprints)}}
        ${{renderUnitFootprintSuggestions(unitFootprintSuggestions)}}
        ${{renderUnitFootprintTemplateSummary(unitFootprintTemplate)}}
        ${{renderUnitFootprintQueue(unitFootprintQueue)}}
        ${{renderAbilityModifiers(abilityModifiers)}}
        ${{renderReviewFiles([...reviewFiles, ...modelFiles])}}
        ${{renderModelComparison(modelComparison)}}
        ${{renderModelAudit(modelAudit)}}
        ${{renderUpdateReport(updateReport)}}
        ${{renderProfileReview(profileReview)}}
        ${{renderDiff(diff)}}
        ${{renderAuditSections(audit)}}
      `;
      wireDataReviewFilters();
    }}

    function renderReviewNav() {{
      const links = [
        ["#review-provenance", "Provenance"],
        ["#review-schema", "Schema"],
        ["#review-weapons", "Suspicious Weapons"],
        ["#review-loadouts", "Loadouts"],
        ["#review-footprints", "Footprints"],
        ["#review-ml", "ML"],
        ["#review-files", "Raw Reports"]
      ].map(([href, label]) => `<a href="${{href}}">${{label}}</a>`).join("");
      return `<nav class="review-nav" aria-label="Data review sections">${{links}}</nav>`;
    }}

    function renderReviewTools() {{
      return `
        <div class="review-tools" aria-label="Data review filters">
          <label>
            Search review data
            <input id="data-review-search" type="search" placeholder="Unit, weapon, source, reason" autocomplete="off">
          </label>
          <label>
            Status
            <select id="data-review-status">
              <option value="">All statuses</option>
              <option value="problem">Problems</option>
              <option value="error">Errors / failed</option>
              <option value="warning">Warnings</option>
              <option value="ok">OK / info</option>
            </select>
          </label>
          <button id="data-review-clear" type="button">Reset</button>
          <div class="review-filter-status" id="data-review-filter-status" aria-live="polite"></div>
        </div>
        <div class="review-filter-empty" id="data-review-filter-empty">No review rows match the current filters.</div>
      `;
    }}

    function renderDataReviewEmptyState() {{
      return `<div class="review-empty" data-testid="data-review-empty-state"><svg class="review-empty-art" data-testid="data-review-empty-art" viewBox="0 0 260 200" role="img" aria-label="Data review artifact preview"><rect x="34" y="26" width="192" height="148" rx="12" fill="#f7fafc" stroke="#cfd8e3"></rect><rect x="52" y="48" width="72" height="14" rx="4" fill="#21639f" opacity=".18"></rect><rect x="52" y="76" width="156" height="10" rx="5" fill="#e6ebf0"></rect><rect x="52" y="100" width="132" height="10" rx="5" fill="#e6ebf0"></rect><rect x="52" y="124" width="156" height="10" rx="5" fill="#e6ebf0"></rect><circle cx="198" cy="81" r="10" fill="#24745f"></circle><path d="M193 81l4 4 7-8" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path><circle cx="198" cy="105" r="10" fill="#aa7a1e"></circle><path d="M198 99v7" stroke="#fff" stroke-width="3" stroke-linecap="round"></path><circle cx="198" cy="112" r="1.5" fill="#fff"></circle><circle cx="198" cy="129" r="10" fill="#24745f"></circle><path d="M193 129l4 4 7-8" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path><path d="M70 154h120" stroke="#cfd8e3" stroke-width="4" stroke-linecap="round"></path></svg><div class="review-empty-copy"><h3>No review artifacts found</h3><p>Run a database update or release verification to generate audit reports, schema checks, provenance, and artifact manifests.</p><div class="review-empty-checks"><span><i class="step-dot">1</i>Refresh imported data</span><span><i class="step-dot">2</i>Generate audit artifacts</span><span><i class="step-dot">3</i>Open Data Review again</span></div></div></div>`;
    }}

    function wireDataReviewFilters() {{
      const search = el("data-review-search");
      const status = el("data-review-status");
      const clear = el("data-review-clear");
      if (!search || !status || !clear) return;
      const apply = () => applyDataReviewFilters(search.value, status.value);
      search.addEventListener("input", apply);
      status.addEventListener("change", apply);
      clear.addEventListener("click", () => {{
        search.value = "";
        status.value = "";
        apply();
        search.focus();
      }});
      apply();
    }}

    function statusMatches(text, filter) {{
      const normalized = String(text || "").toLowerCase();
      if (!filter) return true;
      if (filter === "problem") return /error|fail|failed|warning/.test(normalized);
      if (filter === "error") return /error|fail|failed/.test(normalized);
      if (filter === "warning") return normalized.includes("warning");
      if (filter === "ok") return /ok|pass|info/.test(normalized);
      return true;
    }}

    function applyDataReviewFilters(queryValue, statusValue) {{
      const query = String(queryValue || "").trim().toLowerCase();
      const sections = [...document.querySelectorAll("#results .review-section")];
      let visibleSections = 0;
      let visibleRows = 0;
      let totalRows = 0;

      sections.forEach((section) => {{
        const rows = [...section.querySelectorAll("tbody tr")];
        const dataRows = rows.filter((row) => !(row.cells.length === 1 && row.cells[0].colSpan > 1));
        const sectionTitleMatches = Boolean(query && section.querySelector("h3") && section.querySelector("h3").textContent.toLowerCase().includes(query));
        let sectionRowsVisible = 0;

        if (dataRows.length) {{
          rows.forEach((row) => {{
            const isEmptyRow = row.cells.length === 1 && row.cells[0].colSpan > 1;
            if (isEmptyRow) {{
              row.hidden = Boolean(query || statusValue);
              return;
            }}
            totalRows += 1;
            const text = row.textContent.toLowerCase();
            const statusText = row.cells[0] ? row.cells[0].textContent : "";
            const visible = (!query || text.includes(query) || sectionTitleMatches) && statusMatches(statusText, statusValue);
            row.hidden = !visible;
            if (visible) {{
              sectionRowsVisible += 1;
              visibleRows += 1;
            }}
          }});
          section.hidden = sectionRowsVisible === 0;
        }} else {{
          const visible = (!query || section.textContent.toLowerCase().includes(query)) && !statusValue;
          section.hidden = !visible;
        }}

        if (!section.hidden) visibleSections += 1;
      }});

      const status = el("data-review-filter-status");
      if (status) {{
        const rowText = totalRows ? `${{visibleRows}} of ${{totalRows}} table rows` : "no table rows";
        status.textContent = `${{visibleSections}} review sections visible, ${{rowText}} visible`;
      }}
      const empty = el("data-review-filter-empty");
      if (empty) empty.classList.toggle("visible", visibleSections === 0);
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
        <div class="review-section" id="review-weapons">
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
        <div class="review-section" id="review-schema">
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
      const loadoutRows = (summary.rows || []).map((row) => {{
        const missingRange = Number(row.ranged_weapons_missing_range || 0);
        const rangeText = missingRange ? ` / ${{missingRange}} ranged missing range` : "";
        return `
          <tr>
            <td>${{escapeHtml(row.severity || "")}}</td>
            <td>${{escapeHtml(row.category || "")}}</td>
            <td>${{escapeHtml(row.unit_name || "")}}</td>
            <td>${{escapeHtml(row.faction || "")}}</td>
            <td>${{escapeHtml(`${{row.total_weapons || "0"}} total / ${{row.ranged_weapons || "0"}} ranged / ${{row.melee_weapons || "0"}} melee${{rangeText}}`)}}</td>
            <td>${{escapeHtml(row.points || "")}}</td>
            <td>${{escapeHtml(row.review_reason || "")}}</td>
          </tr>
        `;
      }}).join("");
      return `
        <div class="review-section" id="review-loadouts">
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
            <td>${{escapeHtml(row.ranged_weapons_missing_range || "0")}}</td>
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
            ${{provenanceCard("Missing ranges", totals.ranged_weapons_missing_range || 0, "Ranged weapon profiles without explicit range")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Source</th><th>Units</th><th>Weapons</th><th>Suspicious</th><th>Unit Issues</th><th>Loadouts</th><th>No Weapons</th><th>Missing Ranges</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="8">No source catalogue review rows were generated.</td></tr>`}}</tbody>
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
            ${{provenanceCard("Ranged with range", summary.ranged_weapons_with_range || 0, "Explicit imported weapon ranges")}}
            ${{provenanceCard("Ranged missing range", summary.ranged_weapons_missing_range || 0, "Uses tactical fallback estimates")}}
            ${{coverageCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Unit</th><th>Faction</th><th>Type</th><th>Points</th><th>Models</th><th>Source</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="6">No units without imported weapons were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitFootprints(summary) {{
      if (!summary) return "";
      const severityCards = Object.entries(summary.by_severity || {{}}).map(([key, value]) => provenanceCard(`Severity: ${{key}}`, value, ""));
      const categoryCards = Object.entries(summary.by_category || {{}}).map(([key, value]) => provenanceCard(`Category: ${{key}}`, value, ""));
      const statusCards = Object.entries(summary.by_status || {{}}).map(([key, value]) => provenanceCard(`Status: ${{key}}`, value, ""));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.severity || "")}}</td>
          <td>${{escapeHtml(row.category || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(row.base_width_mm && row.base_depth_mm ? `${{row.base_width_mm}}x${{row.base_depth_mm}}mm ${{row.base_shape || ""}}` : (row.base_type || ""))}}</td>
          <td>${{escapeHtml(row.guide_faction || "")}}</td>
          <td>${{escapeHtml(row.match_confidence || "")}}</td>
          <td>${{escapeHtml(row.review_reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section" id="review-footprints">
          <h3>Unit Footprint Review</h3>
          <div class="provenance-grid">
            ${{provenanceCard("Rows needing review", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{severityCards.join("")}}
            ${{categoryCards.join("")}}
            ${{statusCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Severity</th><th>Category</th><th>Unit</th><th>Faction</th><th>Base</th><th>Guide faction</th><th>Confidence</th><th>Reason</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="8">No footprint review rows were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitFootprintSuggestions(summary) {{
      if (!summary) return "";
      const scoreCards = Object.entries(summary.by_score_band || {{}}).map(([key, value]) => provenanceCard(`Score: ${{key}}`, value, ""));
      const factionCards = Object.entries(summary.by_faction || {{}}).slice(0, 6).map(([key, value]) => provenanceCard(key, value, "suggestions"));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.suggestion_rank || "")}}</td>
          <td>${{escapeHtml(row.suggestion_score || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(row.guide_unit_name || "")}}${{row.guide_model_name ? `: ${{escapeHtml(row.guide_model_name)}}` : ""}}</td>
          <td>${{escapeHtml(row.guide_faction || "")}}</td>
          <td>${{escapeHtml(row.base_size_text || (row.base_width_mm && row.base_depth_mm ? `${{row.base_width_mm}}x${{row.base_depth_mm}}mm` : row.base_type || ""))}}</td>
          <td>${{row.source_url ? `<a href="${{escapeHtml(row.source_url)}}" target="_blank" rel="noreferrer">Page ${{escapeHtml(row.source_page || "unknown")}}</a>` : escapeHtml(row.source_page || "")}}</td>
          <td>${{escapeHtml(row.suggestion_reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Footprint Match Suggestions</h3>
          <p class="small">Suggestions are review aids only. They do not affect Battlefield footprint sizing until accepted into the manual override CSV.</p>
          <div class="provenance-grid">
            ${{provenanceCard("Suggestion rows", summary.total || 0, `${{summary.unit_total || 0}} unmatched units have candidates`)}}
            ${{scoreCards.join("")}}
            ${{factionCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Rank</th><th>Score</th><th>Imported unit</th><th>Faction</th><th>Suggested guide row</th><th>Guide faction</th><th>Base</th><th>Guide source</th><th>Reason</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="9">No footprint suggestions were generated.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitFootprintTemplateSummary(summary) {{
      if (!summary) return "";
      const statusCards = Object.entries(summary.by_status || {{}})
        .filter(([key]) => !["total", "outside_filter"].includes(key))
        .map(([key, value]) => provenanceCard(`Template: ${{key.replaceAll("_", " ")}}`, value, ""));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.unit_name || "")}}</td>
          <td><code>${{escapeHtml(row.unit_id || "")}}</code></td>
          <td>${{escapeHtml(row.review_decision || "")}}</td>
          <td>${{escapeHtml(row.reason || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Footprint Override Template Status</h3>
          <p class="small">Rows become active only after review decisions are promoted into the manual override CSV.</p>
          <div class="provenance-grid">
            ${{provenanceCard("Template rows", summary.total || 0, `${{summary.blank_total || 0}} still blank`)}}
            ${{provenanceCard("Ready to promote", summary.ready_total || 0, "Suggestion-ready plus manual override-ready rows")}}
            ${{provenanceCard("Invalid reviewed rows", summary.invalid_total || 0, "Fix before applying reviewed rows")}}
            ${{statusCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Unit</th><th>Unit ID</th><th>Decision</th><th>Issue</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="4">No invalid reviewed template rows.</td></tr>`}}</tbody>
          </table>
        </div>
      `;
    }}

    function renderUnitFootprintQueue(summary) {{
      if (!summary) return "";
      const priorityCards = Object.entries(summary.by_priority || {{}}).map(([key, value]) => provenanceCard(`Queue: ${{key.replaceAll("_", " ")}}`, value, ""));
      const factionCards = Object.entries(summary.by_faction || {{}}).slice(0, 6).map(([key, value]) => provenanceCard(key, value, "queue rows"));
      const rows = (summary.rows || []).map((row) => `
        <tr>
          <td>${{escapeHtml(row.review_rank || "")}}</td>
          <td>${{escapeHtml(row.review_priority || "")}}</td>
          <td>${{escapeHtml(row.unit_name || "")}}<br><code>${{escapeHtml(row.unit_id || "")}}</code></td>
          <td>${{escapeHtml(row.faction || "")}}</td>
          <td>${{escapeHtml(row.suggestion_score || "")}}</td>
          <td>${{escapeHtml(row.suggested_guide_unit_name || "")}}${{row.suggested_guide_model_name ? `: ${{escapeHtml(row.suggested_guide_model_name)}}` : ""}}</td>
          <td>${{escapeHtml(row.suggested_base_size_text || "")}}</td>
          <td>${{row.suggested_source_url ? `<a href="${{escapeHtml(row.suggested_source_url)}}" target="_blank" rel="noreferrer">Page ${{escapeHtml(row.suggested_source_page || "unknown")}}</a>` : escapeHtml(row.suggested_source_page || "")}}</td>
          <td>${{escapeHtml(row.review_hint || "")}}</td>
        </tr>
      `).join("");
      return `
        <div class="review-section">
          <h3>Footprint Review Queue</h3>
          <p class="small">Prioritized manual review batch from the override template. Use this to decide which rows to research first.</p>
          <div class="provenance-grid">
            ${{provenanceCard("Queued rows", summary.total || 0, `Showing first ${{Math.min((summary.rows || []).length, summary.row_limit || 0)}} rows`)}}
            ${{priorityCards.join("")}}
            ${{factionCards.join("")}}
          </div>
          <table class="report-table">
            <thead><tr><th>Rank</th><th>Priority</th><th>Unit</th><th>Faction</th><th>Score</th><th>Suggested guide row</th><th>Base</th><th>Guide source</th><th>Review hint</th></tr></thead>
            <tbody>${{rows || `<tr><td colspan="9">No footprint review queue rows were generated.</td></tr>`}}</tbody>
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
        <div class="review-section" id="review-provenance">
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
        <div class="review-section" id="review-files">
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

    function renderUnitFootprintReview(unitFootprintReview) {{
      if (!unitFootprintReview) return "";
      return renderMarkdownReport("Unit Footprint Review Report", unitFootprintReview, "review-footprint-report");
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
      return renderMarkdownReport("ML Model Audit", modelAudit, "review-ml");
    }}

    function renderModelComparison(modelComparison) {{
      if (!modelComparison) return "";
      return renderMarkdownReport("ML Model Comparison", modelComparison);
    }}

    function renderMarkdownReport(title, markdown, sectionId = "") {{
      return `
        <div class="review-section"${{sectionId ? ` id="${{escapeHtml(sectionId)}}"` : ""}}>
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

    function setAppMode(mode) {{
      const normalized = ["calculator", "battlefield", "data-review"].includes(mode) ? mode : "calculator";
      document.body.dataset.view = normalized;
      document.querySelectorAll(".mode-tab").forEach((button) => {{
        const active = button.dataset.appMode === normalized;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      }});
      if (normalized !== "calculator") closeDropdown();
    }}

    function showCalculator() {{
      setAppMode("calculator");
      if (el("results").dataset.view === "calculator") return;
      if (state.lastResult) {{
        renderResults(state.lastResult);
        return;
      }}
      el("results").dataset.view = "calculator";
      el("results").innerHTML = renderCalculatorEmptyState();
    }}

    function renderCalculatorEmptyState() {{
      return `<div class="calculator-empty" data-testid="calculator-empty-state"><svg class="calculator-empty-art" data-testid="calculator-empty-art" viewBox="0 0 260 200" role="img" aria-label="Damage calculation preview"><rect x="28" y="28" width="204" height="144" rx="12" fill="#f7fafc" stroke="#cfd8e3"></rect><path d="M52 66h156M52 100h156M52 134h156" stroke="#dfe7ee" stroke-width="4" stroke-linecap="round"></path><circle cx="72" cy="100" r="24" fill="#a5242c"></circle><circle cx="188" cy="100" r="24" fill="#21639f"></circle><path d="M96 100h68" stroke="#aa7a1e" stroke-width="8" stroke-linecap="round"></path><path d="M152 88l18 12-18 12" fill="none" stroke="#aa7a1e" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"></path><rect x="54" y="146" width="152" height="10" rx="5" fill="#e6ebf0"></rect><rect x="54" y="146" width="102" height="10" rx="5" fill="#24745f"></rect><text x="72" y="105" text-anchor="middle" fill="#fff" font-size="18" font-weight="800">A</text><text x="188" y="105" text-anchor="middle" fill="#fff" font-size="18" font-weight="800">D</text></svg><div class="calculator-empty-copy"><h3>Choose a matchup</h3><p>Select an attacker and defender, then calculate expected damage, models destroyed, points removed, and the matchup judgement.</p><div class="calculator-empty-steps"><span><i class="step-dot">1</i>Pick two units</span><span><i class="step-dot">2</i>Set weapon and context options</span><span><i class="step-dot">3</i>Run the calculator</span></div></div></div>`;
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
      setAppMode("calculator");
      el("calculate").addEventListener("click", calculate);
      el("battlefield").addEventListener("click", () => showBattlefield().catch(showBattlefieldError));
      el("data-review").addEventListener("click", showDataReview);
      el("nav-calculator").addEventListener("click", showCalculator);
      el("nav-battlefield").addEventListener("click", () => showBattlefield().catch(showBattlefieldError));
      el("nav-data-review").addEventListener("click", showDataReview);
      el("swap").addEventListener("click", () => {{
        const attacker = el("attacker").value;
        el("attacker").value = el("defender").value;
        el("defender").value = attacker;
        const attackerId = state.selectedUnitIds.attacker;
        state.selectedUnitIds.attacker = state.selectedUnitIds.defender;
        state.selectedUnitIds.defender = attackerId;
        const attackerUnits = state.unitSearchResults.attacker;
        state.unitSearchResults.attacker = state.unitSearchResults.defender;
        state.unitSearchResults.defender = attackerUnits;
        const attackerFaction = el("attacker-faction").value;
        el("attacker-faction").value = el("defender-faction").value;
        el("defender-faction").value = attackerFaction;
        updateSelectedUnitInfos();
        swapContexts();
        refreshWeaponSelectors().catch((error) => {{
          el("error").textContent = error.message;
        }});
      }});
      for (const field of ["attacker", "defender"]) {{
        el(factionSelectId(field)).addEventListener("change", () => {{
          state.selectedUnitIds[field] = null;
          state.unitSearchResults[field] = [];
          el(field).value = "";
          updateSelectedUnitInfo(field);
          refreshWeaponSelectors().catch((error) => {{
            el("error").textContent = error.message;
          }});
          loadUnits("", field).catch((error) => {{
            el("error").textContent = error.message;
          }});
        }});
      }}
      document.querySelectorAll(".combo-toggle").forEach((button) => {{
        button.addEventListener("click", () => {{
          const target = button.dataset.target;
          if (state.openMenu === target) {{
            closeDropdown(target);
            return;
          }}
          openDropdown(target).catch((error) => {{
            el("error").textContent = error.message;
          }});
        }});
      }});
      document.querySelectorAll(".combo-done").forEach((button) => {{
        button.addEventListener("click", () => {{
          closeDropdown(button.dataset.target);
        }});
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
            queueUnitSearch(id, value);
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
          const menuOpen = state.openMenu === id && el(`${{id}}-menu`).classList.contains("open");
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {{
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            if (!menuOpen) {{
              openDropdown(id).catch((error) => {{
                el("error").textContent = error.message;
              }});
              return;
            }}
            setActiveOption(id, state.activeOptionIndex[id] + direction);
          }} else if (event.key === "Enter") {{
            if (menuOpen && state.activeOptionIndex[id] >= 0) {{
              event.preventDefault();
              const option = dropdownOptions(id)[state.activeOptionIndex[id]];
              if (option) selectDropdownOption(id, option);
            }} else {{
              calculate();
            }}
          }} else if (event.key === "Escape") {{
            closeDropdown(id);
          }}
        }});
      }}
    }}

    wireEvents();
    Promise.all([loadHealth(), loadUnits("", "attacker")]).catch((error) => {{
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
        "unitFootprintSummary": unit_footprint_summary(csv_dir / "unit_footprint_review.csv"),
        "unitFootprintSuggestionSummary": unit_footprint_suggestion_summary(csv_dir / "unit_footprint_suggestions.csv"),
        "unitFootprintTemplateSummary": unit_footprint_template_summary(
            csv_dir / "unit_footprint_override_template.csv",
            csv_dir / "unit_footprint_overrides.csv",
        ),
        "unitFootprintQueueSummary": unit_footprint_queue_summary(csv_dir / "unit_footprint_review_queue.csv"),
        "unitFootprintReview": _load_text(csv_dir / "unit_footprint_review.md"),
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
        "base_size_guide.csv": "Official base-size guide CSV",
        "unit_footprint_overrides.csv": "Unit footprint manual overrides CSV",
        "unit_footprint_rejections.csv": "Unit footprint rejected suggestions CSV",
        "unit_footprint_override_template.csv": "Unit footprint override template CSV",
        "unit_footprint_review_queue.csv": "Unit footprint prioritized review queue CSV",
        "unit_footprints.csv": "Unit footprint CSV",
        "unit_footprint_review.csv": "Unit footprint review CSV",
        "unit_footprint_review.md": "Unit footprint review report",
        "unit_footprint_suggestions.csv": "Unit footprint suggestions CSV",
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
