"""Generate synthetic test labels (good + deliberately broken) into samples/labels/.

Run: python samples/generate_samples.py
Also writes samples/labels/applications.csv with the matching application data.
"""

import csv
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "labels"
WARNING_BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic beverages during "
    "pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages "
    "impairs your ability to drive a car or operate machinery, and may cause health problems."
)


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def centered(draw, y, text, f, fill="#2b1a0e", width=900):
    w = draw.textlength(text, font=f)
    draw.text(((width - w) / 2, y), text, font=f, fill=fill)
    return y + f.size + 14


def make_label(brand, class_type, abv, net, bottler, heading="GOVERNMENT WARNING:", heading_bold=True,
               body=WARNING_BODY, country=None, bg="#f4ead5", include_warning=True):
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 24, H - 24], outline="#6b4423", width=6)
    d.rectangle([40, 40, W - 40, H - 40], outline="#6b4423", width=2)

    y = 110
    for line in textwrap.wrap(brand, 18):
        y = centered(d, y, line, font(True, 72))
    y += 30
    d.line([200, y, W - 200, y], fill="#6b4423", width=3)
    y += 40
    for line in textwrap.wrap(class_type, 30):
        y = centered(d, y, line, font(False, 40))
    y += 40
    y = centered(d, y, abv, font(True, 38))
    y = centered(d, y, net, font(False, 36))
    if country:
        y = centered(d, y, country, font(False, 30))
    y += 30
    for line in textwrap.wrap(bottler, 50):
        y = centered(d, y, line, font(False, 24))

    if not include_warning:
        return img

    # Government warning block
    y = H - 330
    hf, bf = font(heading_bold, 22), font(False, 22)
    x = 80
    d.text((x, y), heading, font=hf, fill="#000")
    first_indent = d.textlength(heading + " ", font=hf)
    words, line, lines, avail = body.split(), "", [], W - 160 - first_indent
    for w in words:
        test = f"{line} {w}".strip()
        if d.textlength(test, font=bf) > avail:
            lines.append(line)
            line, avail = w, W - 160
        else:
            line = test
    lines.append(line)
    d.text((x + first_indent, y), lines[0], font=bf, fill="#000")
    for i, ln in enumerate(lines[1:], 1):
        d.text((x, y + i * 30), ln, font=bf, fill="#000")
    return img


BASE = dict(
    brand="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    abv="45% Alc./Vol. (90 Proof)",
    net="750 mL",
    bottler="Bottled by Old Tom Distillery, Bardstown, Kentucky",
)
APP = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "bottler_name_address": "Old Tom Distillery, Bardstown, Kentucky",
    "country_of_origin": "",
    "beverage_type": "spirits",
}

CASES = {
    # filename: (label overrides, application overrides, expected overall)
    "01_good.jpg": ({}, {}, "pass"),
    "02_brand_case_difference.jpg": ({"brand": "STONE'S THROW"}, {"brand_name": "Stone's Throw"}, "pass"),
    "03_wrong_abv.jpg": ({"abv": "40% Alc./Vol. (80 Proof)"}, {}, "fail"),
    "04_title_case_warning.jpg": ({"heading": "Government Warning:"}, {}, "fail"),
    "05_warning_not_bold.jpg": ({"heading_bold": False}, {}, "fail"),
    "06_reworded_warning.jpg": ({"body": WARNING_BODY.replace("birth defects", "complications")}, {}, "fail"),
    "07_wrong_net_contents.jpg": ({"net": "1 L"}, {}, "fail"),
    "08_import_wine.jpg": (
        {"brand": "CHATEAU BELLEVUE", "class_type": "Bordeaux Red Wine", "abv": "13.5% Alc. by Vol.",
         "net": "75 cl", "bottler": "Imported by Bellevue Imports, New York, NY", "country": "Product of France"},
        {"brand_name": "Chateau Bellevue", "class_type": "Bordeaux Red Wine", "alcohol_content": "13.5%",
         "net_contents": "750 mL", "bottler_name_address": "Bellevue Imports, New York, NY",
         "country_of_origin": "France", "beverage_type": "wine"},
        "pass",
    ),
    "10_missing_warning.jpg": ({"include_warning": False}, {}, "fail"),
    "11_beer_no_abv.jpg": (
        {"brand": "RIVER BEND BREWING", "class_type": "India Pale Ale", "abv": "", "net": "12 FL. OZ.",
         "bottler": "Brewed and canned by River Bend Brewing Co., Portland, Oregon", "bg": "#e6f0e6"},
        {"brand_name": "River Bend Brewing", "class_type": "India Pale Ale", "alcohol_content": "",
         "net_contents": "12 fl oz", "bottler_name_address": "River Bend Brewing Co., Portland, Oregon",
         "beverage_type": "beer"},
        "pass",
    ),
}


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for name, (label_over, app_over, expected) in CASES.items():
        make_label(**{**BASE, **label_over}).save(OUT / name, quality=92)
        rows.append({"filename": name, **APP, **app_over, "expected_result": expected})

    # A rough "phone photo": rotated, blurred, uneven lighting.
    img = make_label(**BASE).rotate(7, expand=True, fillcolor="#555").filter(ImageFilter.GaussianBlur(1.2))
    glare = Image.new("L", img.size, 0)
    ImageDraw.Draw(glare).ellipse([img.width * 0.55, 80, img.width * 0.95, 480], fill=110)
    img = Image.composite(Image.new("RGB", img.size, "white"), img, glare.filter(ImageFilter.GaussianBlur(60)))
    img.save(OUT / "09_angled_glare_photo.jpg", quality=80)
    rows.append({"filename": "09_angled_glare_photo.jpg", **APP, "expected_result": "pass"})

    with open(OUT / "applications.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} labels to {OUT}")


if __name__ == "__main__":
    main()
