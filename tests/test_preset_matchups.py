import sys
import types
from pathlib import Path

import pytest

import preset_matchups


def test_normalise_presets_defaults_and_casefold():
    defaults = preset_matchups._normalise_presets(None)
    assert defaults == list(preset_matchups.LEGACY.PRESET_ORDER)

    first = preset_matchups.LEGACY.PRESET_ORDER[0]
    mixed = first.upper()
    assert preset_matchups._normalise_presets([mixed]) == [first]


def test_normalise_presets_unknown_raises():
    with pytest.raises(SystemExit, match="Unknown preset name"):
        preset_matchups._normalise_presets(["not-a-preset"])


def test_collect_fast_units_flags_speed():
    preset = preset_matchups.LEGACY.PRESET_ORDER[0]
    defender_name = preset_matchups.LEGACY.TARGET_PRESETS[preset][0]
    fast_defender = types.SimpleNamespace(
        name=defender_name,
        move=12.0,
        can_advance_and_charge=True,
    )
    highlights = preset_matchups._collect_fast_units(
        {defender_name: fast_defender},
        [preset],
    )
    assert preset in highlights
    entry = highlights[preset][0]
    assert defender_name in entry
    assert "Move 12" in entry
    assert "Advance+Charge" in entry


def test_main_preset_prints_fast_highlights(monkeypatch, tmp_path, capsys):
    preset = preset_matchups.LEGACY.PRESET_ORDER[0]
    defender_name = preset_matchups.LEGACY.TARGET_PRESETS[preset][0]
    attacker = types.SimpleNamespace(name="Speed Tester", move=6.0, can_advance_and_charge=False)
    fast_defender = types.SimpleNamespace(
        name=defender_name,
        move=12.0,
        can_advance_and_charge=True,
    )
    units = {attacker.name: attacker, defender_name: fast_defender}

    def fake_loader(csv_dir, data_path, prefer_faction):
        assert csv_dir == tmp_path
        return units

    monkeypatch.setattr(preset_matchups, "_load_units_from_sources", fake_loader)
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_dataset_metadata", lambda path: None)
    monkeypatch.setattr(preset_matchups.LEGACY, "_require_unit", lambda mapping, name: mapping[name])
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_attacker_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        preset_matchups.LEGACY,
        "_print_weapon_tables_for_presets",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(sys, "argv", [
        "preset_matchups.py",
        "--csv-dir",
        str(tmp_path),
        "--attacker",
        attacker.name,
        "--preset",
        preset,
        "--weapon-mode",
        "melee",
    ])

    preset_matchups.main()
    captured = capsys.readouterr().out
    assert "Fast defenders" in captured
    assert defender_name in captured
    assert "Move 12" in captured


def test_main_list_presets_prints_tables(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["preset_matchups.py", "--list-presets"])
    preset_matchups.main()
    captured = capsys.readouterr().out
    assert "Preset defender tables" in captured
    for preset in preset_matchups.LEGACY.PRESET_ORDER[:2]:
        assert preset in captured


