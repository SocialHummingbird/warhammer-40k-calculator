import pytest

from warhammer.api_payloads import (
    context_from_payload,
    contexts_from_payload,
    optional_unit_id,
    optional_weapon_name,
    query_limit,
)


def test_context_from_payload_normalises_values():
    context = context_from_payload(
        {
            "attacker_advanced": True,
            "target_model_count": "10",
            "target_in_cover": True,
        }
    )

    assert context.attacker_advanced is True
    assert context.attacker_moved is True
    assert context.target_model_count == 10
    assert context.target_in_cover is True


def test_context_from_payload_parses_string_booleans():
    context = context_from_payload(
        {
            "attacker_moved": "false",
            "attacker_advanced": "true",
            "target_within_half_range": "0",
            "target_in_cover": "1",
        }
    )

    assert context.attacker_moved is True
    assert context.attacker_advanced is True
    assert context.target_within_half_range is False
    assert context.target_in_cover is True


def test_context_from_payload_rejects_invalid_values():
    with pytest.raises(ValueError, match="target_model_count"):
        context_from_payload({"target_model_count": "0"})
    with pytest.raises(ValueError, match="attacker_moved"):
        context_from_payload({"attacker_moved": "sometimes"})


def test_contexts_from_payload_keeps_return_strike_independent():
    outgoing, incoming = contexts_from_payload(
        {
            "context": {
                "attacker_advanced": True,
                "target_in_cover": True,
            }
        }
    )

    assert outgoing.attacker_advanced is True
    assert outgoing.target_in_cover is True
    assert incoming.attacker_advanced is False
    assert incoming.target_in_cover is False


def test_contexts_from_payload_accepts_explicit_return_context():
    outgoing, incoming = contexts_from_payload(
        {
            "outgoing_context": {"target_within_half_range": True},
            "incoming_context": {"attacker_moved": True, "target_model_count": 3},
        }
    )

    assert outgoing.target_within_half_range is True
    assert incoming.attacker_moved is True
    assert incoming.target_model_count == 3


def test_optional_weapon_name_normalises_blank_and_all_values():
    assert optional_weapon_name("") is None
    assert optional_weapon_name("__all__") is None
    assert optional_weapon_name("  Bolt rifle ") == "Bolt rifle"
    with pytest.raises(ValueError, match="weapon filters"):
        optional_weapon_name(12)


def test_optional_unit_id_normalises_blank_values():
    assert optional_unit_id("") is None
    assert optional_unit_id("  abc ") == "abc"
    with pytest.raises(ValueError, match="unit ids"):
        optional_unit_id(12)


def test_query_limit_clamps_to_supported_range():
    assert query_limit("bad") == 300
    assert query_limit("0") == 1
    assert query_limit("2000") == 2000
    assert query_limit("25") == 25
