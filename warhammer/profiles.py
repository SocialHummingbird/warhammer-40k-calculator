from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .dice import Quantity, RawQuantity, parse_quantity


_VALID_WEAPON_TYPES = {"ranged", "melee"}
_REROLL_OPTIONS = {"none", "ones", "all"}


@dataclass
class WeaponProfile:
    name: str
    type: str
    attacks: Quantity
    skill: int
    skill_label: str
    strength: int
    ap: int
    damage: Quantity
    reroll_hits: str = "none"
    reroll_wounds: str = "none"
    lethal_hits: bool = False
    sustained_hits: int = 0
    devastating_wounds: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> "WeaponProfile":
        name = data["name"]
        weapon_type = data.get("type", "ranged").lower()
        if weapon_type not in _VALID_WEAPON_TYPES:
            raise ValueError(f"Unsupported weapon type '{data['type']}'. Use 'ranged' or 'melee'.")

        attacks = parse_quantity(data["attacks"])
        damage = parse_quantity(data["damage"])
        skill_value, skill_label = _parse_roll_value(data.get("skill"), field_name="skill", max_allowed=6)

        return cls(
            name=name,
            type=weapon_type,
            attacks=attacks,
            skill=skill_value,
            skill_label=skill_label,
            strength=int(data["strength"]),
            ap=int(data.get("ap", 0)),
            damage=damage,
            reroll_hits=_parse_reroll_option(data.get("reroll_hits")),
            reroll_wounds=_parse_reroll_option(data.get("reroll_wounds")),
            lethal_hits=_parse_bool_flag(data.get("lethal_hits")),
            sustained_hits=_parse_sustained_hits(data.get("sustained_hits")),
            devastating_wounds=_parse_bool_flag(data.get("devastating_wounds")),
        )


@dataclass
class AbilityProfile:
    name: str
    text: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "AbilityProfile":
        if "name" not in data:
            raise ValueError("Ability requires a 'name'")
        return cls(name=data["name"], text=data.get("text", ""))


@dataclass
class UnitProfile:
    name: str
    toughness: int
    save: int
    save_label: str
    wounds: int
    invulnerable_save: Optional[int] = None
    invulnerable_label: Optional[str] = None
    feel_no_pain: Optional[int] = None
    feel_no_pain_label: Optional[str] = None
    damage_cap: Optional[float] = None
    weapons: List[WeaponProfile] = field(default_factory=list)
    abilities: List[AbilityProfile] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> "UnitProfile":
        save_value, save_label = _parse_roll_value(data.get("save"), field_name="save", max_allowed=7)
        invul_value, invul_label = _parse_optional_roll_value(
            data.get("invulnerable_save"), field_name="invulnerable_save", max_allowed=6
        )
        fnp_value, fnp_label = _parse_optional_roll_value(
            data.get("feel_no_pain"), field_name="feel_no_pain", max_allowed=6
        )

        weapons = [WeaponProfile.from_dict(w) for w in data.get("weapons", [])]
        abilities = [AbilityProfile.from_dict(a) for a in data.get("abilities", [])]
        keywords = [str(keyword) for keyword in data.get("keywords", [])]

        return cls(
            name=data["name"],
            toughness=int(data["toughness"]),
            save=save_value,
            save_label=save_label,
            wounds=int(data.get("wounds", 1)),
            invulnerable_save=invul_value,
            invulnerable_label=invul_label,
            feel_no_pain=fnp_value,
            feel_no_pain_label=fnp_label,
            damage_cap=_parse_damage_cap(data.get("damage_cap")),
            weapons=weapons,
            abilities=abilities,
            keywords=keywords,
        )


def load_units(raw_units: Iterable[Dict]) -> List[UnitProfile]:
    return [UnitProfile.from_dict(entry) for entry in raw_units]


def _parse_roll_value(value: RawQuantity, *, field_name: str, max_allowed: int) -> Tuple[int, str]:
    if value is None:
        raise ValueError(f"Missing required field '{field_name}'")

    if isinstance(value, (int, float)):
        roll = int(value)
    elif isinstance(value, str):
        cleaned = value.strip().upper()
        if cleaned.endswith('+'):
            cleaned = cleaned[:-1]
        if not cleaned.isdigit():
            raise ValueError(f"Invalid {field_name} value: {value}")
        roll = int(cleaned)
    else:
        raise ValueError(f"Unsupported type for {field_name}: {type(value)!r}")

    roll = _clamp_roll(roll, max_allowed=max_allowed)
    return roll, f"{roll}+"


def _parse_optional_roll_value(value: RawQuantity, *, field_name: str, max_allowed: int) -> Tuple[Optional[int], Optional[str]]:
    if value is None or value == "":
        return None, None
    roll, label = _parse_roll_value(value, field_name=field_name, max_allowed=max_allowed)
    return roll, label


def _parse_damage_cap(value: Optional[RawQuantity]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        try:
            return float(text)
        except ValueError:
            return None


def _parse_reroll_option(value: Optional[RawQuantity]) -> str:
    if value is None or value == "":
        return "none"
    text = str(value).strip().lower()
    if text in {"full", "all", "reroll_all"}:
        return "all"
    if text in {"ones", "reroll_ones", "1", "1s"}:
        return "ones"
    if text in _REROLL_OPTIONS:
        return text
    return "none"


def _parse_bool_flag(value: Optional[RawQuantity]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"", "no", "false", "0", "none"}:
        return False
    return True


def _parse_sustained_hits(value: Optional[RawQuantity]) -> int:
    if value is None or value == "":
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clamp_roll(value: int, *, max_allowed: int) -> int:
    minimum = 2
    maximum = max(6, max_allowed)

    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
    return value