def test_main_specific_attacker_invokes_table_builder(monkeypatch, tmp_path, capsys):
    stub_unit = types.SimpleNamespace(name="Test Unit")
    units = {stub_unit.name: stub_unit}

    def fake_loader(csv_dir, data_path, prefer_faction):
        assert csv_dir == tmp_path
        assert data_path is None
        assert prefer_faction is None
        return units

    monkeypatch.setattr(preset_matchups, "_load_units_from_sources", fake_loader)

    dataset_calls = []
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_dataset_metadata", lambda path: dataset_calls.append(path))

    def fake_require(units_map, name):
        assert units_map is units
        assert name == stub_unit.name
        return stub_unit

    monkeypatch.setattr(preset_matchups.LEGACY, "_require_unit", fake_require)

    summary_calls = []

    def fake_summary(attacker, weapon_mode, prefix):
        summary_calls.append((attacker.name, weapon_mode, prefix))

    monkeypatch.setattr(preset_matchups.LEGACY, "_print_attacker_summary", fake_summary)

    table_calls = []

    def fake_tables(units_map, attacker, presets, weapon_mode, ppm_basis, *, export_path=None, export_format="md"):
        table_calls.append(
            {
                "units": units_map,
                "attacker": attacker,
                "presets": presets,
                "weapon_mode": weapon_mode,
                "ppm_basis": ppm_basis,
                "export_path": export_path,
                "export_format": export_format,
            }
        )

    monkeypatch.setattr(preset_matchups.LEGACY, "_print_weapon_tables_for_presets", fake_tables)

    monkeypatch.setattr(sys, "argv", [
        "preset_matchups.py",
        "--csv-dir",
        str(tmp_path),
        "--attacker",
        stub_unit.name,
        "--weapon-mode",
        "melee",
        "--preset",
        "vehicles",
        "--ppm-basis",
        "average",
    ])

    preset_matchups.main()
    captured = capsys.readouterr().out
    assert "Attacker selected" in captured
    assert dataset_calls == [tmp_path]
    assert summary_calls == [(stub_unit.name, "melee", "Preset")]
    assert table_calls and table_calls[0]["presets"] == ["vehicles"]
    assert table_calls[0]["weapon_mode"] == "melee"
    assert table_calls[0]["ppm_basis"] == "average"


def test_select_fair_random_pair_filters_by_type_and_points(monkeypatch):
    preset_matchups.LEGACY.random.seed(0)

    def make_unit(name, points, keywords, weapon_types=('melee', 'ranged')):
        weapons = [types.SimpleNamespace(type=wt) for wt in weapon_types]
        return types.SimpleNamespace(
            name=name,
            points=points,
            keywords=keywords,
            models_min=1,
            models_max=1,
            weapons=weapons,
        )

    attacker = make_unit('Knight A', 400, ['Vehicle', 'Titanic'])
    close_match = make_unit('Knight B', 380, ['Vehicle', 'Titanic'])
    far_match = make_unit('Knight C', 310, ['Vehicle', 'Titanic'])
    infantry = make_unit('Infantry', 100, ['Infantry'])
    melee_only = make_unit('Melee Only', 120, ['Vehicle', 'Titanic'], ('melee',))

    units = {u.name: u for u in [attacker, close_match, far_match, infantry, melee_only]}

    chosen_attacker, chosen_defender = preset_matchups._select_fair_random_pair(
        units, required_modes=('melee',), max_point_delta=50.0
    )

    assert {chosen_attacker.name, chosen_defender.name} <= {attacker.name, close_match.name}
    assert chosen_attacker.name != chosen_defender.name
    assert preset_matchups._unit_supports_weapon_mode(chosen_attacker, 'melee')
    assert preset_matchups._unit_supports_weapon_mode(chosen_defender, 'melee')

    with pytest.raises(SystemExit):
        preset_matchups._select_fair_random_pair({attacker.name: attacker, infantry.name: infantry}, required_modes=('melee',), max_point_delta=10.0)




