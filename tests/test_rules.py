from app.models import (
    ApplicationData,
    BeverageType,
    ExtractedLabel,
    Status,
    WarningObservation,
)
from app.verification import rules
from app.verification.rules import GOVERNMENT_WARNING
from app.verification.verifier import build_result, verify

GOOD_WARNING = WarningObservation(present=True, text=GOVERNMENT_WARNING, heading_all_caps=True, heading_bold=True)


# --- Text fields (Dave's "STONE'S THROW" case) ------------------------------

def test_brand_case_difference_passes():
    r = rules.compare_text("brand_name", "Brand name", "Stone's Throw", "STONE'S THROW")
    assert r.status == Status.PASS
    assert "capitalization" in r.message


def test_brand_exact_passes():
    assert rules.compare_text("b", "B", "OLD TOM DISTILLERY", "OLD TOM DISTILLERY").status == Status.PASS


def test_brand_near_miss_needs_review():
    assert rules.compare_text("b", "B", "Old Tom Distillery", "Old Tom Distilery").status == Status.REVIEW


def test_brand_different_fails():
    assert rules.compare_text("b", "B", "Old Tom Distillery", "Buffalo Creek").status == Status.FAIL


def test_missing_on_label_needs_review():
    assert rules.compare_text("b", "B", "Old Tom", None).status == Status.REVIEW


def test_not_on_application_is_na():
    assert rules.compare_text("b", "B", None, "Product of USA").status == Status.NOT_APPLICABLE


def test_raw_text_fallback_finds_brand():
    raw = "OLD TOM\nDISTILLERY\nKentucky Straight Bourbon Whiskey"
    assert rules.compare_text("b", "B", "Old Tom Distillery", None, raw).status == Status.PASS


# --- Alcohol content ---------------------------------------------------------

def test_abv_match_with_proof():
    r = rules.compare_alcohol("45%", "45% Alc./Vol. (90 Proof)", BeverageType.SPIRITS)
    assert r.status == Status.PASS


def test_abv_proof_only_on_label():
    assert rules.compare_alcohol("45% ABV", "90 Proof", BeverageType.SPIRITS).status == Status.PASS


def test_abv_mismatch_fails():
    r = rules.compare_alcohol("45%", "40% Alc./Vol.", BeverageType.SPIRITS)
    assert r.status == Status.FAIL
    assert "40%" in r.message


def test_abv_inconsistent_proof_fails():
    assert rules.compare_alcohol("45%", "45% Alc./Vol. (80 Proof)", BeverageType.SPIRITS).status == Status.FAIL


def test_abv_optional_for_beer():
    assert rules.compare_alcohol(None, None, BeverageType.BEER).status == Status.NOT_APPLICABLE


def test_abv_required_for_spirits():
    assert rules.compare_alcohol(None, "40%", BeverageType.SPIRITS).status == Status.REVIEW


# --- Net contents ------------------------------------------------------------

def test_net_contents_unit_equivalence():
    assert rules.compare_net_contents("750 mL", "75 cl").status == Status.PASS


def test_net_contents_mismatch():
    assert rules.compare_net_contents("750 mL", "1 L").status == Status.FAIL


# --- Government warning (Jenny's rules) -----------------------------------

def test_warning_exact_passes():
    assert rules.check_warning_text(GOOD_WARNING).status == Status.PASS
    assert rules.check_warning_heading(GOOD_WARNING).status == Status.PASS


def test_warning_missing_fails():
    obs = WarningObservation(present=False)
    assert rules.check_warning_text(obs).status == Status.FAIL
    assert rules.check_warning_heading(obs).status == Status.FAIL


def test_warning_title_case_heading_fails():
    text = GOVERNMENT_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    obs = WarningObservation(present=True, text=text, heading_all_caps=False, heading_bold=True)
    r = rules.check_warning_heading(obs)
    assert r.status == Status.FAIL
    assert "capital" in r.message


def test_warning_not_bold_fails():
    obs = GOOD_WARNING.model_copy(update={"heading_bold": False})
    assert rules.check_warning_heading(obs).status == Status.FAIL


def test_warning_bold_unknown_needs_review():
    obs = GOOD_WARNING.model_copy(update={"heading_bold": None})
    assert rules.check_warning_heading(obs).status == Status.REVIEW


def test_warning_reworded_fails_with_diff():
    text = GOVERNMENT_WARNING.replace("birth defects", "health issues")
    r = rules.check_warning_text(WarningObservation(present=True, text=text))
    assert r.status == Status.FAIL
    assert "birth defects" in r.message


def test_warning_wording_mismatch_is_review_under_ocr():
    text = GOVERNMENT_WARNING.replace("pregnancy", "pregnancv")  # typical OCR error
    r = rules.check_warning_text(WarningObservation(present=True, text=text), strict=False)
    assert r.status == Status.REVIEW


def test_warning_extra_whitespace_ok():
    text = GOVERNMENT_WARNING.replace(" ", "  \n ")
    assert rules.check_warning_text(WarningObservation(present=True, text=text)).status == Status.PASS


# --- End to end over the verifier ----------------------------------------------

SAMPLE_APP = ApplicationData(
    brand_name="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
)
SAMPLE_LABEL = ExtractedLabel(
    brand_name="OLD TOM DISTILLERY",
    class_type="KENTUCKY STRAIGHT BOURBON WHISKEY",
    alcohol_content="45% ALC./VOL. (90 PROOF)",
    net_contents="750 ML",
    government_warning=GOOD_WARNING,
)


def test_sample_label_passes():
    result = build_result(SAMPLE_APP, SAMPLE_LABEL, "test", 0)
    assert result.overall == Status.PASS, [f for f in result.fields if f.status != Status.PASS]


def test_one_failure_fails_overall():
    label = SAMPLE_LABEL.model_copy(update={"alcohol_content": "40% ALC./VOL."})
    assert build_result(SAMPLE_APP, label, "test", 0).overall == Status.FAIL


def test_unreadable_image_needs_review():
    result = build_result(SAMPLE_APP, ExtractedLabel(image_readable=False), "test", 0)
    assert result.overall == Status.REVIEW
    assert result.fields == []


def test_all_fields_reported():
    fields = {f.field for f in verify(SAMPLE_APP, SAMPLE_LABEL)}
    assert {"brand_name", "class_type", "alcohol_content", "net_contents", "warning_text", "warning_heading"} <= fields
