from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Optional, Tuple

from .dice import Quantity, RawQuantity, parse_quantity


def _parse_int_default(value: RawQuantity, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    if text.lower() in {"-", "n/a", "na", "none"}:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _parse_strength_quantity(value: RawQuantity) -> Quantity:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("+") and cleaned[:-1].isdigit():
            return parse_quantity(cleaned[:-1])
    return parse_quantity(value)


_VALID_WEAPON_TYPES = {"ranged", "melee"}
_REROLL_OPTIONS = {"none", "ones", "all"}


@dataclass
class AbilityModifier:
    hit_modifier: int = 0
    wound_modifier: int = 0
    reroll_hits: str = "none"
    reroll_wounds: str = "none"
    grant_twin_linked: bool = False
    grant_torrent: bool = False
    grant_blast: bool = False
    grant_assault: bool = False
    anti_rules: List[Tuple[str, int]] = field(default_factory=list)
    ignores_cover: bool = False
    applies_to_ranged: bool = True
    applies_to_melee: bool = True
    target_keywords: set[str] = field(default_factory=set)
    source: str = ""
    description: str = ""

    def applies_to(self, weapon_type: str, defender_keywords: set[str]) -> bool:
        if weapon_type == "ranged" and not self.applies_to_ranged:
            return False
        if weapon_type == "melee" and not self.applies_to_melee:
            return False
        if not self.target_keywords:
            return True
        return bool(self.target_keywords & defender_keywords)


_ABILITY_KEYWORDS = {
    "infantry",
    "vehicle",
    "monster",
    "character",
    "titanic",
    "walker",
    "swarm",
    "beast",
    "cavalry",
    "psyker",
    "fly",
    "daemon",
    "bike",
    "biker",
}


def _extract_keywords_from_text(text: str) -> set[str]:
    lower = text.lower()
    return {kw for kw in _ABILITY_KEYWORDS if kw in lower}


def _detect_attack_scope(text: str) -> tuple[bool, bool]:
    lower = text.lower()
    mentions_melee = any(phrase in lower for phrase in ("melee weapon", "melee attack", "melee weapons", "melee attacks"))
    mentions_ranged = any(phrase in lower for phrase in ("ranged weapon", "shooting attack", "shooting attacks", "ranged attacks"))
    applies_to_melee = True
    applies_to_ranged = True
    if mentions_melee and not mentions_ranged:
        applies_to_ranged = False
    if mentions_ranged and not mentions_melee:
        applies_to_melee = False
    return applies_to_ranged, applies_to_melee


def _parse_modifier_from_ability(text: str) -> tuple[int, int]:
    normalized = text.lower().replace("hit and wound rolls", "hit rolls and wound rolls")
    hit_mod = 0
    wound_mod = 0

    for match in re.finditer(r"(add|subtract)\s+(\d+)\s+(?:to|from)\s+(?:the\s+)?hit roll[s]?", normalized):
        value = int(match.group(2))
        if match.group(1).startswith("subtract"):
            value = -value
        hit_mod += value

    for match in re.finditer(r"(add|subtract)\s+(\d+)\s+(?:to|from)\s+(?:the\s+)?wound roll[s]?", normalized):
        value = int(match.group(2))
        if match.group(1).startswith("subtract"):
            value = -value
        wound_mod += value

    return hit_mod, wound_mod


def _parse_reroll_from_ability(text: str) -> tuple[str, str]:
    lower = text.lower().replace("re-roll", "reroll")

    reroll_hits = "none"
    reroll_wounds = "none"

    if "reroll hit rolls" in lower:
        if "reroll hit rolls of 1" in lower:
            reroll_hits = "ones"
        else:
            reroll_hits = "all"
    if "reroll wound rolls" in lower:
        if "reroll wound rolls of 1" in lower:
            reroll_wounds = "ones"
        else:
            reroll_wounds = "all"
    return reroll_hits, reroll_wounds


def _detect_twin_linked(text: str) -> bool:
    normalized = text.lower().replace("twin linked", "twin-linked")
    return "twin-linked" in normalized


def _detect_ignore_cover(text: str) -> bool:
    lower = text.lower()
    if "ignore cover" in lower or "ignores cover" in lower:
        return True
    if "does not receive the benefit of cover" in lower:
        return True
    return False


def _detect_keyword_grant(text: str, keyword: str) -> bool:
    normalized = text.lower()
    keyword_lower = keyword.lower()
    phrases = [
        f"has the {keyword_lower} ability",
        f"has {keyword_lower} ability",
        f"that attack has the {keyword_lower} ability",
        f"gains the {keyword_lower} ability",
        f"gains {keyword_lower} ability",
        f"with the {keyword_lower} ability",
    ]
    if any(phrase in normalized for phrase in phrases):
        return True
    keyword_tag = f"[{keyword_lower.replace(' ', '-').upper()}]"
    if keyword_tag in text.upper():
        return True
    return False


_ANTI_PATTERN = re.compile(r"anti[-\s]+(?P<keywords>[a-zA-Z\s/,&]+)\s*(?P<threshold>[2-6])\s*\+", re.IGNORECASE)

_DAMAGE_REDUCTION_PATTERN = re.compile(
    r"(?:subtract|reduce)\s+(\d+(?:\.\d+)?)\s+(?:from\s+)?(?:the\s+)?damage\s+characteristic",
    re.IGNORECASE,
)
_DAMAGE_REDUCTION_LITERAL = re.compile(r"damage\s+reduction\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def _extract_anti_rules(text: str) -> List[Tuple[str, int]]:
    rules: List[Tuple[str, int]] = []
    for match in _ANTI_PATTERN.finditer(text):
        threshold = int(match.group("threshold"))
        raw_keywords = match.group("keywords")
        for keyword in re.split(r"[\/,&]", raw_keywords):
            cleaned = keyword.strip().lower()
            if cleaned:
                rules.append((cleaned, threshold))
    return rules


def _extract_damage_reduction_from_text(text: str) -> float:
    for pattern in (_DAMAGE_REDUCTION_PATTERN, _DAMAGE_REDUCTION_LITERAL):
        match = pattern.search(text)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                continue
    return 0.0


def _detect_advance_permissions(abilities: List["AbilityProfile"]) -> tuple[bool, bool]:
    advance_and_charge = False
    advance_and_shoot = False
    charge_phrases = (
        "advance and charge",
        "can declare a charge in a turn in which it advanced",
        "eligible to charge in a turn in which it advanced",
    )
    shoot_phrases = (
        "advance and shoot",
        "advance and still shoot",
        "shoot even if it advanced",
        "shoot even though it advanced",
        "shoot even after advancing",
        "shoot in a turn in which it advanced",
        "shoot as if it had not advanced",
        "make ranged attacks as if it had not advanced",
    )
    for ability in abilities:
        text = f"{ability.name}. {ability.text}" if ability.name else (ability.text or "")
        lower = text.lower()
        if not advance_and_charge and any(phrase in lower for phrase in charge_phrases):
            advance_and_charge = True
        if not advance_and_shoot and any(phrase in lower for phrase in shoot_phrases):
            advance_and_shoot = True
        if advance_and_charge and advance_and_shoot:
            break
    return advance_and_charge, advance_and_shoot



def _parse_ability_modifiers(abilities: List["AbilityProfile"]) -> List[AbilityModifier]:
    modifiers: List[AbilityModifier] = []
    for ability in abilities:
        text = ability.text or ""
        combined_text = f"{ability.name}. {text}" if ability.name else text
        hit_mod, wound_mod = _parse_modifier_from_ability(combined_text)
        reroll_hits, reroll_wounds = _parse_reroll_from_ability(combined_text)
        grant_twin_linked = _detect_twin_linked(combined_text)
        grant_torrent = _detect_keyword_grant(combined_text, "torrent")
        grant_blast = _detect_keyword_grant(combined_text, "blast")
        grant_assault = _detect_keyword_grant(combined_text, "assault")
        anti_rules = _extract_anti_rules(combined_text)
        ignores_cover = _detect_ignore_cover(combined_text)
        target_keywords = _extract_keywords_from_text(combined_text)
        applies_to_ranged, applies_to_melee = _detect_attack_scope(combined_text)

        if not any([
            hit_mod,
            wound_mod,
            reroll_hits != "none",
            reroll_wounds != "none",
            grant_twin_linked,
            grant_torrent,
            grant_blast,
            grant_assault,
            anti_rules,
            ignores_cover,
        ]):
            continue

        description_parts: List[str] = []
        if hit_mod:
            description_parts.append(f"{hit_mod:+d} to hit")
        if wound_mod:
            description_parts.append(f"{wound_mod:+d} to wound")
        if reroll_hits != "none":
            desc = "reroll hit rolls" if reroll_hits == "all" else "reroll hit rolls of 1"
            description_parts.append(desc)
        if reroll_wounds != "none":
            desc = "reroll wound rolls" if reroll_wounds == "all" else "reroll wound rolls of 1"
            description_parts.append(desc)
        if grant_twin_linked:
            description_parts.append("Twin-linked")
        if grant_torrent:
            description_parts.append("Torrent")
        if grant_blast:
            description_parts.append("Blast")
        if grant_assault:
            description_parts.append("Assault")
        if ignores_cover:
            description_parts.append("Ignore Cover")
        if anti_rules:
            description_parts.append(
                "Anti-" + "/".join(sorted(f"{keyword.upper()} {threshold}+" for keyword, threshold in anti_rules))
            )
        if target_keywords:
            description_parts.append("vs " + "/".join(sorted(k.upper() for k in target_keywords)))

        description = ability.name or "Ability modifier"
        if description_parts:
            description = f"{ability.name or 'Ability'}: " + ", ".join(description_parts)

        modifiers.append(
            AbilityModifier(
                hit_modifier=hit_mod,
                wound_modifier=wound_mod,
                reroll_hits=reroll_hits,
                reroll_wounds=reroll_wounds,
                grant_twin_linked=grant_twin_linked,
                grant_torrent=grant_torrent,
                grant_blast=grant_blast,
                grant_assault=grant_assault,
                anti_rules=anti_rules,
                ignores_cover=ignores_cover,
                applies_to_ranged=applies_to_ranged,
                applies_to_melee=applies_to_melee,
                target_keywords=target_keywords,
                source=ability.name,
                description=description,
            )
        )
    return modifiers


@dataclass
class WeaponProfile:
    name: str
    type: str
    attacks: Quantity
    skill: int
    skill_label: str
    strength: int
    strength_label: str
    ap: int
    damage: Quantity
    keywords: List[str] = field(default_factory=list)
    hit_modifier: int = 0
    wound_modifier: int = 0
    reroll_hits: str = "none"
    reroll_wounds: str = "none"
    lethal_hits: bool = False
    sustained_hits: int = 0
    devastating_wounds: bool = False
    auto_hits: bool = False
    assault: bool = False
    heavy: bool = False
    torrent: bool = False
    twin_linked: bool = False
    ignores_cover: bool = False
    blast: bool = False
    melta: Optional[int] = None
    rapid_fire: Optional[int] = None
    anti_rules: List[Tuple[str, int]] = field(default_factory=list)
    range_inches: Optional[float] = None
    source_file: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "WeaponProfile":
        name = data["name"]
        weapon_type = data.get("type", "ranged").lower()
        if weapon_type not in _VALID_WEAPON_TYPES:
            raise ValueError(f"Unsupported weapon type '{data['type']}'. Use 'ranged' or 'melee'.")

        attacks = parse_quantity(data["attacks"])
        strength = _parse_strength_quantity(data.get("strength", 0))
        damage = parse_quantity(data["damage"])

        raw_skill = data.get("skill")
        auto_hits = False
        if isinstance(raw_skill, str):
            cleaned = raw_skill.strip().lower()
            if cleaned in {"auto", "automatic", "n/a", "na", "-", "none"}:
                auto_hits = True
                skill_value = 2
                skill_label = "Auto"
            else:
                skill_value, skill_label = _parse_roll_value(raw_skill, field_name="skill", max_allowed=6)
        else:
            skill_value, skill_label = _parse_roll_value(raw_skill or "6+", field_name="skill", max_allowed=6)

        raw_keywords = data.get("keywords") or []
        keywords = _normalise_weapon_keywords(raw_keywords)
        keyword_flags = _interpret_weapon_keywords(keywords)

        reroll_hits = _parse_reroll_option(data.get("reroll_hits"))
        reroll_wounds = _parse_reroll_option(data.get("reroll_wounds"))
        if keyword_flags["twin_linked"] and reroll_wounds == "none":
            reroll_wounds = "all"
        auto_hits = auto_hits or keyword_flags["torrent"]

        return cls(
            name=name,
            type=weapon_type,
            attacks=attacks,
            skill=skill_value,
            skill_label=skill_label,
            strength=int(round(strength.average)),
            strength_label=strength.label,
            ap=_parse_int_default(data.get("ap", 0), default=0),
            damage=damage,
            keywords=keywords,
            hit_modifier=_parse_int_default(data.get("hit_modifier"), default=0),
            wound_modifier=_parse_int_default(data.get("wound_modifier"), default=0),
            reroll_hits=reroll_hits,
            reroll_wounds=reroll_wounds,
            lethal_hits=_parse_bool_flag(data.get("lethal_hits")) or bool(keyword_flags["lethal_hits"]),
            sustained_hits=max(
                _parse_sustained_hits(data.get("sustained_hits")),
                int(keyword_flags["sustained_hits"]),
            ),
            devastating_wounds=(
                _parse_bool_flag(data.get("devastating_wounds"))
                or bool(keyword_flags["devastating_wounds"])
            ),
            auto_hits=auto_hits,
            assault=keyword_flags["assault"],
            heavy=keyword_flags["heavy"],
            torrent=keyword_flags["torrent"],
            twin_linked=keyword_flags["twin_linked"],
            ignores_cover=keyword_flags["ignores_cover"],
            blast=keyword_flags["blast"],
            melta=keyword_flags["melta"],
            rapid_fire=keyword_flags["rapid_fire"],
            anti_rules=keyword_flags["anti_rules"],
            range_inches=_parse_optional_float(data.get("range_inches") or data.get("range")),
            source_file=str(data.get("source_file") or ""),
        )

    def anti_threshold_for(self, defender_keywords: set[str]) -> Optional[int]:
        threshold: Optional[int] = None
        for keyword, value in self.anti_rules:
            if keyword in defender_keywords:
                threshold = value if threshold is None else min(threshold, value)
        return threshold


@dataclass
class AbilityProfile:
    name: str
    text: str = ""
    source_file: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "AbilityProfile":
        if "name" not in data:
            raise ValueError("Ability requires a 'name'")
        return cls(name=data["name"], text=data.get("text", ""), source_file=str(data.get("source_file") or ""))


@dataclass
class UnitProfile:
    name: str
    toughness: int
    save: int
    save_label: str
    wounds: int
    unit_id: Optional[str] = None
    move: Optional[float] = None
    invulnerable_save: Optional[int] = None
    invulnerable_label: Optional[str] = None
    feel_no_pain: Optional[int] = None
    feel_no_pain_label: Optional[str] = None
    damage_cap: Optional[float] = None
    points: Optional[int] = None
    models_min: Optional[int] = None
    models_max: Optional[int] = None
    faction: Optional[str] = None
    selection_type: Optional[str] = None
    leadership: Optional[int] = None
    objective_control: Optional[int] = None
    source_file: str = ""
    weapons: List[WeaponProfile] = field(default_factory=list)
    abilities: List[AbilityProfile] = field(default_factory=list)
    ability_modifiers: List[AbilityModifier] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    damage_reduction: float = 0.0
    can_advance_and_charge: bool = False
    can_advance_and_shoot: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> "UnitProfile":
        save_value, save_label = _parse_roll_value(data.get("save"), field_name="save", max_allowed=7)
        invul_value, invul_label = _parse_optional_roll_value(
            data.get("invulnerable_save"), field_name="invulnerable_save", max_allowed=6
        )
        fnp_value, fnp_label = _parse_optional_roll_value(
            data.get("feel_no_pain"), field_name="feel_no_pain", max_allowed=6
        )
        points_value = _parse_optional_int(data.get("points"))
        models_min = _parse_optional_int(data.get("models_min"))
        models_max = _parse_optional_int(data.get("models_max"))

        weapons = [WeaponProfile.from_dict(w) for w in data.get("weapons", [])]
        abilities = [AbilityProfile.from_dict(a) for a in data.get("abilities", [])]
        ability_modifiers = _parse_ability_modifiers(abilities) if abilities else []
        keywords = [str(keyword) for keyword in data.get("keywords", [])]
        damage_reduction = 0.0
        for ability in abilities:
            text = f"{ability.name}. {ability.text}" if ability.name else (ability.text or "")
            damage_reduction = max(damage_reduction, _extract_damage_reduction_from_text(text))

        advance_and_charge, advance_and_shoot = _detect_advance_permissions(abilities) if abilities else (False, False)

        return cls(
            name=data["name"],
            toughness=int(data["toughness"]),
            save=save_value,
            save_label=save_label,
            wounds=int(data.get("wounds", 1)),
            unit_id=(str(data.get("unit_id") or data.get("id")) if data.get("unit_id") or data.get("id") else None),
            move=_parse_optional_float(data.get("move")),
            invulnerable_save=invul_value,
            invulnerable_label=invul_label,
            feel_no_pain=fnp_value,
            feel_no_pain_label=fnp_label,
            damage_cap=_parse_damage_cap(data.get("damage_cap")),
            points=points_value,
            models_min=models_min,
            models_max=models_max,
            faction=data.get("faction"),
            selection_type=(str(data.get("selection_type")).lower() if data.get("selection_type") else None),
            leadership=_parse_optional_int(data.get("leadership")),
            objective_control=_parse_optional_int(data.get("objective_control")),
            source_file=str(data.get("source_file") or ""),
            weapons=weapons,
            abilities=abilities,
            ability_modifiers=ability_modifiers,
            keywords=keywords,
            damage_reduction=damage_reduction,
            can_advance_and_charge=advance_and_charge,
            can_advance_and_shoot=advance_and_shoot,
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


def _parse_optional_int(value: Optional[RawQuantity]) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return None
    return None

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

def _parse_optional_float(value: Optional[RawQuantity]) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text_value = str(value).strip().strip('"').strip("'")
    if not text_value:
        return None
    try:
        return float(text_value)
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


def _normalise_weapon_keywords(raw: object) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        tokens = re.split(r",|;", raw)
    elif isinstance(raw, (list, tuple, set)):
        tokens = []
        for item in raw:
            tokens.extend(re.split(r",|;", str(item)))
    else:
        return []
    return [token.strip() for token in tokens if token and token.strip()]


def _interpret_weapon_keywords(keywords: List[str]) -> Dict[str, object]:
    flags: Dict[str, object] = {
        "assault": False,
        "heavy": False,
        "torrent": False,
        "twin_linked": False,
        "ignores_cover": False,
        "blast": False,
        "melta": None,
        "rapid_fire": None,
        "anti_rules": [],
        "devastating_wounds": False,
        "lethal_hits": False,
        "sustained_hits": 0,
    }

    for keyword in keywords:
        lower = keyword.lower()
        if lower == "assault":
            flags["assault"] = True
        elif lower == "heavy":
            flags["heavy"] = True
        elif lower == "torrent":
            flags["torrent"] = True
        elif lower in {"twin-linked", "twin linked"}:
            flags["twin_linked"] = True
        elif "ignores cover" in lower or lower == "ignore cover":
            flags["ignores_cover"] = True
        elif lower == "blast":
            flags["blast"] = True
        elif lower == "devastating wounds":
            flags["devastating_wounds"] = True
        elif lower == "lethal hits":
            flags["lethal_hits"] = True

        anti_match = _ANTI_PATTERN.search(keyword)
        if anti_match:
            threshold = int(anti_match.group("threshold"))
            raw_targets = anti_match.group("keywords")
            for target in re.split(r"[\/,&]", raw_targets):
                target_clean = target.strip().lower()
                if target_clean:
                    flags.setdefault("anti_rules", []).append((target_clean, threshold))
            continue

        melta_match = re.search(r"melta\s*(\d+)?", lower)
        if melta_match:
            value = melta_match.group(1)
            flags["melta"] = int(value) if value else 2
            continue

        rapid_fire_match = re.search(r"rapid\s*fire\s*(\d+)?", lower)
        if rapid_fire_match:
            value = rapid_fire_match.group(1)
            flags["rapid_fire"] = int(value) if value else None
            continue

        sustained_hits_match = re.search(r"sustained\s*hits\s*(\d+)?", lower)
        if sustained_hits_match:
            value = sustained_hits_match.group(1)
            flags["sustained_hits"] = max(int(value), int(flags["sustained_hits"])) if value else 1
            continue

    if not isinstance(flags["anti_rules"], list):
        flags["anti_rules"] = []

    return flags


def _clamp_roll(value: int, *, max_allowed: int) -> int:
    minimum = 2
    maximum = max(6, max_allowed)

    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
    return value
