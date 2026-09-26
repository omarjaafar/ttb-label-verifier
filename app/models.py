"""Data shapes shared across extraction, verification, and the API."""

from enum import Enum

from pydantic import BaseModel, Field


class BeverageType(str, Enum):
    SPIRITS = "spirits"
    WINE = "wine"
    BEER = "beer"


class ApplicationData(BaseModel):
    """What the applicant declared on their COLA application."""

    beverage_type: BeverageType = BeverageType.SPIRITS
    brand_name: str = Field(min_length=1)
    class_type: str = Field(min_length=1)
    # Optional for some wine and beer (27 CFR 4.36 / 7.63); required for spirits.
    alcohol_content: str | None = None
    net_contents: str = Field(min_length=1)
    bottler_name_address: str | None = None
    country_of_origin: str | None = None


class WarningObservation(BaseModel):
    present: bool
    text: str | None = None
    heading_all_caps: bool | None = None
    heading_bold: bool | None = None


class ExtractedLabel(BaseModel):
    """What the extractor read off the label image. None = not found / not readable."""

    image_readable: bool = True
    image_quality_note: str | None = None
    brand_name: str | None = None
    class_type: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    bottler_name_address: str | None = None
    country_of_origin: str | None = None
    government_warning: WarningObservation = WarningObservation(present=False)
    # Full OCR text, when the extractor can't isolate fields (OCR fallback).
    raw_text: str | None = None
    # False when the extractor can't judge typography (e.g. bold); rules turn those into REVIEW.
    can_judge_typography: bool = True


class Status(str, Enum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"
    NOT_APPLICABLE = "n/a"


class FieldResult(BaseModel):
    field: str
    label: str  # human-readable field name
    status: Status
    expected: str | None = None  # from the application
    found: str | None = None  # from the label
    message: str


class VerificationResult(BaseModel):
    overall: Status
    summary: str
    fields: list[FieldResult]
    provider: str
    elapsed_ms: int
