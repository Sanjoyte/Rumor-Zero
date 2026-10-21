"""`avatars.process_photo`: what comes out of an untrusted upload (ARCHITECTURE §4e). Every photo is
generated in the test (`photo_fixtures`)."""

import hashlib
import io
import random

import pytest
from PIL import Image, ImageFile, ImageOps

from apps.accounts import avatars
from apps.accounts.avatars import PhotoRefused, process_photo
from apps.accounts.tests import photo_fixtures as fx


def refused(data):
    with pytest.raises(PhotoRefused) as caught:
        process_photo(data)
    assert caught.value.status_code == 400
    return caught.value.detail.code


# ---------- Only pixels survive ----------


def test_the_fixture_really_carries_gps_icc_and_xmp():
    """Guards the next test from passing because there was nothing to strip."""
    source = fx.gps_jpeg()
    image = Image.open(io.BytesIO(source))
    assert image.getexif().get_ifd(0x8825)  # the GPS block
    assert image.info["icc_profile"]
    assert fx.SECRET_XMP in source and fx.SECRET_MAKER.encode() in source


def test_a_jpeg_with_gps_exif_comes_back_as_webp_with_no_metadata_at_all():
    photo = process_photo(fx.gps_jpeg())

    for data, size in ((photo.image_256, 256), (photo.image_96, 96)):
        # Read from the bytes, not through Pillow: only the picture chunk, no EXIF/ICCP/XMP.
        assert fx.riff_chunks(data) == ["VP8 "]
        assert fx.SECRET_XMP not in data and fx.SECRET_MAKER.encode() not in data
        image = Image.open(io.BytesIO(data))
        assert image.format == "WEBP" and image.size == (size, size)
        assert not image.info.get("exif") and not image.info.get("icc_profile")
        assert not image.info.get("xmp")
        assert not image.getexif()


def test_metadata_from_a_png_and_a_webp_is_dropped_too():
    exif = fx.exif_with(6)
    for source in (
        fx.encode(fx.quadrant_image(), "PNG", exif=exif, icc_profile=fx.srgb_profile()),
        fx.encode(
            fx.quadrant_image(),
            "WEBP",
            exif=exif,
            icc_profile=fx.srgb_profile(),
            xmp=fx.xmp_packet(),
        ),
    ):
        assert fx.SECRET_MAKER.encode() in source
        photo = process_photo(source)
        assert fx.riff_chunks(photo.image_256) == ["VP8 "]
        assert fx.SECRET_MAKER.encode() not in photo.image_256 + photo.image_96


def test_the_result_is_webp_at_256_and_96_and_not_the_original():
    source = fx.gps_jpeg()
    photo = process_photo(source)
    assert photo.image_256[:4] == b"RIFF" and photo.image_256[8:12] == b"WEBP"
    assert photo.image_96[8:12] == b"WEBP"
    assert source not in photo.image_256 and source[100:200] not in photo.image_256
    assert fx.decode(photo.image_256).size == (256, 256)
    assert fx.decode(photo.image_96).size == (96, 96)


def test_the_version_is_the_first_16_hex_of_the_sha256_of_the_256_image():
    photo = process_photo(fx.jpeg())
    assert photo.version == hashlib.sha256(photo.image_256).hexdigest()[:16]
    assert len(photo.version) == 16


def test_the_same_picture_gives_the_same_version_and_another_picture_another():
    first = process_photo(fx.jpeg(colour=fx.RED))
    again = process_photo(fx.jpeg(colour=fx.RED))
    other = process_photo(fx.jpeg(colour=fx.BLUE))
    assert first.version == again.version
    assert first.version != other.version


# ---------- Orientation and cropping ----------


@pytest.mark.parametrize("orientation", fx.ORIENTATIONS)
@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_every_exif_orientation_is_applied_like_pillows_own_transpose(orientation, fmt):
    source = fx.oriented(orientation, fmt)
    upright = ImageOps.exif_transpose(Image.open(io.BytesIO(source)))
    side = min(upright.size)
    left, top = (upright.width - side) // 2, (upright.height - side) // 2
    expected = fx.quadrant_colours(upright.crop((left, top, left + side, top + side)))

    fx.assert_quadrants(fx.quadrants(process_photo(source).image_256), expected)


