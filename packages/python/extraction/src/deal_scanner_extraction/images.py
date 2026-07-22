from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

import imagehash
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class ImageFingerprint:
    sha256: str
    perceptual_hash: str
    width: int
    height: int
    image_format: str
    mime_type: str


class InvalidImage(ValueError):
    pass


def fingerprint_image(content: bytes, max_bytes: int = MAX_IMAGE_BYTES) -> ImageFingerprint:
    if not content or len(content) > max_bytes:
        raise InvalidImage("image is empty or exceeds the configured size limit")
    try:
        with Image.open(BytesIO(content)) as candidate:
            candidate.verify()
        with Image.open(BytesIO(content)) as candidate:
            image_format = (candidate.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise InvalidImage(f"unsupported image format: {image_format or 'unknown'}")
            normalized = ImageOps.exif_transpose(candidate).convert("RGB")
            width, height = normalized.size
            if width < 16 or height < 16 or width * height > 40_000_000:
                raise InvalidImage("image dimensions are outside the allowed range")
            perceptual_hash = str(imagehash.phash(normalized))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("invalid or unsafe image") from exc

    mime_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format]
    return ImageFingerprint(
        sha256=hashlib.sha256(content).hexdigest(),
        perceptual_hash=perceptual_hash,
        width=width,
        height=height,
        image_format=image_format,
        mime_type=mime_type,
    )


def perceptually_similar(first_hash: str, second_hash: str, max_distance: int = 8) -> bool:
    try:
        return imagehash.hex_to_hash(first_hash) - imagehash.hex_to_hash(second_hash) <= max_distance
    except ValueError as exc:
        raise InvalidImage("invalid perceptual hash") from exc
