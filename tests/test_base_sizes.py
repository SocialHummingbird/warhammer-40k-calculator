from pathlib import Path

from warhammer.base_sizes import (
    accepted_override_rows_from_template,
    accepted_override_rows_from_suggestions,
    build_footprint_override_template,
    build_footprint_review_queue,
    build_footprint_suggestions,
    faction_compatible,
    generate_unit_footprint_artifacts,
    match_unit_footprints,
    parse_base_size_lines,
    parse_base_size_text,
    rejected_rows_from_suggestions,
    summarize_footprint_override_template,
    unit_name_keys,
)
from warhammer.battlefield.simulation import default_radius, footprint_dimensions_mm
from warhammer.profiles import UnitProfile


def test_parse_base_size_lines_extracts_faction_rows_and_model_variants():
    records = parse_base_size_lines(
        [
            (14, "BASE SIZE GUIDE"),
            (15, "ORKS"),
            (15, "Boyz 32mm"),
            (15, "Rukkatrukk Squigbuggy 150x95mm Oval Base"),
            (15, "Battlewagon Hull"),
            (28, "CHAOS SPACE MARINES"),
            (28, "Accursed Cultists: Torment 40mm"),
        ]
    )

    assert [record.guide_faction for record in records] == ["ORKS", "ORKS", "ORKS", "CHAOS SPACE MARINES"]
    assert records[0].guide_unit_name == "Boyz"
    assert records[0].base_width_mm == "32"
    assert records[1].base_shape == "oval"
    assert records[1].base_depth_mm == "95"
    assert records[2].base_type == "hull"
    assert records[3].guide_model_name == "Torment"


def test_parse_base_size_text_handles_common_official_formats():
    assert parse_base_size_text("32mm") == {
        "base_type": "round",
        "base_shape": "round",
        "base_width_mm": "32",
        "base_depth_mm": "32",
    }
    assert parse_base_size_text("90x52.5mm Oval Base")["base_shape"] == "oval"
    assert parse_base_size_text("Large Flying Base")["base_type"] == "large_flying_base"


def test_match_unit_footprints_uses_faction_and_flags_multi_base_units():
    units = [
        {
            "unit_id": "boyz",
            "faction": "Xenos - Orks",
            "name": "Boyz",
            "selection_type": "unit",
            "models_min": "10",
            "models_max": "20",
        },
        {
            "unit_id": "guardians",
            "faction": "Aeldari - Aeldari Library",
            "name": "Guardian Defenders",
            "selection_type": "unit",
            "models_min": "11",
            "models_max": "11",
        },
    ]
    guide = [
        {
            "guide_faction": "ORKS",
            "guide_unit_name": "Boyz",
            "guide_model_name": "",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "32",
            "base_depth_mm": "32",
        },
        {
            "guide_faction": "AELDARI",
            "guide_unit_name": "Guardian Defenders",
            "guide_model_name": "Heavy Weapon Platform",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "40",
            "base_depth_mm": "40",
        },
        {
            "guide_faction": "AELDARI",
            "guide_unit_name": "Guardian Defenders",
            "guide_model_name": "Guardian",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "28.5",
            "base_depth_mm": "28.5",
        },
    ]

    footprints, reviews = match_unit_footprints(units, guide)

    assert footprints[0]["footprint_status"] == "matched"
    assert footprints[0]["base_width_mm"] == "32"
    assert footprints[1]["footprint_status"] == "review"
    assert footprints[1]["base_width_mm"] == "40"
    assert reviews[0]["review_category"] == "mixed_or_multi_base_unit"


