import pytest

from app.verification.normalize import abv_percent, normalize_bottler, normalize_country, normalize_text, parse_abv, parse_volume_ml


@pytest.mark.parametrize("a,b", [
    ("STONE'S THROW", "Stone's Throw"),
    ("Stone’s Throw", "STONE'S THROW"),
    ("OLD  TOM   DISTILLERY", "Old Tom Distillery"),
    ("Smith & Sons", "Smith and Sons"),
])
def test_normalize_text_equivalent(a, b):
    assert normalize_text(a) == normalize_text(b)


def test_normalize_text_different():
    assert normalize_text("Stone's Throw") != normalize_text("Stone Throw Reserve")


@pytest.mark.parametrize("s,pct,proof", [
    ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
    ("ALC. 12.5% BY VOL.", 12.5, None),
    ("80 Proof", None, 80.0),
    ("5.2 alc/vol", 5.2, None),
])
def test_parse_abv(s, pct, proof):
    assert parse_abv(s) == (pct, proof)


def test_abv_percent_from_proof():
    assert abv_percent("90 Proof") == 45.0


@pytest.mark.parametrize("s,ml", [
    ("750 mL", 750),
    ("750ML", 750),
    ("1.75 L", 1750),
    ("1 Liter", 1000),
    ("75 cl", 750),
    ("12 FL. OZ.", 12 * 29.5735),
    ("12 fl oz", 12 * 29.5735),
    ("1 Pint", 473.176),
])
def test_parse_volume(s, ml):
    assert parse_volume_ml(s) == pytest.approx(ml)


def test_parse_volume_none():
    assert parse_volume_ml("Kentucky Straight Bourbon") is None


@pytest.mark.parametrize("a,b", [
    ("USA", "United States"),
    ("Product of U.S.A.", "united states of america"),
    ("Product of Scotland", "United Kingdom"),
    ("Made in France", "France"),
])
def test_normalize_country(a, b):
    assert normalize_country(a) == normalize_country(b)


@pytest.mark.parametrize("label", [
    "Bottled by Old Tom Distillery, Bardstown, Kentucky",
    "DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
    "Imported by: Old Tom Distillery, Bardstown, Kentucky",
])
def test_normalize_bottler_strips_role_prefix(label):
    assert normalize_bottler(label) == normalize_bottler("Old Tom Distillery, Bardstown, Kentucky")
