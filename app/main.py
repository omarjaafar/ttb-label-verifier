import time
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import config
from app.extraction import ExtractionError, LabelExtractor, get_extractor
from app.imaging import ImageError, prepare_image
from app.models import ApplicationData, BeverageType, VerificationResult
from app.verification.verifier import build_result

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="TTB Label Verification",
    description="Checks alcohol label artwork against COLA application data. Prototype; nothing is stored.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_extractors: dict[str, LabelExtractor] = {}


def extractor_for(name: str) -> LabelExtractor:
    if name not in _extractors:
        try:
            _extractors[name] = get_extractor(name)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return _extractors[name]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_provider": config.EXTRACTION_PROVIDER}


async def read_upload(image: UploadFile) -> tuple[bytes, str]:
    data = await image.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Image is too large. The maximum is {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        return prepare_image(data)
    except ImageError as e:
        raise HTTPException(400, str(e))


def parse_application(beverage_type: BeverageType, **text_fields: str) -> ApplicationData:
    cleaned = {k: v.strip() or None for k, v in text_fields.items()}
    try:
        return ApplicationData(beverage_type=beverage_type, **cleaned)
    except ValidationError as e:
        missing = ", ".join(str(err["loc"][0]).replace("_", " ") for err in e.errors())
        raise HTTPException(422, f"Please fill in: {missing}.")


@app.post("/api/verify", response_model=VerificationResult)
async def verify_label(
    image: Annotated[UploadFile, File(description="Photo or scan of the label")],
    brand_name: Annotated[str, Form()] = "",
    class_type: Annotated[str, Form()] = "",
    net_contents: Annotated[str, Form()] = "",
    alcohol_content: Annotated[str, Form()] = "",
    bottler_name_address: Annotated[str, Form()] = "",
    country_of_origin: Annotated[str, Form()] = "",
    beverage_type: Annotated[BeverageType, Form()] = BeverageType.SPIRITS,
    provider: Annotated[str | None, Form()] = None,
) -> VerificationResult:
    application = parse_application(
        brand_name=brand_name, class_type=class_type, net_contents=net_contents, alcohol_content=alcohol_content,
        bottler_name_address=bottler_name_address, country_of_origin=country_of_origin, beverage_type=beverage_type,
    )
    image_bytes, media_type = await read_upload(image)
    extractor = extractor_for(provider or config.EXTRACTION_PROVIDER)

    start = time.perf_counter()
    try:
        label = await extractor.extract(image_bytes, media_type)
    except ExtractionError as e:
        raise HTTPException(502, str(e))
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return build_result(application, label, extractor.name, elapsed_ms)
