from warhammer.footprint_review import render_footprint_review_report, write_footprint_review_report


def test_render_footprint_review_report_groups_counts_and_suggestions(tmp_path):
    (tmp_path / "unit_footprints.csv").write_text(
        "\n".join(
            [
                "unit_id,unit_name,faction,footprint_status",
                "u1,Boyz,Xenos - Orks,matched",
                "u2,Legacy Captain,Imperium - Space Marines,unmatched",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_review.csv").write_text(
        "\n".join(
            [
                "review_severity,review_category,unit_id,unit_name,faction,footprint_status",
                "warning,unmatched_unit,u2,Legacy Captain,Imperium - Space Marines,unmatched",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_suggestions.csv").write_text(
        "\n".join(
            [
                "unit_id,faction,unit_name,suggestion_rank,suggestion_score,suggestion_reason,guide_unit_name,base_size_text,base_type",
                "u2,Imperium - Space Marines,Legacy Captain,1,0.91,similar,Captain,40mm,round",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_overrides.csv").write_text(
        "unit_id,unit_name\n",
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_override_template.csv").write_text(
        "\n".join(
            [
                "unit_id,unit_name,suggested_guide_unit_name,suggested_base_size_text,review_decision",
                "u2,Legacy Captain,Captain,40mm,accept_suggestion",
                "u3,Bad Row,,,accept_suggestion",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_review_queue.csv").write_text(
        "\n".join(
            [
                "review_rank,review_priority,unit_id,unit_name,faction_contains,suggested_guide_unit_name,suggested_base_size_text,suggested_source_page",
                "1,review_suggestion_high,u2,Legacy Captain,Imperium - Space Marines,Captain,40mm,42",
                "2,no_suggestion,u4,Mystery Unit,Xenos - Orks,,,",
            ]
        ),
        encoding="utf-8",
    )

    report = render_footprint_review_report(tmp_path)

    assert "# Unit Footprint Review" in report
    assert "- Footprint rows: 2" in report
    assert "- Rejected suggestions: 0" in report
    assert "- Override template rows: 2" in report
    assert "- Prioritized review queue rows: 2" in report
    assert "- unmatched: 1" in report
    assert "Non-Numeric Footprint Estimates" in report
    assert "Legacy Captain" in report
    assert "accept_footprint_suggestions.py" in report
    assert "promote_footprint_override_template.py" in report
    assert "review_decision" in report
    assert "Override Template Review Status" in report
    assert "- Suggestion-ready rows: 1" in report
    assert "- Invalid reviewed rows: 1" in report
    assert "Prioritized Manual Review Queue" in report
    assert "- review_suggestion_high: 1" in report
    assert "| 1 | review_suggestion_high | Legacy Captain | Imperium - Space Marines | Captain | 40mm | 42 |" in report
    assert "verify same datasheet" in report
    assert "research base and fill override fields" in report
    assert "plan_footprint_review.py" in report


def test_write_footprint_review_report_defaults_to_data_dir(tmp_path):
    output = write_footprint_review_report(tmp_path)

    assert output == tmp_path / "unit_footprint_review.md"
    assert output.exists()


def test_render_footprint_review_report_honours_row_limit(tmp_path):
    (tmp_path / "unit_footprints.csv").write_text("unit_id,unit_name,faction,footprint_status\n", encoding="utf-8")
    (tmp_path / "unit_footprint_review.csv").write_text("review_severity,review_category,unit_id,unit_name,faction\n", encoding="utf-8")
    (tmp_path / "unit_footprint_overrides.csv").write_text("unit_id,unit_name\n", encoding="utf-8")
    (tmp_path / "unit_footprint_override_template.csv").write_text("unit_id,unit_name,review_decision\n", encoding="utf-8")
    (tmp_path / "unit_footprint_suggestions.csv").write_text(
        "\n".join(
            [
                "unit_id,faction,unit_name,suggestion_rank,suggestion_score,suggestion_reason,guide_unit_name,base_size_text,base_type",
                "u1,Faction,First,1,0.91,similar,First Guide,40mm,round",
                "u2,Faction,Second,1,0.90,similar,Second Guide,50mm,round",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "unit_footprint_review_queue.csv").write_text(
        "\n".join(
            [
                "review_rank,review_priority,unit_id,unit_name,faction_contains,suggested_guide_unit_name,suggested_base_size_text,suggested_source_page",
                "1,review_suggestion_high,u1,First,Faction,First Guide,40mm,10",
                "2,review_suggestion_high,u2,Second,Faction,Second Guide,50mm,11",
            ]
        ),
        encoding="utf-8",
    )

    report = render_footprint_review_report(tmp_path, row_limit=1)

    assert "First" in report
    assert "Second" not in report
    assert "1 additional high-confidence suggestions omitted" in report
    assert "1 additional queue rows omitted" in report
