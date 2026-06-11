"""Bitmap re-encoding: ship the smallest encoding of each raster asset.

For every eligible bitmap, several candidates are encoded — lossless
WebP, lossy WebP, AVIF, and (when ``cwebp`` is on ``PATH``) near-lossless
WebP — and the smallest is kept. The original always competes, so
re-encoding can never enlarge a deck: the guard is on *size*, with visual
fidelity protected by the quality setting rather than by the size guard.

SVG (vector), animated GIF/WebP (multi-frame re-encoding is out of scope),
and non-image payloads pass through untouched. Results are cached by input
bytes for the lifetime of one :class:`BitmapReencoder`, so a duplicate
asset is encoded once and the considered/re-encoded tallies stay
post-dedup — consistent with the help screen's ``Unique`` counts.

The module is a sibling of ``_bundler`` in style: a small stateful
collaborator instantiated per build, threaded through
``pipeline.assets._inline_refs`` (the seam that already reads each asset's
bytes), and snapshotted via :meth:`BitmapReencoder.stats` for the help
screen.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

# Raster mimes the tournament accepts. SVG (``image/svg+xml``) is excluded
# by construction — it is vector and near-free in the compressed stream.
_ELIGIBLE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"})

_WEBP_MIME = "image/webp"
_AVIF_MIME = "image/avif"


# ==================================================================================================
#  Value types
# ==================================================================================================
@dataclass(frozen=True)
class ReencodeStats:
    """Snapshot of one build's bitmap re-encoding, for the help screen.

    ``quality`` is ``None`` when re-encoding was off (``considered`` is
    still populated so the help screen can show ``off`` against the real
    eligible-bitmap count). ``considered`` and ``reencoded`` are
    post-dedup counts of unique eligible bitmaps; ``bytes_saved`` is the
    raw asset-byte saving summed over the bitmaps that flipped.
    """

    quality: int | None
    considered: int
    reencoded: int
    bytes_saved: int

    def as_dict(self) -> dict[str, int | None]:
        """Return the help-screen JSON form (the ``reencoding`` stats block)."""
        return {
            "quality": self.quality,
            "considered": self.considered,
            "reencoded": self.reencoded,
            "bytes_saved": self.bytes_saved,
        }


# ==================================================================================================
#  BitmapReencoder
# ==================================================================================================
class BitmapReencoder:
    """Runs the per-asset encoding tournament and tallies the outcome.

    Constructed with the quality setting (``None`` = off); call
    :meth:`process` for each asset's bytes and mime, and :meth:`stats`
    once at the end for the help-screen snapshot.
    """

    # --------------------------------------------------------------------------
    #  Constructor
    # --------------------------------------------------------------------------
    def __init__(self, quality: int | None) -> None:
        """Initialize with the quality setting (``None`` disables encoding)."""
        self._quality = quality
        self._cache: dict[bytes, tuple[bytes, str]] = {}
        self._considered = 0
        self._reencoded = 0
        self._bytes_saved = 0

    # --------------------------------------------------------------------------
    #  Main API
    # --------------------------------------------------------------------------
    def process(self, raw: bytes, mime: str) -> tuple[bytes, str]:
        """Return the bytes and mime to ship for one asset.

        Ineligible payloads (non-raster mimes, animated or undecodable
        bitmaps) and the off setting return the input unchanged. Otherwise
        the smallest tournament candidate wins, falling back to the
        original on a tie so re-encoding never enlarges the asset.

        Args:
            raw: The asset's raw bytes.
            mime: The asset's mime type (from its file extension).

        Returns:
            ``(bytes, mime)`` to ship — possibly the inputs unchanged.
        """
        if mime not in _ELIGIBLE_MIMES:
            return raw, mime
        cached = self._cache.get(raw)
        if cached is not None:
            return cached
        chosen = self._run_tournament(raw, mime)
        self._cache[raw] = chosen
        return chosen

    def stats(self) -> ReencodeStats:
        """Snapshot the considered / re-encoded / saved tallies."""
        return ReencodeStats(
            quality=self._quality,
            considered=self._considered,
            reencoded=self._reencoded,
            bytes_saved=self._bytes_saved,
        )

    # --------------------------------------------------------------------------
    #  Internals
    # --------------------------------------------------------------------------
    def _run_tournament(self, raw: bytes, mime: str) -> tuple[bytes, str]:
        """Encode candidates for one eligible bitmap and keep the smallest.

        Counts the bitmap as considered once it is confirmed static and
        decodable; encodes only when a quality is set. Updates the
        re-encoded count and byte saving when a candidate beats the
        original.
        """
        image = _open_static(raw)
        if image is None:
            return raw, mime
        self._considered += 1
        if self._quality is None:
            return raw, mime

        normalized = _normalize_mode(image)
        best_bytes, best_mime = raw, mime
        for candidate in _encode_candidates(normalized, raw, self._quality):
            if len(candidate[0]) < len(best_bytes):
                best_bytes, best_mime = candidate

        if best_bytes is not raw:
            self._reencoded += 1
            self._bytes_saved += len(raw) - len(best_bytes)
        return best_bytes, best_mime


# ==================================================================================================
#  Image preparation
# ==================================================================================================
def _open_static(raw: bytes) -> Image.Image | None:
    """Decode ``raw`` to a single-frame image, or ``None`` if unfit.

    Returns ``None`` for anything that can't be decoded or that carries
    more than one frame (animated GIF/WebP), so multi-frame assets ship
    untouched and don't count toward the considered tally.
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        return None
    if getattr(image, "n_frames", 1) > 1:
        return None
    return image


