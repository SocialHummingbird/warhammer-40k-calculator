import re
from collections import Counter
from dataclasses import dataclass
from typing import Tuple, Union


_DICE_PATTERN = re.compile(r'^\s*(?:(\d*)[dD](\d+))\s*(?:([+-])\s*(\d+(?:\.\d+)?))?\s*$')


@dataclass
class Quantity:
    """Represents a numeric quantity and the expression used to describe it."""

    label: str
    average: float


class QuantityParseError(ValueError):
    """Raised when a dice expression cannot be parsed."""


RawQuantity = Union[int, float, str]

# Common placeholders that can appear in catalogue fields
_PLACEHOLDERS = {"*", "-", "—", "n/a", "na", "N/A", "NA"}


def parse_quantity(value: RawQuantity) -> Quantity:
    """Parses dice expressions like 'D6+2' into their average value.

    Supports integers, floats, and dice notation of the form '2D6+3'. The
    returned "label" preserves the original expression for display purposes.
    Unknown or placeholder values are treated as 0.0.
    """

    if isinstance(value, (int, float)):
        return Quantity(label=str(value), average=float(value))

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise QuantityParseError('Empty quantity expression')

        # Tolerate common placeholders that appear in catalogues
        if cleaned in _PLACEHOLDERS or cleaned.lower() in _PLACEHOLDERS:
            return Quantity(label=cleaned, average=0.0)

        # Pure number stored as a string
        if _is_numeric(cleaned):
            return Quantity(label=cleaned, average=float(cleaned))

        match = _DICE_PATTERN.match(cleaned)
        if not match:
            raise QuantityParseError(f'Unsupported quantity expression: {value}')

        count_text, sides_text, sign_text, modifier_text = match.groups()
        count = int(count_text) if count_text else 1
        sides = int(sides_text)
        modifier = float(modifier_text) if modifier_text else 0.0
        if sign_text == '-':
            modifier = -modifier

        average = count * (sides + 1) / 2 + modifier
        return Quantity(label=cleaned.upper(), average=average)

    raise QuantityParseError(f'Unsupported quantity type: {type(value)!r}')


def quantity_distribution(value: RawQuantity) -> Tuple[Tuple[float, float], ...]:
    """Return outcome/probability pairs for a supported quantity expression."""

    if isinstance(value, (int, float)):
        return ((float(value), 1.0),)

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise QuantityParseError('Empty quantity expression')
        if cleaned in _PLACEHOLDERS or cleaned.lower() in _PLACEHOLDERS:
            return ((0.0, 1.0),)
        if _is_numeric(cleaned):
            return ((float(cleaned), 1.0),)

        match = _DICE_PATTERN.match(cleaned)
        if not match:
            raise QuantityParseError(f'Unsupported quantity expression: {value}')

        count_text, sides_text, sign_text, modifier_text = match.groups()
        count = int(count_text) if count_text else 1
        sides = int(sides_text)
        modifier = float(modifier_text) if modifier_text else 0.0
        if sign_text == '-':
            modifier = -modifier

        totals = Counter({0: 1})
        for _ in range(count):
            next_totals: Counter[int] = Counter()
            for subtotal, subtotal_count in totals.items():
                for face in range(1, sides + 1):
                    next_totals[subtotal + face] += subtotal_count
            totals = next_totals

        outcome_count = float(sides**count)
        return tuple((subtotal + modifier, hits / outcome_count) for subtotal, hits in sorted(totals.items()))

    raise QuantityParseError(f'Unsupported quantity type: {type(value)!r}')


def _is_numeric(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True
