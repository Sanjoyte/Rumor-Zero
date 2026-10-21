"""Profile photos (ARCHITECTURE §4e; Part 14B): from an untrusted upload to two small WebP images.

**Nothing of the uploaded file survives except resized pixels.** `process_photo` decodes the bytes
with Pillow (only as JPEG, PNG or WebP, whatever the file is called or the browser said), looks at
the size in the header before any pixel is decoded, applies the EXIF orientation, crops the centre
square, flattens transparency onto white and builds two **new** images (256 and 96 px) that are
saved as WebP from pixel bytes only: no EXIF, ICC or XMP chunk can be written because the new image
has none to give. The original is never stored, and its bytes never touch the disk: the upload
handler keeps the file in memory and stops at 5 MB.

**Memory.** A decoded 25 MP RGBA image is 100 MB, so a 512 MB Render instance with two workers can't
decode two at once: `save_photo` takes a site-wide Postgres advisory lock first (one decode at a
time, whichever worker), waits at most `GATE_TIMEOUT` and then answers 503 `photo_busy`. The
transaction-scoped lock can't leak. Inside the decode, the centre square is flattened and shrunk in
horizontal bands, so no second full-size copy exists (Pillow's own `reduce` makes a premultiplied
copy of a whole RGBA image, which cost 314 MB on a 300 x 83,000 panorama). Measured peaks above the
process baseline, in a fresh interpreter: 25 MP RGBA PNG about 114 MB, 24 MP JPEG about 8 MB, 12 MP
WebP about 190 MB. Pillow 13's only WebP decoder is the animation decoder (two RGBA canvases, the
frame bytes and the image: about 16 bytes per pixel), hence the lower WebP cap.

Only this module writes `Avatar` rows and `users.avatar_version` (with `.update()`, under the
account's `FOR NO KEY UPDATE` lock). It never locks a post, so it can't deadlock with
`delete_account`, which locks posts and then the user.
"""

import hashlib
import io
import struct
import warnings
from typing import NamedTuple

import psycopg.errors
from django.core.files.uploadhandler import MemoryFileUploadHandler, StopUpload
from django.db import OperationalError, connection, transaction
from django.utils import timezone
from PIL import Image
from rest_framework.exceptions import APIException, AuthenticationFailed

from apps.accounts.models import Avatar, User

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# The multipart envelope around the file (boundary lines, headers, the other fields).
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
MAX_PIXELS = 25_000_000
# Pillow 13 decodes WebP through its animation decoder, about 16 bytes per pixel (see above).
MAX_WEBP_PIXELS = 12_000_000
MIN_SIDE = 128
LARGE, SMALL = 256, 96
SIZES = (LARGE, SMALL)
WEBP_QUALITY = 80
# Only these decoders ever see the bytes. An MPO (a multi-picture JPEG some cameras write) comes
# back from the JPEG opener with format "MPO" and is read as its first frame.
FORMATS = ("JPEG", "PNG", "WEBP")
ACCEPTED_FORMATS = frozenset({*FORMATS, "MPO"})
# Rows per band when flattening and shrinking the centre square (a multiple of the shrink factor).
BAND_ROWS = 256

GATE_KEY = 7_251_411_014  # pg_advisory_xact_lock key: one photo decode at a time, site-wide
GATE_TIMEOUT = "10s"
BUSY_RETRY_SECONDS = 5

# Pillow warns between 1x and 2x of MAX_IMAGE_PIXELS and raises only above 2x; the explicit check
# in `process_photo` refuses everything over our own limits, so the warning only adds noise.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
# A damaged multi-picture JPEG is read as a plain JPEG (and usually refused a moment later).
warnings.filterwarnings("ignore", message="Image appears to be a malformed MPO file")

# EXIF orientation -> the transpose that makes the picture upright (what ImageOps.exif_transpose
# does, applied to the small result instead of the full-size decode).
_ORIENTATION = 0x0112
_UPRIGHT = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

# What Pillow's decoders raise on bad data. Anything else is our bug and stays a 500.
_DECODE_ERRORS = (
    OSError,
    SyntaxError,
    ValueError,
    TypeError,
    IndexError,
    KeyError,
    EOFError,
    OverflowError,
    ArithmeticError,
    struct.error,
)

