"""CSV row definitions for imported Warhammer data."""

from dataclasses import dataclass, asdict
from typing import Dict, Optional


@dataclass
class UnitRow:
    unit_id: str
    faction: str
    name: str
    toughness: Optional[int]
    save: Optional[str]
    invulnerable_save: Optional[str]
    wounds: Optional[int]
    leadership: Optional[str]
    objective_control: Optional[int]
    feel_no_pain: Optional[str] = None
    damage_cap: Optional[str] = None

    def asdict(self) -> Dict[str, Optional[str]]:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class WeaponRow:
    weapon_id: str
    unit_id: str
    name: str
    weapon_type: str
    attacks: str
    skill: str
    strength: str
    ap: str
    damage: str
    keywords: str
    reroll_hits: str = ""
    reroll_wounds: str = ""
    lethal_hits: str = ""
    sustained_hits: str = ""
    devastating_wounds: str = ""

    def asdict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class AbilityRow:
    ability_id: str
    source_type: str
    source_id: str
    name: str
    text: str

    def asdict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class KeywordRow:
    keyword_id: str
    keyword: str
    description: str

    def asdict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class UnitKeywordRow:
    unit_id: str
    keyword_id: str

    def asdict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items()}


UNIT_HEADERS = list(UnitRow.__annotations__.keys())
WEAPON_HEADERS = list(WeaponRow.__annotations__.keys())
ABILITY_HEADERS = list(AbilityRow.__annotations__.keys())
KEYWORD_HEADERS = list(KeywordRow.__annotations__.keys())
UNIT_KEYWORD_HEADERS = list(UnitKeywordRow.__annotations__.keys())