def test_match_unit_footprints_handles_apostrophes_plural_names_and_overrides():
    units = [
        {
            "unit_id": "belakor",
            "faction": "Chaos - Daemons Library",
            "name": "Be'lakor",
            "selection_type": "model",
            "models_min": "1",
            "models_max": "1",
        },
        {
            "unit_id": "walkers",
            "faction": "Aeldari - Aeldari Library",
            "name": "War Walkers",
            "selection_type": "unit",
            "models_min": "1",
            "models_max": "2",
        },
        {
            "unit_id": "custom",
            "faction": "Test Faction",
            "name": "Custom Unit",
            "selection_type": "model",
            "models_min": "1",
            "models_max": "1",
        },
    ]
    guide = [
        {
            "guide_faction": "CHAOS DAEMONS",
            "guide_unit_name": "Belakor",
            "guide_model_name": "",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "100",
            "base_depth_mm": "100",
        },
        {
            "guide_faction": "AELDARI",
            "guide_unit_name": "War Walker",
            "guide_model_name": "",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "60",
            "base_depth_mm": "60",
        },
    ]
    overrides = [
        {
            "unit_id": "custom",
            "base_size_text": "50mm",
            "guide_faction": "TEST",
            "guide_unit_name": "Custom Unit",
            "review_reason": "Manual local test override.",
        }
    ]

    footprints, reviews = match_unit_footprints(units, guide, override_rows=overrides)

    assert footprints[0]["base_width_mm"] == "100"
    assert footprints[1]["base_width_mm"] == "60"
    assert footprints[2]["footprint_status"] == "override"
    assert footprints[2]["base_width_mm"] == "50"
    assert reviews == []


def test_unit_name_keys_adds_singular_variant():
    assert "war walker" in unit_name_keys("War Walkers")
    assert "sydonian dragoon taser lance" in unit_name_keys("Sydonian Dragoons with Taser Lances")
    assert "ancient in terminator armor" in unit_name_keys("Ancient in Terminator Armour")
    assert "sword brethren" in unit_name_keys("Sword Brethren Squad")


def test_faction_compatible_handles_bsdata_library_catalogues():
    assert faction_compatible("DRUKHARI", "Aeldari - Aeldari Library")
    assert faction_compatible("WORLD EATERS", "Chaos - Chaos Space Marines")
    assert faction_compatible("EMPEROR’S CHILDREN", "Chaos - Chaos Space Marines")
    assert faction_compatible("DEATHWATCH", "Imperium - Agents of the Imperium")
    assert faction_compatible("ADEPTUS TITANICUS", "Library - Titans")


def test_build_footprint_suggestions_for_unmatched_units():
    units = [
        {
            "unit_id": "autarch-bike",
            "faction": "Aeldari - Aeldari Library",
            "name": "Autarch Skyrunner",
            "selection_type": "model",
            "models_min": "1",
            "models_max": "1",
        }
    ]
    guide = [
        {
            "guide_faction": "AELDARI",
            "guide_unit_name": "Farseer Skyrunner",
            "guide_model_name": "",
            "base_size_text": "Small Flying Base",
            "base_type": "small_flying_base",
            "base_shape": "flying",
            "base_width_mm": "",
            "base_depth_mm": "",
        },
        {
            "guide_faction": "AELDARI",
            "guide_unit_name": "Autarch",
            "guide_model_name": "",
            "base_size_text": "32mm",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "32",
            "base_depth_mm": "32",
        },
    ]
    footprints = [
        {
            "unit_id": "autarch-bike",
            "footprint_status": "unmatched",
        }
    ]

    suggestions = build_footprint_suggestions(units, guide, footprints, min_score=0.1)

    assert suggestions
    assert suggestions[0]["unit_name"] == "Autarch Skyrunner"
    assert suggestions[0]["guide_faction"] == "AELDARI"
    assert suggestions[0]["suggestion_score"]


def test_accepted_override_rows_from_suggestions_filters_reviewed_rank_and_score():
    suggestions = [
        {
            "unit_id": "safe",
            "unit_name": "Ancient in Terminator Armor",
            "faction": "Imperium - Adeptus Astartes",
            "suggestion_rank": "1",
            "suggestion_score": "0.97",
            "suggestion_reason": "name similarity 1.00; faction compatible",
            "guide_faction": "SPACE MARINES",
            "guide_unit_name": "Ancient in Terminator Armour",
            "base_size_text": "40mm",
            "base_type": "round",
            "base_shape": "round",
            "base_width_mm": "40",
            "base_depth_mm": "40",
        },
        {
            "unit_id": "low",
            "unit_name": "Loose Match",
            "faction": "Imperium",
            "suggestion_rank": "1",
            "suggestion_score": "0.61",
            "guide_unit_name": "Other Unit",
        },
    ]

    accepted = accepted_override_rows_from_suggestions(suggestions, [], min_score=0.9)

    assert [row["unit_id"] for row in accepted] == ["safe"]
    assert accepted[0]["guide_unit_name"] == "Ancient in Terminator Armour"
    assert accepted[0]["base_width_mm"] == "40"
    assert "Accepted footprint suggestion" in accepted[0]["review_reason"]


