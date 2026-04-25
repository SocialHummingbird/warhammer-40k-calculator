from __future__ import annotations

import re
from typing import Any

_DECIMAL_PATTERN = re.compile(
    r'(?<![\w%])(-?\d+(?:\.\d+)?)(?=(?:pts|PPM|[\s/,;:\)]|$))',
    re.IGNORECASE,
)

_BULLET_PREFIXES = ('➤', '▶', '►', '•', '●', '◆', '◇')

_ANTI_TAG_ABBREVIATIONS = {
    'character': 'CHAR',
    'epic hero': 'EPIC',
    'chaos': 'CHAO',
    'daemon': 'DAEM',
    'infantry': 'INFT',
    'monster': 'MONS',
    'psyker': 'PSYK',
    'titanic': 'TITN',
    'tyranids': 'TYRA',
    'vehicle': 'VEHC',
    'walker': 'WLKR',
    'fly': 'FLY',
}

_FIXED_KEYWORD_ABBREVIATIONS = {
    'assault': 'ASLT',
    'blast': 'BLST',
    'bubblechukka': 'BCHK',
    'conversion': 'CONV',
    'dead choppy': 'DCHP',
    'defensive array': 'DARR',
    'devastating wounds': 'DVW',
    'extra attacks': 'XATK',
    'hazardous': 'HZRD',
    'heavy': 'HVY',
    'hive defences': 'HDEF',
    'hooked': 'HOKD',
    'ignores cover': 'IGNCV',
    'impaled': 'IMPL',
    'indirect fire': 'INDF',
    'lance': 'LANC',
    'lethal hits': 'LTH',
    'linked fire': 'LNKF',
    'one shot': '1SHT',
    'overcharge': 'OVRG',
    'pistol': 'PSTL',
    'plasma warhead': 'PLWH',
    'precision': 'PREC',
    'psychic': 'PSYC',
    'psychic assassin': 'PSASN',
    'reverberating summons': 'RVRB',
    'snagged': 'SNAG',
    'sonic devastation': 'SNDV',
    'torrent': 'TORR',
    'twin linked': 'TL',
}


def _normalise_keyword(text: str) -> str:
    return re.sub(r'[\s-]+', ' ', text.strip().lower())


def _format_number(token: str) -> str:
    try:
        value = float(token)
    except ValueError:
        return token
    return f"{value:.3f}"


def normalise_weapon_label(label: str) -> str:
    text = label.lstrip()
    while text and text[0] in _BULLET_PREFIXES:
        text = text[1:].lstrip()
    return text


def abbreviate_weapon_keyword(keyword: str) -> str:
    if keyword is None:
        return ''
    raw = keyword.strip()
    if not raw or raw == '-':
        return ''

    anti_match = re.match(r'(?i)^anti[\s-]*([a-z\s]+)\s*(\d\+?)?$', raw)
    if anti_match:
        tag = anti_match.group(1).strip().lower()
        roll = anti_match.group(2) or ''
        tag_abbr = _ANTI_TAG_ABBREVIATIONS.get(tag)
        if not tag_abbr:
            letters = re.sub(r'[^a-z]', '', tag).upper()
            tag_abbr = letters[:4] or letters
        return f"A-{tag_abbr}{roll.upper()}"

    rapid_match = re.match(r'(?i)^rapid\s*fire\s*(.*)$', raw)
    if rapid_match:
        suffix = rapid_match.group(1).strip().replace(' ', '').upper()
        return f"RF{suffix}" if suffix else 'RF'

    sustained_match = re.match(r'(?i)^sustained\s*hits\s*(.*)$', raw)
    if sustained_match:
        suffix = sustained_match.group(1).strip().replace(' ', '').upper()
        return f"STH{suffix}" if suffix else 'STH'

    melta_match = re.match(r'(?i)^melta\s*(.*)$', raw)
    if melta_match:
        suffix = melta_match.group(1).strip().replace(' ', '').upper()
        return f"MEL{suffix}" if suffix else 'MEL'

    hit_mod_match = re.match(r'(?i)^hit\s*mod\s*([+-]?\d+)$', raw)
    if hit_mod_match:
        return f"HM{hit_mod_match.group(1)}"

    wound_mod_match = re.match(r'(?i)^wound\s*mod\s*([+-]?\d+)$', raw)
    if wound_mod_match:
        return f"WM{wound_mod_match.group(1)}"

    reroll_match = re.match(r'(?i)^reroll\s*(hits|wounds):\s*(.+)$', raw)
    if reroll_match:
        prefix = 'RRH' if reroll_match.group(1).lower() == 'hits' else 'RRW'
        suffix = reroll_match.group(2).strip().upper().replace(' ', '')
        if suffix == 'ONES':
            suffix = '1S'
        elif suffix == 'ONE':
            suffix = '1'
        return f"{prefix}{suffix}"

    normalised = _normalise_keyword(raw)
    abbr = _FIXED_KEYWORD_ABBREVIATIONS.get(normalised)
    if abbr:
        return abbr

    return raw


def format_three_decimal_text(value: Any) -> str:
    text = "" if value is None else str(value)

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        start, end = match.span(1)
        before = text[:start]
        after = text[end:]
        if not _should_format(token, before, after):
            return token
        return _format_number(token)

    return _DECIMAL_PATTERN.sub(repl, text)


def _should_format(token: str, before: str, after: str) -> bool:
    if '.' in token:
        return True

    trimmed_after = after.lstrip()
    trimmed_before = before.rstrip()
    lower_after = trimmed_after.lower()

    if trimmed_after.startswith('/') or trimmed_before.endswith('/'):
        return True
    if lower_after.startswith('pts') or lower_after.startswith('ppm'):
        return True
    if trimmed_before.lower().endswith('ppm:') or trimmed_before.lower().endswith('pts:'):
        return True

    return False
