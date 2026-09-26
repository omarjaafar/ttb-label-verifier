from app.extraction.base import ExtractionError, LabelExtractor


def get_extractor(name: str) -> LabelExtractor:
    if name == "claude":
        from app.extraction.claude import ClaudeExtractor

        return ClaudeExtractor()
    if name == "ocr":
        from app.extraction.ocr import OcrExtractor

        return OcrExtractor()
    raise ValueError(f"Unknown extraction provider: {name!r} (expected 'claude' or 'ocr')")


__all__ = ["ExtractionError", "LabelExtractor", "get_extractor"]
