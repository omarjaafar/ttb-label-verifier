from typing import Protocol

from app.models import ExtractedLabel


class ExtractionError(Exception):
    """Extraction failed in a way the user should be told about (message is user-facing)."""


class LabelExtractor(Protocol):
    name: str

    async def extract(self, image_bytes: bytes, media_type: str) -> ExtractedLabel: ...
