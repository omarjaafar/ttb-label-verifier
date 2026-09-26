"""Offline fallback extractor using local Tesseract OCR. No network calls.

For networks that block cloud AI endpoints. OCR gives us raw text, not labelled fields,
so we regex out the structured bits (ABV, volume, warning) and let the rules fuzzy-search
the raw text for brand and class. OCR can't see bold type, so that check becomes "needs review".
"""

import asyncio
import io
import re

from PIL import Image, ImageOps

from app.extraction.base import ExtractionError
from app.models import ExtractedLabel, WarningObservation

_WARNING_RE = re.compile(r"government\s+warning\s*:?.*", re.I | re.S)
_ABV_RE = re.compile(
    r"\d+(?:\.\d+)?\s*%\s*(?:alc\.?\s*/?\s*(?:by\s*)?vol\.?)?(?:\s*\(?\s*\d+(?:\.\d+)?\s*proof\s*\)?)?"
    r"|\d+(?:\.\d+)?\s*proof",
    re.I,
)
_VOLUME_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:ml|l|cl|fl\.?\s*oz|liters?|litres?)\b\.?", re.I)
_MIN_TEXT_CHARS = 15


def _ocr(image_bytes: bytes) -> str:
    try:
        import pytesseract
    except ImportError:  # pragma: no cover
        raise ExtractionError("Offline OCR isn't installed on this server.")
    img = ImageOps.grayscale(Image.open(io.BytesIO(image_bytes)))
    img = ImageOps.autocontrast(img)
    try:
        return pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError:
        raise ExtractionError("Offline OCR (Tesseract) isn't installed on this server.")


def parse_ocr_text(text: str) -> ExtractedLabel:
    text = text.strip()
    if len(re.sub(r"\W", "", text)) < _MIN_TEXT_CHARS:
        return ExtractedLabel(image_readable=False, image_quality_note="Almost no text could be recognized.",
                              can_judge_typography=False)

    warning_m = _WARNING_RE.search(text)
    warning_text = re.sub(r"\s+", " ", warning_m.group(0)).strip() if warning_m else None
    if warning_text:
        # Warning ends at "health problems." Trim trailing label text OCR picked up after it.
        end = warning_text.lower().find("health problems")
        if end != -1:
            warning_text = warning_text[: end + len("health problems.")].rstrip()
    abv_m, vol_m = _ABV_RE.search(text), _VOLUME_RE.search(text)
    return ExtractedLabel(
        alcohol_content=abv_m.group(0).strip() if abv_m else None,
        net_contents=vol_m.group(0).strip() if vol_m else None,
        government_warning=WarningObservation(
            present=warning_m is not None,
            text=warning_text,
            heading_all_caps=warning_text.startswith("GOVERNMENT WARNING") if warning_text else None,
            heading_bold=None,
        ),
        raw_text=text,
        can_judge_typography=False,
        image_quality_note="Checked with offline OCR. Bold type can't be verified and small text may be misread.",
    )


class OcrExtractor:
    name = "ocr"

    async def extract(self, image_bytes: bytes, media_type: str) -> ExtractedLabel:
        text = await asyncio.to_thread(_ocr, image_bytes)
        return parse_ocr_text(text)
