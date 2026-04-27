import warhammer.calculator as calculator


def test_calculator_public_api_exports_compatibility_symbols():
    expected = {
        "DEFAULT_RULES_EDITION",
        "EngagementContext",
        "EngagementMode",
        "UnitResult",
        "WeaponResult",
        "evaluate_unit",
        "evaluate_weapon",
        "scale_unit_result",
        "scale_weapon_result",
    }

    assert set(calculator.__all__) == expected
    for name in expected:
        assert hasattr(calculator, name)
