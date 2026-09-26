"""Image intake: validate, fix orientation, and downscale before extraction.

Downscaling keeps model latency and cost down (Sarah's ~5s bar); 1568px on the long
edge is the size Claude vision works at natively, so larger images only add upload time.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_EDGE_PX = 1568
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"}


class ImageError(ValueError):
    """Bad upload; message is user-facing."""


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Return (jpeg_bytes, media_type) ready to send to an extractor."""
    if not data:
        raise ImageError("The uploaded file is empty.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ImageError("That file isn't an image we can read. Please upload a JPG or PNG photo of the label.")
    if img.format not in ALLOWED_FORMATS:
        raise ImageError(f"{img.format} images aren't supported. Please upload a JPG or PNG.")

    img = ImageOps.exif_transpose(img)  # phone photos are often stored sideways
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue(), "image/jpeg"
