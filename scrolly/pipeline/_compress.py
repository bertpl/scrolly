"""Shared gzip+base64 compression primitives for inlined payloads.

Used by the iframe renderer (srcdoc content) and the asset pipeline
(image data URIs) to decide per-payload whether gzip compression
shrinks the inlined form enough to justify client-side decompression.
"""

from __future__ import annotations

import base64
import gzip
from dataclasses import dataclass

GZIP_LEVEL = 9
MIN_SAVING = 0.10


@dataclass(frozen=True)
class CompressionStats:
    """Aggregate compression statistics across one or more payloads."""

    compressed: int = 0
    bytes_saved: int = 0

    def __add__(self, other: CompressionStats) -> CompressionStats:
        """Combine two stats values element-wise."""
        return CompressionStats(
            compressed=self.compressed + other.compressed,
            bytes_saved=self.bytes_saved + other.bytes_saved,
        )


@dataclass(frozen=True)
class CompressionResult:
    """Outcome of a single compression attempt against the 5% gate."""

    packed: str | None
    bytes_saved: int


def pack_gzip_b64(raw: bytes) -> str:
    """Gzip-compress and base64-encode raw bytes.

    Args:
        raw: The raw bytes to compress.

    Returns:
        Base64-encoded ASCII string of the gzipped bytes.
    """
    return base64.b64encode(gzip.compress(raw, GZIP_LEVEL)).decode("ascii")


def worth_compressing(packed_len: int, baseline_len: int) -> bool:
    """Check whether the compressed form saves at least MIN_SAVING of the baseline.

    Args:
        packed_len: Length of the compressed+encoded payload.
        baseline_len: Length of the uncompressed inlined form.

    Returns:
        True if the compressed form is at least 10% smaller. The headroom
        absorbs the surrounding HTML attribute-structure overhead difference
        between the compressed and uncompressed forms (which the comparison
        itself doesn't account for) and keeps small wins from being eaten by
        that overhead.
    """
    if baseline_len <= 0:
        return False
    return packed_len <= baseline_len * (1.0 - MIN_SAVING)


def try_compress(raw: bytes, baseline_len: int) -> CompressionResult:
    """Compress raw bytes and accept the result only if it passes the gate.

    Args:
        raw: Raw bytes to compress.
        baseline_len: Size of the uncompressed inlined form, used for the gate.

    Returns:
        A `CompressionResult` whose `packed` is the base64 payload when the
        gate passes, or `None` when it doesn't. `bytes_saved` is the
        baseline-vs-packed delta, or 0 when not compressed.
    """
    packed = pack_gzip_b64(raw)
    if worth_compressing(len(packed), baseline_len):
        return CompressionResult(packed=packed, bytes_saved=baseline_len - len(packed))
    return CompressionResult(packed=None, bytes_saved=0)