def _which_quadrant(colour):
    return min(
        range(4),
        key=lambda i: sum(abs(a - b) for a, b in zip(colour, fx.QUADRANT_COLOURS[i], strict=True)),
    )


def test_the_eight_orientations_really_give_eight_different_pictures():
    """Otherwise the test above could pass with no rotation at all."""
    layouts = {
        tuple(
            _which_quadrant(colour)
            for colour in fx.quadrants(process_photo(fx.oriented(orientation)).image_256)
        )
        for orientation in fx.ORIENTATIONS
    }
    assert len(layouts) == 8


def test_an_orientation_6_picture_has_its_stored_top_left_in_the_top_right_corner():
    colours = fx.quadrants(process_photo(fx.oriented(6)).image_256)
    # Stored top-left is red; turned upright (rotated 90 degrees clockwise) it is top-right.
    assert fx.close(colours[1], fx.RED) and fx.close(colours[0], fx.BLUE)


def test_the_crop_is_the_exact_centre_square():
    # 400 x 200: a blue stripe on each side, red in the middle 200 columns.
    image = Image.new("RGB", (400, 200), fx.BLUE)
    image.paste(fx.RED, (100, 0, 300, 200))
    photo = process_photo(fx.encode(image, "PNG"))
    result = fx.decode(photo.image_256)
    for x, y in ((8, 8), (247, 8), (8, 247), (247, 247), (128, 128)):
        assert fx.close(result.getpixel((x, y)), fx.RED), (x, y)


def test_a_tall_picture_is_cropped_from_its_middle_rows():
    image = Image.new("RGB", (200, 600), fx.BLUE)
    image.paste(fx.GREEN, (0, 200, 200, 400))
    result = fx.decode(process_photo(fx.encode(image, "PNG")).image_256)
    for x, y in ((8, 8), (247, 247), (128, 128), (8, 247)):
        assert fx.close(result.getpixel((x, y)), fx.GREEN), (x, y)


def test_a_large_picture_is_shrunk_before_it_is_resized_but_keeps_its_content():
    # 2000 x 1500: the JPEG draft and the PNG band reduction both have to run.
    source = fx.quadrant_image(2000, 1500)
    for data in (fx.encode(source, "JPEG", quality=92), fx.encode(source, "PNG")):
        colours = fx.quadrants(process_photo(data).image_256)
        fx.assert_quadrants(colours, fx.QUADRANT_COLOURS)


def test_a_band_boundary_cuts_nothing_off_a_picture_whose_side_is_not_a_multiple():
    # 777 x 701: the shrink factor is 2 and the last band is shorter than the others.
    image = Image.new("RGB", (777, 701), fx.GREEN)
    image.paste(fx.RED, (0, 690, 777, 701))  # the last 11 rows
    result = fx.decode(process_photo(fx.encode(image, "PNG")).image_256)
    assert fx.close(result.getpixel((128, 128)), fx.GREEN)
    assert fx.close(result.getpixel((128, 255)), fx.RED)


# ---------- Colour modes ----------


def test_transparent_pixels_become_white():
    transparent = fx.encode(Image.new("RGBA", (200, 200), (255, 0, 0, 0)), "PNG")
    result = fx.decode(process_photo(transparent).image_256)
    assert fx.close(result.getpixel((100, 100)), (255, 255, 255), 8)

    half = fx.encode(Image.new("RGBA", (200, 200), (255, 0, 0, 128)), "PNG")
    red, green, blue = fx.decode(process_photo(half).image_256).getpixel((100, 100))
    assert red > 240 and 100 < green < 160 and 100 < blue < 160  # pink: red over white


def test_a_palette_png_with_a_transparent_colour_is_flattened_too():
    palette = Image.new("P", (200, 200), 0)
    palette.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    data = fx.encode(palette, "PNG", transparency=0)
    result = fx.decode(process_photo(data).image_256)
    assert fx.close(result.getpixel((100, 100)), (255, 255, 255), 8)


