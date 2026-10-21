"""The memory a photo decode needs, measured in a fresh interpreter (ARCHITECTURE §4e, §13).

Render's free instance has 512 MB for two gunicorn workers, so a crafted upload must not need
hundreds of MB. Each case writes its file in one subprocess and decodes it in another, and checks
how far the decoder's peak RSS grew above the process baseline (Django loaded, Pillow imported).
Linux only. The peak is the child's own `VmHWM` (`/proc/self/status`), **not** `ru_maxrss`: a child
starts with its parent's peak in `ru_maxrss` (it survives fork and exec), so after hundreds of tests
a big pytest process would hide up to its own size of growth (a mutation check showed whole-image
processing passing at 407 MB). The bounds leave room for another machine and sit
well under what the naive recipes cost (whole-image `reduce`: 194 MB on a 25 MP RGBA PNG, 314 MB on
a 300 x 83,000 panorama; Pillow's WebP decoder: about 16 bytes per pixel, 390 MB at 25 MP).
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="reads /proc/self/status")

BACKEND = Path(__file__).resolve().parents[3]

MAKE = textwrap.dedent(
    """
    import sys
    from PIL import Image

    kind, path = sys.argv[1], sys.argv[2]

    def gradient(size, mode):
        # A mildly varied picture (not one flat colour), built from one repeated row: fast.
        width, height = size
        row = bytes((x * 7 + (x >> 3) * 13) & 255 for x in range(width))
        if mode == "RGBA":
            line = bytes(b for v in row for b in (v, 255 - v, v ^ 90, 200))
        else:
            line = bytes(b for v in row for b in (v, 255 - v, v ^ 90))
        return Image.frombytes(mode, size, line * height)

    if kind == "rgba_25mp":
        gradient((5000, 5000), "RGBA").save(path, "PNG")
    elif kind == "rgba_panorama":
        gradient((300, 83000), "RGBA").save(path, "PNG")
    elif kind == "rgb_25mp_png":
        gradient((5000, 5000), "RGB").save(path, "PNG")
    elif kind == "jpeg_24mp":
        gradient((6000, 4000), "RGB").save(path, "JPEG", quality=85)
    elif kind == "webp_12mp":
        Image.new("RGB", (4000, 3000), (10, 120, 200)).save(path, "WEBP", lossless=True)
    elif kind == "webp_25mp":
        Image.new("RGB", (5000, 5000), (10, 120, 200)).save(path, "WEBP", lossless=True)
    elif kind == "png_bomb_64mp":
        Image.new("L", (8000, 8000)).save(path, "PNG")
    """
)

MEASURE = textwrap.dedent(
    """
    import json, sys
    import django
    django.setup()
    from apps.accounts import avatars

    def peak_kb():
        # This process's own high-water mark of resident memory.
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])

    data = open(sys.argv[1], "rb").read()
    before = peak_kb()
    try:
        avatars.process_photo(data)
        outcome = "ok"
    except avatars.PhotoRefused as refused:
        outcome = refused.detail.code
    print(json.dumps({"outcome": outcome, "grew_mb": (peak_kb() - before) / 1024}))
    """
)


def run(code, *args):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "rumor_zero.settings"}
    result = subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout


def peak(kind, tmp_path):
    path = tmp_path / kind
    run(MAKE, kind, str(path))
    assert path.stat().st_size < 5 * 1024 * 1024  # small enough to be uploaded
    return json.loads(run(MEASURE, str(path)).strip().splitlines()[-1])


@pytest.mark.parametrize(
    ("kind", "outcome", "limit_mb"),
    [
        # Accepted, at the biggest size each format allows.
        ("rgba_25mp", "ok", 170),
        ("rgba_panorama", "ok", 170),
        ("rgb_25mp_png", "ok", 150),
        ("jpeg_24mp", "ok", 40),
        ("webp_12mp", "ok", 260),
        # Refused from the header, before any pixel exists.
        ("webp_25mp", "photo_too_many_pixels", 60),
        ("png_bomb_64mp", "photo_too_many_pixels", 60),
    ],
)
def test_the_decode_stays_small(kind, outcome, limit_mb, tmp_path):
    measured = peak(kind, tmp_path)
    assert measured["outcome"] == outcome
    assert measured["grew_mb"] < limit_mb, f"{kind}: grew {measured['grew_mb']:.0f} MB"