def test_rejected_rows_from_suggestions_filter_future_candidates():
    suggestions = [
        {
            "unit_id": "unsafe",
            "unit_name": "Captain on Bike",
            "faction": "Imperium - Adeptus Astartes",
            "suggestion_rank": "1",
            "suggestion_score": "0.88",
            "guide_faction": "SPACE MARINES",
            "guide_unit_name": "Chaplain on Bike",
            "base_size_text": "90x52.5mm Oval Base",
        }
    ]
    rejected = rejected_rows_from_suggestions(suggestions, [], min_score=0.8, reason="Different datasheet.")

    assert rejected[0]["unit_id"] == "unsafe"
    assert rejected[0]["decision"] == "rejected"
    assert rejected[0]["review_reason"] == "Different datasheet."

    units = [
        {
            "unit_id": "unsafe",
            "faction": "Imperium - Adeptus Astartes",
            "name": "Captain on Bike",
            "selection_type": "model",
            "models_min": "1",
            "models_max": "1",
        }
    ]
    guide = [
        {
            "guide_faction": "SPACE MARINES",
            "guide_unit_name": "Chaplain on Bike",
            "guide_model_name": "",
            "base_size_text": "90x52.5mm Oval Base",
            "base_type": "oval",
            "base_shape": "oval",
            "base_width_mm": "90",
            "base_depth_mm": "52.5",
        }
    ]
    footprints = [{"unit_id": "unsafe", "footprint_status": "unmatched"}]

    assert build_footprint_suggestions(units, guide, footprints, min_score=0.1, rejection_rows=rejected) == []


def test_build_footprint_override_template_prefills_unmatched_units_and_suggestion_context():
    review_rows = [
        {
            "review_category": "unmatched_unit",
            "unit_id": "missing",
            "unit_name": "Missing Base",
            "faction": "Test Faction",
            "selection_type": "model",
            "models_min": "1",
            "models_max": "1",
        },
        {
            "review_category": "non_numeric_base",
            "unit_id": "hull",
            "unit_name": "Hull Unit",
            "faction": "Test Faction",
        },
    ]
    suggestions = [
        {
            "unit_id": "missing",
            "suggestion_rank": "1",
            "suggestion_score": "0.72",
            "suggestion_reason": "similar",
            "guide_faction": "TEST",
            "guide_unit_name": "Suggested Unit",
            "base_size_text": "40mm",
        }
    ]

    template = build_footprint_override_template(review_rows, suggestions)

    assert len(template) == 1
    assert template[0]["unit_id"] == "missing"
    assert template[0]["faction_contains"] == "Test Faction"
    assert template[0]["suggested_guide_unit_name"] == "Suggested Unit"
    assert template[0]["override_base_size_text"] == ""


def test_build_footprint_review_queue_prioritizes_reviewable_suggestions():
    template = [
        {
            "unit_id": "none",
            "unit_name": "No Suggestion",
            "faction_contains": "Test",
        },
        {
            "unit_id": "medium",
            "unit_name": "Medium Suggestion",
            "faction_contains": "Test",
            "models_max": "10",
            "suggestion_score": "0.70",
            "suggested_guide_unit_name": "Medium Official",
            "suggested_base_size_text": "32mm",
        },
        {
            "unit_id": "high",
            "unit_name": "High Suggestion",
            "faction_contains": "Test",
            "models_max": "1",
            "suggestion_score": "0.81",
            "suggested_guide_unit_name": "High Official",
            "suggested_base_size_text": "40mm",
        },
        {
            "unit_id": "decided",
            "unit_name": "Decided",
            "faction_contains": "Test",
            "suggestion_score": "0.95",
            "review_decision": "reject",
        },
    ]

    queue = build_footprint_review_queue(template)

    assert [row["unit_id"] for row in queue] == ["high", "medium", "none"]
    assert queue[0]["review_rank"] == "1"
    assert queue[0]["review_priority"] == "review_suggestion_high"
    assert "accept_suggestion" in queue[0]["review_hint"]
    assert queue[-1]["review_priority"] == "no_suggestion"
    assert "override_*" in queue[-1]["review_hint"]