@pytest.mark.parametrize(
    "image",
    [
        Image.new("L", (200, 200), 90),
        Image.new("1", (200, 200), 1),
        Image.new("LA", (200, 200), (90, 255)),
        Image.new("P", (200, 200), 3),
        Image.new("RGBA", (200, 200), (10, 20, 30, 255)),
        Image.new("I;16", (200, 200), 30000),
    ],
    ids=lambda image: image.mode,
)
def test_other_png_colour_modes_are_accepted(image):
    photo = process_photo(fx.encode(image, "PNG"))
    assert fx.decode(photo.image_256).size == (256, 256)


def test_a_cmyk_and_a_greyscale_jpeg_are_accepted():
    for mode in ("CMYK", "L"):
        data = fx.encode(Image.new(mode, (200, 200)), "JPEG")
        assert fx.decode(process_photo(data).image_256).size == (256, 256)


def test_a_multi_picture_jpeg_is_read_as_its_first_frame():
    data = fx.mpo(first=fx.RED, second=fx.GREEN)
    assert Image.open(io.BytesIO(data), formats=avatars.FORMATS).format == "MPO"
    result = fx.decode(process_photo(data).image_256)
    assert fx.close(result.getpixel((128, 128)), fx.RED)


def test_the_file_name_and_the_declared_type_play_no_part_a_png_is_a_png():
    # `process_photo` sees bytes only; a PNG sent as photo.jpg is simply a PNG.
    assert fx.decode(process_photo(fx.png()).image_256).size == (256, 256)


def test_a_picture_smaller_than_256_is_still_made_256():
    assert fx.decode(process_photo(fx.png(130, 140)).image_256).size == (256, 256)


def test_the_smallest_accepted_picture_is_128_by_128():
    assert fx.decode(process_photo(fx.png(128, 128)).image_96).size == (96, 96)


# ---------- Refusals ----------


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(fx.SVG, id="svg"),
        pytest.param(fx.gif(), id="gif"),
        pytest.param(fx.HEIC, id="heic"),
        pytest.param(fx.bmp(), id="bmp"),
        pytest.param(fx.tiff(), id="tiff"),
        pytest.param(fx.apng(), id="animated-png"),
        pytest.param(fx.animated_webp(), id="animated-webp"),
        pytest.param(b"", id="empty"),
        pytest.param(b"definitely not a picture " * 40, id="garbage"),
        pytest.param(fx.jpeg()[:60], id="header-only-jpeg"),
        pytest.param(fx.png()[:-30], id="truncated-png"),
        pytest.param(fx.jpeg(400, 300)[:-400], id="truncated-jpeg"),
        pytest.param(fx.webp()[:-20], id="truncated-webp"),
    ],
)
def test_what_is_not_a_usable_jpeg_png_or_webp_is_unsupported(data):
    assert refused(data) == "photo_unsupported"


def test_more_than_5_mb_is_too_large_before_anything_is_decoded(monkeypatch):
    monkeypatch.setattr(avatars.Image, "open", lambda *a, **k: pytest.fail("decoded"))
    assert refused(b"\xff\xd8" + b"0" * avatars.MAX_UPLOAD_BYTES) == "photo_too_large"


def test_exactly_5_mb_is_not_too_large():
    data = fx.jpeg()
    padded = data + b"\x00" * (avatars.MAX_UPLOAD_BYTES - len(data))  # trailing junk is ignored
    assert len(padded) == avatars.MAX_UPLOAD_BYTES
    assert fx.decode(process_photo(padded).image_256).size == (256, 256)


@pytest.mark.parametrize("size", [(127, 500), (500, 127), (100, 100), (1, 1)])
def test_a_picture_under_128_on_either_side_is_too_small(size):
    assert refused(fx.png(*size)) == "photo_too_small"


@pytest.mark.parametrize(
    "size",
    [(5001, 5000), (6000, 6000), (8000, 8000), (100_000, 400)],
    ids=["just-over-25mp", "36mp-warns-in-pillow", "64mp-raises-in-pillow", "40mp-thin"],
)
def test_a_picture_over_25_megapixels_is_refused_without_decoding_a_pixel(size, monkeypatch):
    data = fx.flat_png(*size)  # a few KB of bytes for tens of millions of pixels
    assert len(data) < avatars.MAX_UPLOAD_BYTES

    def never(self, *args, **kwargs):
        raise AssertionError("the bomb was decoded")

    monkeypatch.setattr(ImageFile.ImageFile, "load", never)
    assert refused(data) == "photo_too_many_pixels"