MESSAGES = {
    "photo_missing": "Choose a photo to upload.",
    "photo_too_large": "That file is over 5 MB.",
    "photo_unsupported": (
        "We can't read that file. Use a JPEG, PNG or WebP photo that isn't animated."
    ),
    "photo_too_small": "That photo is too small. Use one at least 128 × 128 pixels.",
    "photo_too_many_pixels": (
        "That photo has too many pixels. Use one under 25 megapixels (WebP: 12)."
    ),
}


class PhotoRefused(APIException):
    """A 400 `{"detail", "code"}` for a photo that can't be used (a validation error carries no
    code on the wire, and the page branches on it)."""

    status_code = 400

    def __init__(self, code):
        super().__init__(MESSAGES[code], code)


class PhotoUploadsBlocked(APIException):
    status_code = 403
    default_code = "photo_uploads_blocked"
    default_detail = "A moderator turned off photo uploads for your account."


class EmailUnverified(APIException):
    status_code = 403
    default_code = "email_unverified"
    default_detail = "Verify your email address first. Check your inbox for the link."


class PhotoBusy(APIException):
    """Another photo is being decoded and the gate didn't open in time. `wait` makes DRF send
    `Retry-After`."""

    status_code = 503
    default_code = "photo_busy"
    default_detail = "Photo uploads are busy right now. Try again in a few seconds."
    wait = BUSY_RETRY_SECONDS


class ProcessedPhoto(NamedTuple):
    image_256: bytes
    image_96: bytes
    version: str


# ---------- The upload ----------


class PhotoUploadHandler(MemoryFileUploadHandler):
    """The only upload handler of the avatar view: the file stays in memory (Django's default pair
    spools anything over 2.5 MB to a temp file, and the original must never touch the disk) and the
    upload stops once the files' bytes pass `MAX_UPLOAD_BYTES`, whatever the declared length said.
    The view reads `too_large` afterwards: a stopped upload parses to an empty `FILES`."""

    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0
        self.too_large = False

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        # Django would switch itself off above FILE_UPLOAD_MAX_MEMORY_SIZE; the view has already
        # refused a body that can't fit.
        self.activated = True

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > MAX_UPLOAD_BYTES:
            self.too_large = True
            raise StopUpload(connection_reset=False)
        return super().receive_data_chunk(raw_data, start)


# ---------- The pixels ----------


def _flat_rgb(image):
    """`image` as RGB, any transparency flattened onto white."""
    if image.has_transparency_data:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")


