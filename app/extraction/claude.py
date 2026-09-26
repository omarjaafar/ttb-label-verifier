"""Vision-LLM extractor: reads label fields (and warning typography) from the image.

Claude only *transcribes* here. It never decides compliance; app.verification does that.
"""

import base64
import json

import anthropic

from app import config
from app.extraction.base import ExtractionError
from app.models import ExtractedLabel

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_NULLABLE_BOOL = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}

_SCHEMA = {
    "type": "object",
    "properties": {
        "image_readable": {"type": "boolean"},
        "image_quality_note": _NULLABLE_STR,
        "brand_name": _NULLABLE_STR,
        "class_type": _NULLABLE_STR,
        "alcohol_content": _NULLABLE_STR,
        "net_contents": _NULLABLE_STR,
        "bottler_name_address": _NULLABLE_STR,
        "country_of_origin": _NULLABLE_STR,
        "government_warning": {
            "type": "object",
            "properties": {
                "present": {"type": "boolean"},
                "heading_as_printed": _NULLABLE_STR,
                "text": _NULLABLE_STR,
                "heading_all_caps": _NULLABLE_BOOL,
                "heading_bold": _NULLABLE_BOOL,
            },
            "required": ["present", "heading_as_printed", "text", "heading_all_caps", "heading_bold"],
            "additionalProperties": False,
        },
    },
    "required": [
        "image_readable",
        "image_quality_note",
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_name_address",
        "country_of_origin",
        "government_warning",
    ],
    "additionalProperties": False,
}

_SYSTEM = """You transcribe text from alcohol beverage label images for U.S. TTB compliance review.
Latency-sensitive: begin your answer immediately.

Transcribe exactly what is printed. Do not correct spelling, capitalization, punctuation, or wording, \
because reviewers need to catch labels that deviate from the rules. If a field is not on the label or \
you can't read it, use null. Never guess or fill in expected values.

Fields:
- brand_name: the brand name as printed.
- class_type: the class/type designation (e.g., "Kentucky Straight Bourbon Whiskey", "India Pale Ale").
- alcohol_content: the full alcohol statement (e.g., "45% Alc./Vol. (90 Proof)").
- net_contents: e.g., "750 mL", "12 FL OZ".
- bottler_name_address: the "bottled by / produced by / imported by" name and address line.
- country_of_origin: only if stated (e.g., "Product of Scotland").
- government_warning: whether the health warning is present, and:
  - heading_as_printed: the warning's heading copied letter-for-letter with its exact letter case. \
Labels are often non-compliant here, so do not normalize: if it is printed "Government Warning:", write \
"Government Warning:", not "GOVERNMENT WARNING:". Look closely at each letter.
  - text: the full warning verbatim, starting with the heading exactly as in heading_as_printed.
  - heading_all_caps: true only if every letter of the printed heading is uppercase.
  - heading_bold: whether the heading is visibly bold (heavier stroke than the surrounding text); \
null if you genuinely cannot tell.
- image_readable: false only if the image is too blurry, dark, glared, or angled to read the label.
- image_quality_note: a short note if glare, angle, blur, or cropping affected reading. Otherwise null."""


# Models that support server-side refusal fallbacks (re-run on another model instead of failing).
_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}


class ClaudeExtractor:
    name = "claude"

    def __init__(self, model: str = config.CLAUDE_MODEL, thinking: str = config.CLAUDE_THINKING,
                 timeout_s: float = config.EXTRACTION_TIMEOUT_S):
        self.model = model
        self.thinking = thinking
        self.client = anthropic.AsyncAnthropic(timeout=timeout_s, max_retries=1)

    def _request_options(self) -> dict:
        opts: dict = {}
        if self.thinking == "disabled":
            opts["thinking"] = {"type": "disabled"}
        if self.model in _FALLBACK_MODELS:
            opts["betas"] = ["server-side-fallback-2026-07-01"]
            opts["fallbacks"] = "default"
        return opts

    async def extract(self, image_bytes: bytes, media_type: str) -> ExtractedLabel:
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=4096,
                system=_SYSTEM,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                     "data": base64.standard_b64encode(image_bytes).decode()}},
                        {"type": "text", "text": "Transcribe this label."},
                    ],
                }],
                **self._request_options(),
            )
        except anthropic.AuthenticationError:
            raise ExtractionError("The AI service isn't configured correctly (bad API key). Contact IT.")
        except anthropic.RateLimitError:
            raise ExtractionError("The AI service is busy right now. Please try again in a moment.")
        except anthropic.APITimeoutError:
            raise ExtractionError("The AI service took too long to respond. Please try again.")
        except anthropic.APIConnectionError:
            raise ExtractionError(
                "Couldn't reach the AI service (network or firewall). Try again, or switch to offline OCR mode."
            )
        except anthropic.APIStatusError as e:
            raise ExtractionError(f"The AI service returned an error ({e.status_code}). Please try again.")

        if response.stop_reason == "refusal":
            raise ExtractionError("The AI service declined to process this image. Please review it manually.")
        if response.stop_reason == "max_tokens":
            raise ExtractionError("The label had more text than expected. Please review it manually.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ExtractionError("The AI service returned no result. Please try again.")
        return ExtractedLabel.model_validate(json.loads(text))