def test_exactly_25_megapixels_is_allowed():
    assert fx.decode(process_photo(fx.flat_png(5000, 5000)).image_256).size == (256, 256)


def test_a_webp_over_12_megapixels_is_refused_before_its_expensive_decode(monkeypatch):
    # Pillow decodes WebP through its animation decoder: about 16 bytes per pixel.
    data = fx.encode(Image.new("RGB", (4000, 3001)), "WEBP", lossless=True)
    assert len(data) < 100_000

    def never(self, *args, **kwargs):
        raise AssertionError("the WebP was decoded")

    monkeypatch.setattr(ImageFile.ImageFile, "load", never)
    assert refused(data) == "photo_too_many_pixels"


def test_a_webp_of_exactly_12_megapixels_is_allowed():
    data = fx.encode(Image.new("RGB", (4000, 3000), fx.GREEN), "WEBP", lossless=True)
    assert fx.close(fx.decode(process_photo(data).image_256).getpixel((100, 100)), fx.GREEN)


def test_a_jpeg_or_png_between_12_and_25_megapixels_is_not_held_to_the_webp_limit():
    assert fx.decode(process_photo(fx.flat_png(4000, 4000)).image_256).size == (256, 256)


def test_every_refusal_has_a_message_a_person_can_read():
    for code in avatars.MESSAGES:
        error = PhotoRefused(code)
        assert error.detail == avatars.MESSAGES[code] and error.detail.code == code
        assert error.detail.endswith(".")


# ---------- Only the three decoders ever see the bytes ----------


def test_pillow_is_asked_for_jpeg_png_and_webp_and_nothing_else(monkeypatch):
    seen = {}
    real_open = avatars.Image.open

    def spy(fp, mode="r", formats=None):
        seen["formats"] = formats
        return real_open(fp, mode, formats)

    monkeypatch.setattr(avatars.Image, "open", spy)
    process_photo(fx.jpeg())
    assert tuple(seen["formats"]) == ("JPEG", "PNG", "WEBP")


def test_pillows_pixel_limit_is_set_so_a_giant_header_raises_at_open():
    assert Image.MAX_IMAGE_PIXELS == avatars.MAX_PIXELS == 25_000_000


# ---------- Whatever the bytes, the answer is a photo or a refusal, never a crash ----------


def _mutations(rng, data):
    kind = rng.choice(["truncate", "flip", "insert", "zero", "swap"])
    raw = bytearray(data)
    if kind == "truncate":
        return bytes(raw[: rng.randrange(1, len(raw))])
    if kind == "flip":
        for _ in range(rng.randrange(1, 12)):
            raw[rng.randrange(len(raw))] ^= 1 << rng.randrange(8)
    elif kind == "insert":
        at = rng.randrange(len(raw))
        raw[at:at] = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 40)))
    elif kind == "zero":
        at = rng.randrange(len(raw))
        raw[at : at + rng.randrange(1, 60)] = b"\x00" * rng.randrange(1, 60)
    else:
        a, b = rng.randrange(len(raw)), rng.randrange(len(raw))
        raw[a], raw[b] = raw[b], raw[a]
    return bytes(raw)


def test_damaged_files_never_crash_the_decoder_into_a_500():
    rng = random.Random(14)
    samples = [
        fx.gps_jpeg(300, 200, orientation=6),
        fx.png(300, 200),
        fx.encode(Image.new("RGBA", (260, 260), (1, 2, 3, 99)), "PNG"),
        fx.webp(),
        fx.mpo(),
        fx.apng(),
        fx.animated_webp(),
        fx.gif(),
    ]
    outcomes = {"photo": 0, "refused": 0}
    for _ in range(400):
        data = _mutations(rng, rng.choice(samples))
        try:
            process_photo(data)
            outcomes["photo"] += 1
        except PhotoRefused:
            outcomes["refused"] += 1
    # Some survive (a flipped pixel byte), most don't: both paths were really taken.
    assert outcomes["photo"] > 0 and outcomes["refused"] > 0