def test_main_random_fair_duel_calls_pair_selector(monkeypatch, tmp_path, capsys):
    fair_attacker = types.SimpleNamespace(
        name="Fair One",
        move=6.0,
        can_advance_and_charge=False,
        models_min=1,
        models_max=1,
        keywords=['Infantry'],
        weapons=[types.SimpleNamespace(type='melee'), types.SimpleNamespace(type='ranged')],
    )
    fair_defender = types.SimpleNamespace(
        name="Fair Two",
        move=7.0,
        can_advance_and_charge=True,
        models_min=1,
        models_max=1,
        keywords=['Infantry'],
        weapons=[types.SimpleNamespace(type='melee')],
    )
    units = {fair_attacker.name: fair_attacker, fair_defender.name: fair_defender}

    def fake_loader(csv_dir, data_path, prefer_faction):
        assert csv_dir == tmp_path
        return units

    monkeypatch.setattr(preset_matchups, "_load_units_from_sources", fake_loader)
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_dataset_metadata", lambda path: None)
    monkeypatch.setattr(preset_matchups.LEGACY, "_require_unit", lambda mapping, name: mapping[name])

    pair_calls = []

    def fake_pair_selector(units_map, required_modes, max_point_delta):
        pair_calls.append((required_modes, max_point_delta))
        return fair_attacker, fair_defender

    monkeypatch.setattr(preset_matchups, "_select_fair_random_pair", fake_pair_selector)

    table = {
        "name_header": ["Weapon/Target", fair_defender.name],
        "stats_header": ["Unit Stats", "T4 W3"],
        "_extra_header_rows": [["Points", "100pts"]],
        "rows": [["Blade", "1.0 / 0.5 / 10"]],
    }

    monkeypatch.setattr(preset_matchups.LEGACY, "_print_attacker_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(preset_matchups.LEGACY, "_build_weapon_table", lambda *args, **kwargs: table)
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_weapon_table_data", lambda tbl: None)

    monkeypatch.setattr(sys, "argv", [
        "preset_matchups.py",
        "--csv-dir",
        str(tmp_path),
        "--random-fair-duel",
        "--weapon-mode",
        "melee",
    ])

    preset_matchups.main()
    captured = capsys.readouterr().out
    assert "Random fair duel selected" in captured
    assert f"Duel: {fair_attacker.name} vs {fair_defender.name}" in captured
    assert pair_calls == [(('melee',), 40.0)]


def test_main_explain_triggers_ai_summary(monkeypatch, tmp_path, capsys):
    attacker = types.SimpleNamespace(name="Analysis Unit")
    defender = types.SimpleNamespace(name="Target Unit")
    units = {attacker.name: attacker, defender.name: defender}

    def fake_loader(csv_dir, data_path, prefer_faction):
        assert csv_dir == tmp_path
        return units

    monkeypatch.setattr(preset_matchups, "_load_units_from_sources", fake_loader)

    monkeypatch.setattr(preset_matchups.LEGACY, "_print_dataset_metadata", lambda path: None)

    def fake_require(units_map, name):
        return units_map[name]

    monkeypatch.setattr(preset_matchups.LEGACY, "_require_unit", fake_require)

    def fake_summary(attacker_unit, weapon_mode, prefix=""):
        preset_matchups._capture_line(f"{prefix}: {attacker_unit.name} ({weapon_mode})")

    monkeypatch.setattr(preset_matchups.LEGACY, "_print_attacker_summary", fake_summary)

    table = {
        "name_header": ["Weapon/Target", defender.name],
        "stats_header": ["Unit Stats", "T4 W3"],
        "_extra_header_rows": [["Points", "80pts"]],
        "rows": [["Test Blade", "1.0 / 1.0 / 10pts"]],
        "note": "Test note",
    }

    monkeypatch.setattr(preset_matchups.LEGACY, "_build_weapon_table", lambda *args, **kwargs: table)
    monkeypatch.setattr(preset_matchups.LEGACY, "_print_weapon_table_data", lambda tbl: preset_matchups._capture_line("Printed table"))

    monkeypatch.setattr(preset_matchups, "resolve_api_key", lambda: "test-key")

    create_calls = []

    class FakeResponses:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            class Response:
                output_text = "Mock AI summary"
            return Response()

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setattr(preset_matchups, "OpenAI", FakeClient)

    monkeypatch.setattr(sys, "argv", [
        "preset_matchups.py",
        "--csv-dir",
        str(tmp_path),
        "--attacker",
        attacker.name,
        "--defender",
        defender.name,
        "--weapon-mode",
        "ranged",
        "--explain",
        "--scenario",
        "realistic",
    ])

    preset_matchups.main()
    captured = capsys.readouterr().out
    assert "=== AI summary ===" in captured
    assert "Mock AI summary" in captured
    assert create_calls
    user_payload = create_calls[0]["input"][1]["content"]
    assert defender.name in user_payload
    assert "Printed table" in user_payload
    assert "Scenario context" in user_payload


