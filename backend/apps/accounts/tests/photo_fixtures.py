"""Photos for the avatar tests, generated with Pillow in the test (the repository keeps no binary
fixtures; ARCHITECTURE §4e). Quadrant images make orientation and cropping visible: the four
quadrants are four clearly different colours, read back at their centres through `quadrants`."""

import io
import struct

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageCms

# What a phone adds to a picture and the avatar must not keep.
SECRET_MAKER = "SecretCameraMaker"
SECRET_XMP = b"SECRET-XMP-MARKER"
GPS = {1: "N", 2: (37.0, 25.0, 19.0), 3: "W", 4: (122.0, 5.0, 24.0)}

RED, GREEN, BLUE, YELLOW = (230, 20, 20), (20, 200, 20), (20, 20, 230), (240, 220, 20)
# Top-left, top-right, bottom-left, bottom-right.
QUADRANT_COLOURS = (RED, GREEN, BLUE, YELLOW)
# EXIF orientation values 1 to 8.
ORIENTATIONS = range(1, 9)


def encode(image, fmt, **options):
    out = io.BytesIO()
    image.save(out, fmt, **options)
    return out.getvalue()


def quadrant_image(width=300, height=200):
    """Four solid quadrants: red, green / blue, yellow."""
    image = Image.new("RGB", (width, height))
    xs, ys = (0, width // 2, width), (0, height // 2, height)
    for index, colour in enumerate(QUADRANT_COLOURS):
        column, row = index % 2, index // 2
        image.paste(colour, (xs[column], ys[row], xs[column + 1], ys[row + 1]))
    return image


def exif_with(orientation=1, gps=True):
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x010F] = SECRET_MAKER
    if gps:
        ifd = exif.get_ifd(0x8825)
        ifd.update(GPS)
    return exif


def srgb_profile():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def xmp_packet():
    return b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF>' + SECRET_XMP + b"</rdf:RDF></x:xmpmeta>"


def gps_jpeg(width=400, height=300, orientation=1):
    """A JPEG with GPS EXIF, a maker name, an ICC profile and an XMP packet."""
    return encode(
        quadrant_image(width, height),
        "JPEG",
        exif=exif_with(orientation),
        icc_profile=srgb_profile(),
        xmp=xmp_packet(),
        quality=92,
    )


def oriented(orientation, fmt="JPEG", width=300, height=200):
    """The quadrant picture as stored, with EXIF `orientation` (the pixels are not rotated)."""
    options = {"quality": 95} if fmt == "JPEG" else {}
    exif = exif_with(orientation, gps=False)
    return encode(quadrant_image(width, height), fmt, exif=exif, **options)


def jpeg(width=300, height=200, colour=RED, quality=90):
    return encode(Image.new("RGB", (width, height), colour), "JPEG", quality=quality)


def png(width=300, height=200, mode="RGB", colour=RED):
    return encode(Image.new(mode, (width, height), colour), "PNG")


def webp(width=300, height=200, colour=RED, lossless=False):
    return encode(Image.new("RGB", (width, height), colour), "WEBP", lossless=lossless, quality=80)


def flat_png(width, height, mode="L"):
    """A big-in-pixels, tiny-in-bytes image (what a decompression bomb is)."""
    return encode(Image.new(mode, (width, height)), "PNG")


def apng():
    frames = [Image.new("RGB", (200, 200), colour) for colour in (RED, GREEN)]
    return encode(frames[0], "PNG", save_all=True, append_images=frames[1:], duration=100, loop=0)


def animated_webp():
    frames = [Image.new("RGB", (200, 200), colour) for colour in (RED, GREEN)]
    return encode(frames[0], "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)


def mpo(first=RED, second=GREEN):
    """A multi-picture JPEG, as some cameras write: two frames, the first one is the photo."""
    frames = [Image.new("RGB", (200, 200), colour) for colour in (first, second)]
    return encode(frames[0], "MPO", save_all=True, append_images=frames[1:])


def gif():
    return encode(Image.new("RGB", (200, 200), RED), "GIF")


def bmp():
    return encode(Image.new("RGB", (200, 200), RED), "BMP")


def tiff():
    return encode(Image.new("RGB", (200, 200), RED), "TIFF")


SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
    b'<rect width="200" height="200"/></svg>'
)
# The start of a HEIC file (an ISO base media "ftyp" box): no Pillow decoder reads it here.
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 200


def riff_chunks(data):
    """The chunk names of a WebP file, read from the bytes (not through Pillow)."""
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", "not a WebP file"
    names, position = [], 12
    while position + 8 <= len(data):
        names.append(data[position : position + 4].decode("latin-1"))
        (size,) = struct.unpack("<I", data[position + 4 : position + 8])
        position += 8 + size + (size & 1)
    return names


def decode(data):
    image = Image.open(io.BytesIO(data))
    image.load()
    return image.convert("RGB")


def quadrant_colours(image):
    """The colours at the centres of the four quadrants of a PIL image, top-left first."""
    image = image.convert("RGB")
    width, height = image.size
    return tuple(
        image.getpixel((width * (1 + 2 * x) // 4, height * (1 + 2 * y) // 4))
        for y in (0, 1)
        for x in (0, 1)
    )


def quadrants(data):
    """`quadrant_colours` of encoded image bytes."""
    return quadrant_colours(decode(data))


def close(colour_a, colour_b, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(colour_a, colour_b, strict=True))


def assert_quadrants(actual, expected):
    assert all(close(a, e) for a, e in zip(actual, expected, strict=True)), (actual, expected)


def upload(data, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


def noisy_jpeg(side=2000, quality=90, seed=14):
    """A valid JPEG of random pixels that is several MB: over Django's 2.5 MB spool threshold, so a
    default upload handler would write it to a temp file."""
    import random

    pixels = random.Random(seed).randbytes(side * side * 3)
    return encode(Image.frombytes("RGB", (side, side), pixels), "JPEG", quality=quality)


def give_photo(user, data=None):
    """Make `data` (default: a red JPEG) the photo of `user` and return its version. The user must
    have a verified email, as the service requires."""
    from apps.accounts import avatars

    return avatars.save_photo(user.pk, data if data is not None else jpeg())
