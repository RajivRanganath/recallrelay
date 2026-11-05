"""Bounded PNG/JPEG decoding; no image bodies in logs or object representations."""
import base64
import binascii
from dataclasses import dataclass, field
from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError

from evidence.backend.errors import InvalidInput

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 8_000_000
MAX_IMAGE_EDGE = 4096


@dataclass(frozen=True)
class DecodedImage:
    content: bytes = field(repr=False)
    mime_type: str
    width: int
    height: int


def decode_image(encoded, mime):
    if encoded is None and mime is None:
        return None
    if not isinstance(encoded, str) or mime not in ('image/png', 'image/jpeg'):
        raise InvalidInput('Use PNG or JPEG, or omit both image and MIME type')
    if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise InvalidInput('Image exceeds the 2 MiB limit')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise InvalidInput('Image must be valid base64') from None
    if not 0 < len(raw) <= MAX_IMAGE_BYTES:
        raise InvalidInput('Image must be 1 byte to 2 MiB')
    expected = 'PNG' if mime == 'image/png' else 'JPEG'
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            # Restrict decoders, check dimensions before allocating pixel storage.
            with Image.open(BytesIO(raw), formats=['PNG', 'JPEG']) as image:
                width, height = image.size
                if (image.format != expected or not 0 < width <= MAX_IMAGE_EDGE
                        or not 0 < height <= MAX_IMAGE_EDGE or width * height > MAX_IMAGE_PIXELS
                        or getattr(image, 'n_frames', 1) != 1):
                    raise InvalidInput('Unsupported image format, dimensions or animation')
                image.verify()
            # verify() checks integrity; load() separately exercises pixel decoding.
            with Image.open(BytesIO(raw), formats=['PNG', 'JPEG']) as image:
                image.load()
    except (OSError, ValueError, SyntaxError, EOFError, UnidentifiedImageError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise InvalidInput('Image cannot be decoded within the supported limits') from None
    return DecodedImage(raw, mime, width, height)
