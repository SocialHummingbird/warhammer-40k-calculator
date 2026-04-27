from warhammer.edition_readiness import render_edition_readiness_report


def test_render_edition_readiness_report_marks_ready_edition():
    report = render_edition_readiness_report(
        {
            "edition": "10e",
            "status": "ready",
            "calculations_enabled": True,
            "rules_available": True,
            "supported_rules_editions": ["10e"],
            "data_dir": "data/10e/latest",
            "counts": {"units": 1, "weapons": 2},
            "audit_summary": {"error": 0, "warning": 1, "info": 0, "total": 1},
            "rule_capabilities": [
                {"key": "hit_rolls", "label": "Hit rolls", "status": "implemented", "notes": []}
            ],
            "blockers": [],
            "source": {"commit": "abc"},
        }
    )

    assert report.startswith("# Edition Readiness Report")
    assert "Edition: `10e`" in report
    assert "Calculations enabled: yes" in report
    assert "Ruleset Capability Coverage" in report
    assert "| Hit rolls | implemented |  |" in report
    assert "- [x] Ruleset module exists" in report
    assert "- None" in report


def test_render_edition_readiness_report_lists_future_edition_work():
    report = render_edition_readiness_report(
        {
            "edition": "11e",
            "status": "blocked",
            "calculations_enabled": False,
            "rules_available": False,
            "supported_rules_editions": ["10e"],
            "counts": {"units": 3},
            "audit_summary": {"error": 2, "warning": 0, "info": 0, "total": 2},
            "blockers": ["Ruleset not implemented", "Audit has 2 error samples"],
        }
    )

    assert "Edition: `11e`" in report
    assert "Ruleset not implemented" in report
    assert "No registered ruleset capabilities" in report
    assert "- [ ] Ruleset module exists" in report
    assert "Add focused parity tests" in report
    assert "keep it separate from `10e` data" in report


def test_render_edition_readiness_report_can_use_project_relative_path(tmp_path):
    data_dir = tmp_path / "data" / "10e" / "latest"
    data_dir.mkdir(parents=True)

    report = render_edition_readiness_report(
        {
            "edition": "10e",
            "status": "ready",
            "calculations_enabled": True,
            "rules_available": True,
            "data_dir": str(data_dir),
            "audit_summary": {"error": 0},
        },
        project_root=tmp_path,
    )

    assert "Data directory: `data/10e/latest`" in report
