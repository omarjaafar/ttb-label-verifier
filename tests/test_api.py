"""API tests with a fake extractor, so no network or API key is needed."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.extraction import ExtractionError
from app.models import ExtractedLabel, WarningObservation
from app.verification.rules import GOVERNMENT_WARNING

FORM = {
    "brand_name": "Old Tom Distillery",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45%",
    "net_contents": "750 mL",
}


class FakeExtractor:
    name = "fake"

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    async def extract(self, image_bytes, media_type):
        if self.error:
            raise self.error
        return self.result


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    label = ExtractedLabel(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
        government_warning=WarningObservation(present=True, text=GOVERNMENT_WARNING,
                                              heading_all_caps=True, heading_bold=True),
    )
    monkeypatch.setattr(main, "extractor_for", lambda name: FakeExtractor(label))
    return TestClient(main.app)


def post(client, form=FORM, image=None):
    return client.post("/api/verify", data=form, files={"image": ("label.png", image or png_bytes(), "image/png")})


def test_index_served(client):
    assert client.get("/").status_code == 200


def test_verify_pass(client):
    r = post(client)
    assert r.status_code == 200
    assert r.json()["overall"] == "pass"


def test_missing_required_field(client):
    r = post(client, form={**FORM, "brand_name": "  "})
    assert r.status_code == 422
    assert "brand name" in r.json()["detail"]


def test_non_image_rejected(client):
    r = post(client, image=b"not an image")
    assert r.status_code == 400
    assert "JPG or PNG" in r.json()["detail"]


def test_extraction_error_is_friendly(monkeypatch):
    monkeypatch.setattr(main, "extractor_for", lambda name: FakeExtractor(error=ExtractionError("AI is down.")))
    r = post(TestClient(main.app))
    assert r.status_code == 502
    assert r.json()["detail"] == "AI is down."
