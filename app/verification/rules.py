"""Per-field comparison rules. Each returns a FieldResult with a plain-language message."""

import difflib

from rapidfuzz import fuzz

from app.models import BeverageType, FieldResult, Status, WarningObservation
from app.verification.normalize import (
    abv_percent,
    clean_whitespace,
    normalize_bottler,
    normalize_country,
    normalize_text,
    parse_abv,
    parse_volume_ml,
)

# 27 CFR 16.21 — the exact mandatory text.
WARNING_HEADING = "GOVERNMENT WARNING:"
WARNING_BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic beverages during "
    "pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages "
    "impairs your ability to drive a car or operate machinery, and may cause health problems."
)
GOVERNMENT_WARNING = f"{WARNING_HEADING} {WARNING_BODY}"

CLOSE_MATCH_THRESHOLD = 85  # rapidfuzz score (0–100) above which a mismatch is "needs review", not "fail"
RAW_TEXT_FOUND_THRESHOLD = 90


def _not_on_application(field: str, label: str, found: str | None) -> FieldResult:
    return FieldResult(
        field=field, label=label, status=Status.NOT_APPLICABLE, found=found, message="Not on the application."
    )


def _not_found(field: str, label: str, expected: str) -> FieldResult:
    return FieldResult(
        field=field,
        label=label,
        status=Status.REVIEW,
        expected=expected,
        message="Couldn't find this on the label. Please check by eye.",
    )


def _search_raw_text(field: str, label: str, expected: str, raw_text: str | None) -> FieldResult:
    """Fallback when the extractor gave us full text but not the isolated field (OCR mode)."""
    if raw_text:
        score = fuzz.partial_ratio(normalize_text(expected), normalize_text(raw_text))
        if score >= RAW_TEXT_FOUND_THRESHOLD:
            return FieldResult(
                field=field,
                label=label,
                status=Status.PASS,
                expected=expected,
                found=expected,
                message="Found in the label text.",
            )
    return _not_found(field, label, expected)


def compare_text(field: str, label: str, expected: str | None, found: str | None, raw_text: str | None = None,
                 normalizer=normalize_text) -> FieldResult:
    if not expected:
        return _not_on_application(field, label, found)
    if not found:
        return _search_raw_text(field, label, expected, raw_text)

    base = dict(field=field, label=label, expected=expected, found=found)
    if clean_whitespace(expected) == clean_whitespace(found):
        return FieldResult(**base, status=Status.PASS, message="Exact match.")
    if normalizer(expected) == normalizer(found):
        return FieldResult(
            **base, status=Status.PASS, message="Matches. Differs only in capitalization, punctuation, or spacing."
        )
    score = fuzz.token_sort_ratio(normalizer(expected), normalizer(found))
    if score >= CLOSE_MATCH_THRESHOLD:
        return FieldResult(**base, status=Status.REVIEW, message="Very close but not identical. Please confirm.")
    return FieldResult(**base, status=Status.FAIL, message="Does not match the application.")


def compare_bottler(expected: str | None, found: str | None, raw_text: str | None = None) -> FieldResult:
    return compare_text("bottler_name_address", "Bottler / producer name and address", expected, found, raw_text,
                        normalize_bottler)


def compare_country(expected: str | None, found: str | None, raw_text: str | None = None) -> FieldResult:
    return compare_text("country_of_origin", "Country of origin", expected, found, raw_text, normalize_country)


def compare_alcohol(expected: str | None, found: str | None, beverage_type: BeverageType,
                    raw_text: str | None = None) -> FieldResult:
    field, label = "alcohol_content", "Alcohol content"
    if not expected:
        if beverage_type == BeverageType.SPIRITS:
            return FieldResult(
                field=field,
                label=label,
                status=Status.REVIEW,
                found=found,
                message="Distilled spirits must state alcohol content, but none was given on the application.",
            )
        return _not_on_application(field, label, found)
    if not found:
        return _search_raw_text(field, label, expected, raw_text)

    base = dict(field=field, label=label, expected=expected, found=found)
    exp_pct, found_pct = abv_percent(expected), abv_percent(found)
    if exp_pct is None or found_pct is None:
        return compare_text(field, label, expected, found)

    label_pct, label_proof = parse_abv(found)
    if label_pct is not None and label_proof is not None and abs(label_proof - 2 * label_pct) > 0.2:
        return FieldResult(
            **base,
            status=Status.FAIL,
            message=f"Label is inconsistent: {label_pct:g}% should be {2 * label_pct:g} proof, not {label_proof:g}.",
        )
    if abs(exp_pct - found_pct) < 0.05:
        return FieldResult(**base, status=Status.PASS, message=f"Matches ({found_pct:g}% alcohol by volume).")
    return FieldResult(
        **base, status=Status.FAIL, message=f"Label says {found_pct:g}%, application says {exp_pct:g}%."
    )