def _normalize_mode(image: Image.Image) -> Image.Image:
    """Convert to ``RGB`` / ``RGBA`` so encoders can't flatten transparency.

    Palette images with transparency become ``RGBA`` (rather than being
    flattened by the encoder); every other mode collapses to ``RGB`` or
    ``RGBA`` by whether it carries an alpha channel.
    """
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    target = "RGBA" if has_alpha else "RGB"
    if image.mode != target:
        return image.convert(target)
    return image


# ==================================================================================================
#  Candidate encoders
# ==================================================================================================
def _encode_candidates(
    image: Image.Image,
    raw: bytes,
    quality: int,
) -> list[tuple[bytes, str]]:
    """Encode every available candidate for ``image``; drop the ones that fail.

    Args:
        image: The mode-normalized image.
        raw: The original bytes (input to the ``cwebp`` near-lossless pass,
            which decodes the source itself).
        quality: The quality setting passed through to each codec's native
            scale (no perceptual calibration).

    Returns:
        ``(bytes, mime)`` for each candidate that encoded successfully.
        Encoder failures are skipped — the original still competes in the
        caller, so a missing candidate only forgoes a potential saving.
    """
    has_alpha = image.mode == "RGBA"
    candidates: list[tuple[bytes, str] | None] = [
        _webp_lossless(image),
        _webp_lossy(image, quality),
        _avif(image, quality, has_alpha=has_alpha),
        _webp_near_lossless(raw, quality),
    ]
    return [candidate for candidate in candidates if candidate is not None]


def _save(image: Image.Image, fmt: str, **options: object) -> bytes:
    """Encode ``image`` to ``fmt`` in memory and return the bytes."""
    buffer = io.BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def _webp_lossless(image: Image.Image) -> tuple[bytes, str] | None:
    """Lossless WebP candidate (carries alpha bit-exact)."""
    try:
        data = _save(image, "WEBP", lossless=True, quality=100, method=5, exact=False)
    except Exception:
        return None
    return data, _WEBP_MIME


def _webp_lossy(image: Image.Image, quality: int) -> tuple[bytes, str] | None:
    """Lossy WebP candidate; alpha plane kept lossless via ``alpha_quality``."""
    try:
        data = _save(
            image,
            "WEBP",
            quality=quality,
            method=5,
            alpha_quality=100,
            use_sharp_yuv=True,
        )
    except Exception:
        return None
    return data, _WEBP_MIME


def _avif(image: Image.Image, quality: int, *, has_alpha: bool) -> tuple[bytes, str] | None:
    """AVIF candidate at ``speed=4``, full-range 4:4:4 to protect chroma edges."""
    options: dict[str, object] = {
        "quality": quality,
        "speed": 4,
        "subsampling": "4:4:4",
        "range": "full",
    }
    if has_alpha:
        options["alpha_quality"] = 100
    try:
        data = _save(image, "AVIF", **options)
    except Exception:
        return None
    return data, _AVIF_MIME


def _webp_near_lossless(raw: bytes, quality: int) -> tuple[bytes, str] | None:
    """Near-lossless WebP via ``cwebp`` — skipped silently when it's absent.

    No pure-pip encoder exposes libwebp's near-lossless knob, so this
    candidate shells out to ``cwebp`` when it is on ``PATH``; otherwise it
    is omitted from the tournament. ``cwebp`` decodes the source itself, so
    it receives the original bytes rather than a re-encoded intermediate.
    """
    cwebp = _cwebp_path()
    if cwebp is None:
        return None
    level = _near_lossless_level(quality)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            dst = Path(tmp) / "out.webp"
            src.write_bytes(raw)
            subprocess.run(
                [
                    cwebp,
                    "-near_lossless",
                    str(level),
                    "-sharp_yuv",
                    "-m",
                    "5",
                    "-alpha_q",
                    "100",
                    "-mt",
                    "-quiet",
                    str(src),
                    "-o",
                    str(dst),
                ],
                check=True,
                capture_output=True,
            )
            data = dst.read_bytes()
    except Exception:
        return None
    return data, _WEBP_MIME


def _near_lossless_level(quality: int) -> int:
    """Snap a quality value to ``cwebp``'s coarse near-lossless grid (steps of 20)."""
    return max(0, min(100, round(quality / 20) * 20))


@lru_cache(maxsize=1)
def _cwebp_path() -> str | None:
    """Return the ``cwebp`` executable path, or ``None`` when it isn't installed."""
    return shutil.which("cwebp")
