import pytest

from warhammer.profiles import UnitProfile
from warhammer.web_calculation import calculate_from_payload


def _unit(name, *, unit_id, weapons=None):
    return UnitProfile.from_dict(
        {
            "unit_id": unit_id,
            "name": name,
            "toughness": 4,
            "save": "3+",
            "wounds": 2,
            "points": 100,
            "models_min": 1,
            "models_max": 1,
            "weapons": weapons
            or [
                {
                    "name": "Test Weapon",
                    "type": "ranged",
                    "attacks": "2",
                    "skill": "3+",
                    "strength": 4,
                    "ap": 0,
                    "damage": "1",
                }
            ],
        }
    )


class _Dataset:
    supported_rules_editions = ["10e"]

    def __init__(self, units):
        self.units_by_name = {unit.name.casefold(): unit for unit in units}
        self.units_by_id = {unit.unit_id: unit for unit in units}

    def require_unit(self, name="", *, unit_id=None):
        if unit_id:
            try:
                return self.units_by_id[unit_id]
            except KeyError:
                raise KeyError(unit_id)
        try:
            return self.units_by_name[name.casefold()]
        except KeyError:
            raise KeyError(name)


class _State:
    rules_edition = "10e"

    def __init__(self):
        self.dataset = _Dataset([
            _unit("Attacker", unit_id="a"),
            _unit("Defender", unit_id="d"),
        ])

    def dataset_for_edition(self, edition=None):
        if edition not in {None, "10e"}:
            raise ValueError("not loaded")
        return self.dataset

    def ml_model_for_edition(self, edition=None):
        return None


def test_calculate_from_payload_returns_matchup_payload():
    payload = calculate_from_payload(
        {
            "attacker_id": "a",
            "defender_id": "d",
            "mode": "ranged",
            "outgoing_multiplier": 2,
            "incoming_multiplier": 3,
        },
        state=_State(),
    )

    assert payload["attacker"]["id"] == "a"
    assert payload["defender"]["id"] == "d"
    assert payload["mode"] == "ranged"
    assert payload["multipliers"] == {"outgoing": 2, "incoming": 3}
    assert "ml_judgement" not in payload


def test_calculate_from_payload_rejects_invalid_mode():
    with pytest.raises(ValueError, match="mode"):
        calculate_from_payload(
            {"attacker_id": "a", "defender_id": "d", "mode": "psychic"},
            state=_State(),
        )


def test_calculate_from_payload_rejects_unknown_unit():
    with pytest.raises(KeyError):
        calculate_from_payload(
            {"attacker_id": "missing", "defender_id": "d", "mode": "ranged"},
            state=_State(),
        )
