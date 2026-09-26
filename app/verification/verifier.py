"""Runs every rule against an extracted label and rolls results up into one verdict."""

from app.models import ApplicationData, ExtractedLabel, FieldResult, Status, VerificationResult
from app.verification import rules

_SUMMARIES = {
    Status.PASS: "Label matches the application.",
    Status.REVIEW: "Mostly matches. Some items need a quick human check.",
    Status.FAIL: "Label does not match the application.",
}


def verify(app: ApplicationData, label: ExtractedLabel) -> list[FieldResult]:
    raw = label.raw_text
    return [
        rules.compare_text("brand_name", "Brand name", app.brand_name, label.brand_name, raw),
        rules.compare_text("class_type", "Class / type", app.class_type, label.class_type, raw),
        rules.compare_alcohol(app.alcohol_content, label.alcohol_content, app.beverage_type, raw),
        rules.compare_net_contents(app.net_contents, label.net_contents, raw),
        rules.compare_bottler(app.bottler_name_address, label.bottler_name_address, raw),
        rules.compare_country(app.country_of_origin, label.country_of_origin, raw),
        rules.check_warning_text(label.government_warning, strict=label.can_judge_typography),
        rules.check_warning_heading(label.government_warning, can_judge_bold=label.can_judge_typography),
    ]


def overall_status(fields: list[FieldResult]) -> Status:
    statuses = {f.status for f in fields}
    if Status.FAIL in statuses:
        return Status.FAIL
    if Status.REVIEW in statuses:
        return Status.REVIEW
    return Status.PASS


def build_result(app: ApplicationData, label: ExtractedLabel, provider: str, elapsed_ms: int) -> VerificationResult:
    if not label.image_readable:
        note = label.image_quality_note or "The image is too blurry, dark, or angled to read."
        return VerificationResult(
            overall=Status.REVIEW,
            summary=f"Couldn't read this label reliably: {note} Consider requesting a clearer image.",
            fields=[],
            provider=provider,
            elapsed_ms=elapsed_ms,
        )
    fields = verify(app, label)
    overall = overall_status(fields)
    summary = _SUMMARIES[overall]
    if label.image_quality_note:
        summary += f" Note on image: {label.image_quality_note}"
    return VerificationResult(overall=overall, summary=summary, fields=fields, provider=provider,
                              elapsed_ms=elapsed_ms)