def _centre_square(image):
    """The centre square of the decoded `image` as RGB, shrunk by a whole factor while its side
    stays at least `LARGE`. Band by band: each band is flattened and shrunk on its own, so the only
    full-size pixels in memory are `image`'s own."""
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    factor = max(side // LARGE, 1)
    rows = factor * max(1, BAND_ROWS // factor)
    square = Image.new("RGB", (-(-side // factor),) * 2)
    for y in range(0, side, rows):
        band = image.crop((left, top + y, left + side, top + min(y + rows, side)))
        band = _flat_rgb(band)
        if factor > 1:
            band = band.reduce(factor)
        square.paste(band, (0, y // factor))
    return square


def _webp(square, size):
    """`square` at `size` x `size` as WebP bytes. The encoder gets a fresh image built from pixel
    bytes, so it has no metadata to write even if a future Pillow stopped ignoring it."""
    resized = square.resize((size, size), Image.Resampling.LANCZOS)
    fresh = Image.frombytes("RGB", resized.size, resized.tobytes())
    out = io.BytesIO()
    fresh.save(out, "WEBP", quality=WEBP_QUALITY)
    return out.getvalue()


def _process(data):
    with Image.open(io.BytesIO(data), formats=FORMATS) as image:
        if image.format not in ACCEPTED_FORMATS:
            raise PhotoRefused("photo_unsupported")
        # From the header: nothing has been decoded yet.
        width, height = image.size
        pixels = width * height
        if pixels > MAX_PIXELS or (image.format == "WEBP" and pixels > MAX_WEBP_PIXELS):
            raise PhotoRefused("photo_too_many_pixels")
        if min(width, height) < MIN_SIDE:
            raise PhotoRefused("photo_too_small")
        if image.format != "MPO" and getattr(image, "is_animated", False):
            raise PhotoRefused("photo_unsupported")
        orientation = image.getexif().get(_ORIENTATION)
        if image.format in ("JPEG", "MPO"):
            # Decode at 1/2, 1/4 or 1/8 scale, as far as the result stays at least LARGE px.
            image.draft("RGB", (LARGE, LARGE))
        image.load()
        square = _centre_square(image)
    if orientation in _UPRIGHT:
        square = square.transpose(_UPRIGHT[orientation])
    image_256, image_96 = (_webp(square, size) for size in SIZES)
    version = hashlib.sha256(image_256).hexdigest()[:16]
    return ProcessedPhoto(image_256, image_96, version)


def process_photo(data):
    """Validate and re-encode an upload. Returns a `ProcessedPhoto`, or raises `PhotoRefused`
    (400 with a code) for anything that isn't a usable JPEG, PNG or WebP photo."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoRefused("photo_too_large")
    try:
        return _process(data)
    except PhotoRefused:
        raise
    except Image.DecompressionBombError:
        raise PhotoRefused("photo_too_many_pixels") from None
    except _DECODE_ERRORS:
        raise PhotoRefused("photo_unsupported") from None


# ---------- The rows ----------


def _lock_account(user_id):
    """The account's row with `FOR NO KEY UPDATE` (Part 11B's rule for user rows), or None."""
    return (
        User.objects.select_for_update(no_key=True)
        .only("pk", "is_active", "is_email_verified", "avatar_version", "avatar_uploads_blocked")
        .filter(pk=user_id)
        .first()
    )


def _take_the_gate():
    """Wait for our turn to decode (one at a time, site-wide). Lasts until the transaction ends, so
    it can't leak; `lock_timeout` also bounds the wait for the account's row afterwards."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('lock_timeout', %s, true)", [GATE_TIMEOUT])
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [GATE_KEY])


def save_photo(user_id, data, *, now=None):
    """Make `data` the account's photo and return its version (the new URL's name).

    One transaction: take the decode gate, process, lock the account, check again under the lock
    that it is still active, verified and allowed to upload (a Block that committed while this
    waited wins), then write the `Avatar` row and `users.avatar_version`. Identical pixels give the
    same version. Raises `PhotoRefused`, `PhotoBusy`, `PhotoUploadsBlocked`, `EmailUnverified`.
    """
    try:
        with transaction.atomic():
            _take_the_gate()
            photo = process_photo(data)
            account = _lock_account(user_id)
            if account is None or not account.is_active:
                raise AuthenticationFailed
            if not account.is_email_verified:
                raise EmailUnverified
            if account.avatar_uploads_blocked:
                raise PhotoUploadsBlocked
            now = now or timezone.now()
            Avatar.objects.update_or_create(
                user_id=user_id,
                defaults={
                    "image_256": photo.image_256,
                    "image_96": photo.image_96,
                    "version": photo.version,
                    "bytes_total": len(photo.image_256) + len(photo.image_96),
                    "updated_at": now,
                },
                create_defaults={
                    "image_256": photo.image_256,
                    "image_96": photo.image_96,
                    "version": photo.version,
                    "bytes_total": len(photo.image_256) + len(photo.image_96),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            User.objects.filter(pk=user_id).update(avatar_version=photo.version)
    except OperationalError as error:
        if isinstance(error.__cause__, psycopg.errors.LockNotAvailable):
            raise PhotoBusy from None
        raise
    return photo.version


def delete_photo(user_id):
    """Remove the account's photo, so it shows initials again. Returns True when there was one;
    safe to repeat. Takes the account's lock (already held, when a moderator's action calls it)."""
    with transaction.atomic():
        if _lock_account(user_id) is None:
            return False
        removed, _ = Avatar.objects.filter(user_id=user_id).delete()
        User.objects.filter(pk=user_id).update(avatar_version=None)
    return removed > 0
