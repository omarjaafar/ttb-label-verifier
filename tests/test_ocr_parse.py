from app.extraction.ocr import parse_ocr_text
from app.models import Status
from app.verification.rules import GOVERNMENT_WARNING, check_warning_heading

OCR_TEXT = f"""OLD TOM
DISTILLERY
Kentucky Straight Bourbon Whiskey
45% Alc./Vol. (90 Proof)   750 mL
{GOVERNMENT_WARNING}
Bottled by Old Tom Distillery, Bardstown, KY"""


def test_ocr_parse_extracts_structured_fields():
    label = parse_ocr_text(OCR_TEXT)
    assert label.alcohol_content.startswith("45%")
    assert label.net_contents == "750 mL"
    assert label.government_warning.present
    assert label.government_warning.text == GOVERNMENT_WARNING  # trailing "Bottled by" trimmed
    assert label.can_judge_typography is False


def test_ocr_cannot_confirm_bold():
    label = parse_ocr_text(OCR_TEXT)
    assert check_warning_heading(label.government_warning, can_judge_bold=False).status == Status.REVIEW


def test_ocr_empty_is_unreadable():
    assert parse_ocr_text("  ~ ; ").image_readable is False