def test_build_footprint_review_queue_filters_faction_and_limits_rows():
    template = [
        {"unit_id": "ork", "unit_name": "Ork", "faction_contains": "Xenos - Orks", "suggestion_score": "0.70"},
        {"unit_id": "marine", "unit_name": "Marine", "faction_contains": "Imperium - Space Marines", "suggestion_score": "0.80"},
    ]

    queue = build_footprint_review_queue(template, faction_contains="orks", limit=1)

    assert [row["unit_id"] for row in queue] == ["ork"]


def test_accepted_override_rows_from_template_promotes_reviewed_rows_only():
    template = [
        {
            "unit_id": "suggested",
            "unit_name": "Suggested Unit",
            "faction_contains": "Test Faction",
            "suggestion_score": "0.81",
            "suggestion_reason": "name similarity 0.80; faction compatible",
            "suggested_guide_faction": "TEST",
            "suggested_guide_unit_name": "Official Suggested Unit",
            "suggested_base_size_text": "40mm",
            "review_decision": "accept_suggestion",
            "review_notes": "Checked official PDF.",
        },
        {
            "unit_id": "manual",
            "unit_name": "Manual Unit",
            "faction_contains": "Test Faction",
            "override_base_size_text": "90x52.5mm Oval Base",
            "override_guide_faction": "TEST",
            "override_guide_unit_name": "Manual Official Unit",
            "review_decision": "override",
        },
        {
            "unit_id": "blank",
            "unit_name": "Blank Decision",
            "suggested_base_size_text": "32mm",
        },
    ]

    accepted = accepted_override_rows_from_template(template, [])

    assert [row["unit_id"] for row in accepted] == ["suggested", "manual"]
    assert accepted[0]["base_width_mm"] == "40"
    assert accepted[0]["guide_unit_name"] == "Official Suggested Unit"
    assert "Checked official PDF" in accepted[0]["review_reason"]
    assert accepted[1]["base_shape"] == "oval"
    assert accepted[1]["base_depth_mm"] == "52.5"


def test_accepted_override_rows_from_template_accepts_review_queue_rows():
    queue_rows = [
        {
            "review_rank": "1",
            "review_priority": "review_suggestion_high",
            "review_hint": "Check whether this imported unit is the same datasheet.",
            "unit_id": "queued",
            "unit_name": "Queued Unit",
            "faction_contains": "Test Faction",
            "suggestion_score": "0.82",
            "suggestion_reason": "name similarity 0.82; faction compatible",
            "suggested_guide_faction": "TEST",
            "suggested_guide_unit_name": "Official Queued Unit",
            "suggested_base_size_text": "50mm",
            "review_decision": "accept_suggestion",
            "review_notes": "Reviewed from prioritized queue.",
        }
    ]

    accepted = accepted_override_rows_from_template(queue_rows, [])

    assert [row["unit_id"] for row in accepted] == ["queued"]
    assert accepted[0]["base_width_mm"] == "50"
    assert accepted[0]["guide_unit_name"] == "Official Queued Unit"
    assert "Reviewed from prioritized queue" in accepted[0]["review_reason"]


def test_accepted_override_rows_from_template_skips_existing_overrides():
    template = [
        {
            "unit_id": "existing",
            "unit_name": "Existing Unit",
            "override_base_size_text": "40mm",
            "review_decision": "override",
        }
    ]

    accepted = accepted_override_rows_from_template(template, [{"unit_id": "existing"}])

    assert accepted == []


