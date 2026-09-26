"""Text/number normalization used to compare label values against application values.

Everything here is deterministic and unit-tested: these functions encode the
"judgment" agents apply by eye (case, punctuation, unit equivalence).
"""

import re
import unicodedata

_QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "´": "'", "`": "'"})


def clean_whitespace(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_QUOTE_MAP)
    return re.sub(r"\s+", " ", s).strip()


def normalize_text(s: str) -> str:
    """Case-, punctuation- and whitespace-insensitive form. "STONE'S THROW" == "Stone's Throw"."""
    s = clean_whitespace(s).casefold().replace("&", " and ")
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


# --- Alcohol content ------------------------------------------------------

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_ABV_WORDS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:percent|pct)?\s*(?:alc(?:ohol)?\.?\s*(?:/|by)\s*vol)", re.I)
_PROOF_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:°\s*)?proof", re.I)


def parse_abv(s: str) -> tuple[float | None, float | None]:
    """Return (percent ABV, proof) as found in the text; either may be None."""
    pct_m = _PCT_RE.search(s) or _ABV_WORDS_RE.search(s)
    proof_m = _PROOF_RE.search(s)
    pct = float(pct_m.group(1)) if pct_m else None
    proof = float(proof_m.group(1)) if proof_m else None
    return pct, proof


def abv_percent(s: str) -> float | None:
    """Best-effort ABV percentage; derives it from proof (proof / 2) when no % is given."""
    pct, proof = parse_abv(s)
    if pct is not None:
        return pct
    return proof / 2 if proof is not None else None


# --- Net contents ---------------------------------------------------------

_ML_PER_UNIT = {
    "ml": 1.0,
    "milliliter": 1.0,
    "millilitre": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "centilitre": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "fl oz": 29.5735,
    "fluid ounce": 29.5735,
    "oz": 29.5735,
    "pint": 473.176,
    "pt": 473.176,
    "quart": 946.353,
    "qt": 946.353,
    "gallon": 3785.41,
    "gal": 3785.41,
}
_UNIT_PATTERN = "|".join(
    sorted((re.escape(u).replace(r"\ ", r"\.?\s*") + "s?" for u in _ML_PER_UNIT), key=len, reverse=True)
)
_VOLUME_RE = re.compile(rf"(\d+(?:[.,]\d+)?)\s*({_UNIT_PATTERN})\.?(?![a-z])", re.I)


def parse_volume_ml(s: str) -> float | None:
    """'750 mL' -> 750.0, '1.75 L' -> 1750.0, '12 FL. OZ.' -> 354.9."""
    m = _VOLUME_RE.search(s)
    if not m:
        return None
    qty = float(m.group(1).replace(",", "."))
    unit = re.sub(r"[.\s]+", " ", m.group(2).lower()).strip()
    unit = unit[:-1] if unit.endswith("s") and unit[:-1] in _ML_PER_UNIT else unit
    return qty * _ML_PER_UNIT[unit]


# --- Bottler / producer ---------------------------------------------------

_BOTTLER_PREFIX_RE = re.compile(
    r"^\s*(?:(?:bottled|produced|distilled|imported|brewed|vinted|cellared|blended|made|packed|canned)"
    r"(?:\s*(?:and|&)\s*(?:bottled|produced|distilled|imported|brewed|vinted|cellared|blended|packed|canned))?"
    r"\s+(?:by|for)\s*:?\s*)",
    re.I,
)


def normalize_bottler(s: str) -> str:
    """'Bottled by Old Tom Distillery, Bardstown, KY' -> 'old tom distillery bardstown ky'."""
    return normalize_text(_BOTTLER_PREFIX_RE.sub("", s))


# --- Country of origin ----------------------------------------------------

_COUNTRY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "united states of america": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
    "scotland": "united kingdom",
    "holland": "netherlands",
    "the netherlands": "netherlands",
}


def normalize_country(s: str) -> str:
    n = normalize_text(re.sub(r"^(product|produce|made|imported)\s+(of|in|from)\s+", "", s, flags=re.I))
    n = n.replace(" ", "") if len(n) <= 5 else n  # "u s a" -> "usa"
    return _COUNTRY_ALIASES.get(n, n)