def compare_net_contents(expected: str | None, found: str | None, raw_text: str | None = None) -> FieldResult:
    field, label = "net_contents", "Net contents"
    if not expected:
        return _not_on_application(field, label, found)
    if not found:
        return _search_raw_text(field, label, expected, raw_text)

    base = dict(field=field, label=label, expected=expected, found=found)
    exp_ml, found_ml = parse_volume_ml(expected), parse_volume_ml(found)
    if exp_ml is None or found_ml is None:
        return compare_text(field, label, expected, found)
    if abs(exp_ml - found_ml) <= 0.005 * exp_ml:
        same_text = normalize_text(expected) == normalize_text(found)
        msg = "Exact match." if same_text else f"Matches (same volume: {found_ml:g} mL)."
        return FieldResult(**base, status=Status.PASS, message=msg)
    return FieldResult(
        **base, status=Status.FAIL, message=f"Label is {found_ml:g} mL, application is {exp_ml:g} mL."
    )


def _word_diff(expected: str, found: str) -> str:
    exp_words, found_words = expected.split(), found.split()
    parts = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=[w.lower() for w in exp_words],
                                                      b=[w.lower() for w in found_words]).get_opcodes():
        if op in ("replace", "delete"):
            parts.append(f'expected "{" ".join(exp_words[i1:i2])}"'
                         + (f', found "{" ".join(found_words[j1:j2])}"' if op == "replace" else ", missing"))
        elif op == "insert":
            parts.append(f'extra text "{" ".join(found_words[j1:j2])}"')
    return "; ".join(parts[:3]) + ("; …" if len(parts) > 3 else "")


def check_warning_text(obs: WarningObservation, strict: bool = True) -> FieldResult:
    """Word-for-word check of the mandatory warning (heading case is checked separately)."""
    field, label = "warning_text", "Government warning: wording"
    if not obs.present:
        return FieldResult(field=field, label=label, status=Status.FAIL, expected=GOVERNMENT_WARNING,
                           message="Government warning statement not found on the label.")
    if not obs.text:
        return FieldResult(field=field, label=label, status=Status.REVIEW, expected=GOVERNMENT_WARNING,
                           message="A warning is present but couldn't be read. Please check by eye.")

    found = clean_whitespace(obs.text)
    base = dict(field=field, label=label, expected=GOVERNMENT_WARNING, found=found)
    # Body compared case-insensitively here; heading capitalization is its own check.
    if found.casefold() == GOVERNMENT_WARNING.casefold():
        return FieldResult(**base, status=Status.PASS, message="Wording matches the required text exactly.")
    diff = _word_diff(GOVERNMENT_WARNING, found)
    if not strict:
        return FieldResult(**base, status=Status.REVIEW,
                           message=f"Wording differs ({diff}). This may be a text-recognition error, so please check.")
    return FieldResult(**base, status=Status.FAIL, message=f"Wording is not exact: {diff}.")


def check_warning_heading(obs: WarningObservation, can_judge_bold: bool = True) -> FieldResult:
    """'GOVERNMENT WARNING:' must be ALL CAPS and bold (27 CFR 16.22)."""
    field, label = "warning_heading", 'Government warning: "GOVERNMENT WARNING:" in caps and bold'
    if not obs.present:
        return FieldResult(field=field, label=label, status=Status.FAIL, expected=WARNING_HEADING,
                           message="No government warning on the label.")

    found_heading = clean_whitespace(obs.text or "")[: len(WARNING_HEADING)] or None
    base = dict(field=field, label=label, expected=WARNING_HEADING, found=found_heading)
    caps_ok = (found_heading == WARNING_HEADING) if found_heading else obs.heading_all_caps
    if caps_ok is False or obs.heading_all_caps is False:
        return FieldResult(**base, status=Status.FAIL,
                           message='"GOVERNMENT WARNING:" must be in all capital letters.')
    if caps_ok is None:
        return FieldResult(**base, status=Status.REVIEW, message="Couldn't confirm capitalization. Please check.")

    if not can_judge_bold or obs.heading_bold is None:
        return FieldResult(**base, status=Status.REVIEW,
                           message="All caps confirmed. Couldn't confirm bold type, so please check by eye.")
    if obs.heading_bold is False:
        return FieldResult(**base, status=Status.FAIL, message='"GOVERNMENT WARNING:" must be in bold type.')
    return FieldResult(**base, status=Status.PASS, message="All caps and bold.")
