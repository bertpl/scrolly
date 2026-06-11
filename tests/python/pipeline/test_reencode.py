"""Tests for the bitmap re-encoding tournament (``pipeline/_reencode.py``).

Encoder availability differs across machines (e.g. ``cwebp`` may be
absent), so these tests assert on *invariants* — original always
competes, alpha is preserved, ineligible payloads pass through, counts
are post-dedup — rather than on exact byte counts of any one codec.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from scrolly.pipeline import _reencode
from scrolly.pipeline._reencode import BitmapReencoder


# ==================================================================================================
#  Fixtures
# ==================================================================================================
def _png(image: Image.Image) -> bytes:
    """Encode ``image`` to PNG bytes."""
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _gradient_rgb(size: int = 64) -> Image.Image:
    """A smoothly-varying RGB image (re-encodes smaller than PNG)."""
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = (x * 4 % 256, y * 4 % 256, (x * y) % 256)
    return image


def _gradient_rgba(size: int = 64) -> Image.Image:
    """An RGBA image with a diagonal alpha gradient over varying color."""
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = (x * 4 % 256, y * 4 % 256, 128, (x + y) * 2 % 256)
    return image


def _animated_gif() -> bytes:
    """A two-frame GIF (an out-of-scope, must-be-skipped multi-frame asset)."""
    red = Image.new("RGB", (8, 8), (255, 0, 0))
    blue = Image.new("RGB", (8, 8), (0, 0, 255))
    buffer = io.BytesIO()
    red.save(buffer, "GIF", save_all=True, append_images=[blue], duration=100, loop=0)
    return buffer.getvalue()


# ==================================================================================================
#  Eligibility / pass-through
# ==================================================================================================
def test_non_image_mime_passes_through_unconsidered() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(95)
    raw = b"<svg/>"

    # --- act --------------------------
    out, mime = reencoder.process(raw, "image/svg+xml")

    # --- assert -----------------------
    assert (out, mime) == (raw, "image/svg+xml")
    assert reencoder.stats().considered == 0


def test_animated_gif_is_skipped() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(95)
    raw = _animated_gif()

    # --- act --------------------------
    out, mime = reencoder.process(raw, "image/gif")

    # --- assert -----------------------
    # Multi-frame: shipped untouched and not counted as an eligible bitmap.
    assert (out, mime) == (raw, "image/gif")
    assert reencoder.stats().considered == 0


def test_undecodable_bytes_pass_through() -> None:
    # --- arrange / act ----------------
    reencoder = BitmapReencoder(95)
    out, mime = reencoder.process(b"not really a png", "image/png")

    # --- assert -----------------------
    assert (out, mime) == (b"not really a png", "image/png")
    assert reencoder.stats().considered == 0


# ==================================================================================================
#  Off / original-wins
# ==================================================================================================
def test_off_counts_but_does_not_encode() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(None)
    raw = _png(_gradient_rgb())

    # --- act --------------------------
    out, mime = reencoder.process(raw, "image/png")

    # --- assert -----------------------
    assert out is raw and mime == "image/png"
    stats = reencoder.stats()
    assert (stats.quality, stats.considered, stats.reencoded, stats.bytes_saved) == (None, 1, 0, 0)


def test_original_wins_when_no_candidate_is_smaller(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    # Force every candidate larger than the source: the original must win
    # (the guard is on size), and nothing is counted as flipped.
    reencoder = BitmapReencoder(95)
    raw = _png(_gradient_rgb())
    monkeypatch.setattr(_reencode, "_encode_candidates", lambda *a, **k: [(raw + b"xx", "image/webp")])

    # --- act --------------------------
    out, mime = reencoder.process(raw, "image/png")

    # --- assert -----------------------
    assert out is raw and mime == "image/png"
    stats = reencoder.stats()
    assert stats.considered == 1 and stats.reencoded == 0 and stats.bytes_saved == 0


@pytest.mark.parametrize("factory", [_gradient_rgb, _gradient_rgba, lambda: Image.new("RGB", (1, 1), (10, 20, 30))])
def test_re_encoding_never_enlarges(factory) -> None:
    # --- arrange / act ----------------
    raw = _png(factory())
    out, _ = BitmapReencoder(95).process(raw, "image/png")

    # --- assert -----------------------
    assert len(out) <= len(raw)


# ==================================================================================================
#  Format flip / dedup
# ==================================================================================================
def test_gradient_png_flips_to_smaller_format() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(95)
    raw = _png(_gradient_rgb())

    # --- act --------------------------
    out, mime = reencoder.process(raw, "image/png")

    # --- assert -----------------------
    assert mime in ("image/webp", "image/avif")
    assert len(out) < len(raw)
    stats = reencoder.stats()
    assert stats.reencoded == 1 and stats.bytes_saved == len(raw) - len(out)


def test_duplicate_bytes_encoded_once() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(95)
    raw = _png(_gradient_rgb())

    # --- act --------------------------
    first = reencoder.process(raw, "image/png")
    second = reencoder.process(raw, "image/png")

    # --- assert -----------------------
    # Cache hit returns the same result and keeps the tally post-dedup.
    assert first == second
    assert reencoder.stats().considered == 1


# ==================================================================================================
#  Alpha preservation
# ==================================================================================================
def test_alpha_channel_is_preserved_bit_exact() -> None:
    # --- arrange ----------------------
    reencoder = BitmapReencoder(95)
    original = _gradient_rgba()
    raw = _png(original)

    # --- act --------------------------
    out, _ = reencoder.process(raw, "image/png")

    # --- assert -----------------------
    # Whichever candidate wins, the alpha plane is never lossy.
    decoded = Image.open(io.BytesIO(out)).convert("RGBA")
    assert decoded.getchannel("A").tobytes() == original.getchannel("A").tobytes()


def test_palette_with_transparency_normalizes_to_rgba() -> None:
    # --- arrange ----------------------
    palette = Image.new("P", (8, 8), color=0)
    palette.info["transparency"] = 0

    # --- act --------------------------
    normalized = _reencode._normalize_mode(palette)

    # --- assert -----------------------
    assert normalized.mode == "RGBA"


# ==================================================================================================
#  cwebp-absent path
# ==================================================================================================
def test_near_lossless_skipped_without_cwebp(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    monkeypatch.setattr(_reencode, "_cwebp_path", lambda: None)

    # --- act --------------------------
    candidate = _reencode._webp_near_lossless(_png(_gradient_rgb()), 95)

    # --- assert -----------------------
    assert candidate is None