def test_summarize_footprint_override_template_reports_invalid_reviewed_rows():
    template = [
        {
            "unit_id": "ready",
            "unit_name": "Ready Unit",
            "suggested_guide_unit_name": "Official Unit",
            "suggested_base_size_text": "40mm",
            "review_decision": "accept_suggestion",
        },
        {
            "unit_id": "bad-suggestion",
            "unit_name": "Bad Suggestion",
            "review_decision": "accept_suggestion",
        },
        {
            "unit_id": "bad-override",
            "unit_name": "Bad Override",
            "override_base_size_text": "unknown base",
            "review_decision": "override",
        },
        {
            "unit_id": "skipped",
            "unit_name": "Skipped Unit",
            "review_decision": "reject",
        },
        {
            "unit_id": "blank",
            "unit_name": "Blank Unit",
        },
    ]

    summary = summarize_footprint_override_template(template, [])

    assert summary["counts"]["accept_suggestion_ready"] == 1
    assert summary["counts"]["invalid"] == 2
    assert summary["counts"]["rejected"] == 1
    assert summary["counts"]["blank"] == 1
    assert [issue["unit_id"] for issue in summary["issues"]] == ["bad-suggestion", "bad-override"]


def test_generate_unit_footprint_artifacts_round_trips_csv(tmp_path):
    units_csv = tmp_path / "units.csv"
    units_csv.write_text(
        "unit_id,faction,name,selection_type,models_min,models_max\n"
        "boyz,Xenos - Orks,Boyz,unit,10,20\n",
        encoding="utf-8",
    )
    guide_csv = tmp_path / "base_size_guide.csv"
    guide_csv.write_text(
        "source,source_url,source_updated,page,guide_faction,guide_unit_name,guide_model_name,base_size_text,base_type,base_shape,base_width_mm,base_depth_mm\n"
        "guide,url,January 2026,42,ORKS,Boyz,,32mm,round,round,32,32\n",
        encoding="utf-8",
    )

    summary = generate_unit_footprint_artifacts(
        units_csv=units_csv,
        base_size_csv=guide_csv,
        unit_footprints_csv=tmp_path / "unit_footprints.csv",
        review_csv=tmp_path / "unit_footprint_review.csv",
        suggestions_csv=tmp_path / "unit_footprint_suggestions.csv",
        override_template_csv=tmp_path / "unit_footprint_override_template.csv",
        review_queue_csv=tmp_path / "unit_footprint_review_queue.csv",
    )

    assert summary["footprints"] == 1
    assert summary["override_template_rows"] == 0
    assert summary["review_queue_rows"] == 0
    assert "suggestion_score" in (tmp_path / "unit_footprint_suggestions.csv").read_text(encoding="utf-8")
    assert "override_base_size_text" in (tmp_path / "unit_footprint_override_template.csv").read_text(encoding="utf-8")
    assert "review_priority" in (tmp_path / "unit_footprint_review_queue.csv").read_text(encoding="utf-8")
    assert "matched" in (tmp_path / "unit_footprints.csv").read_text(encoding="utf-8")


def test_default_radius_uses_numeric_base_size_when_available():
    with_base = UnitProfile.from_dict(
        {
            "name": "Boyz",
            "toughness": 5,
            "save": "5+",
            "wounds": 1,
            "models_min": 10,
            "models_max": 10,
            "base_width_mm": "32",
            "base_depth_mm": "32",
        }
    )
    fallback = UnitProfile.from_dict(
        {
            "name": "Boyz",
            "toughness": 5,
            "save": "5+",
            "wounds": 1,
            "models_min": 10,
            "models_max": 10,
        }
    )

    assert default_radius(with_base) == 2.62
    assert default_radius(with_base) != default_radius(fallback)


def test_default_radius_uses_derived_non_numeric_base_estimates():
    small_flying = UnitProfile.from_dict(
        {
            "name": "Farseer Skyrunner",
            "toughness": 4,
            "save": "4+",
            "wounds": 5,
            "models_min": 1,
            "models_max": 1,
            "base_type": "small_flying_base",
        }
    )
    large_flying = UnitProfile.from_dict(
        {
            "name": "Falcon",
            "toughness": 9,
            "save": "3+",
            "wounds": 12,
            "models_min": 1,
            "models_max": 1,
            "base_type": "large_flying_base",
        }
    )
    hull = UnitProfile.from_dict(
        {
            "name": "Land Raider",
            "toughness": 12,
            "save": "2+",
            "wounds": 16,
            "models_min": 1,
            "models_max": 1,
            "base_type": "hull",
        }
    )

    assert footprint_dimensions_mm(small_flying) == (32.0, 32.0)
    assert default_radius(small_flying) == 0.83
    assert default_radius(large_flying) == 1.38
    assert default_radius(hull) == 2.8
