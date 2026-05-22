"""Tests for scrolly.pipeline._compress — gzip+base64 compression gate."""

from __future__ import annotations

import base64
import gzip

import pytest

from scrolly.pipeline._compress import (
    MIN_SAVING,
    CompressionStats,
    pack_gzip_b64,
    try_compress,
    worth_compressing,
)


def test_pack_gzip_b64_roundtrips() -> None:
    # --- arrange ----------------------------
    raw = b"hello world, this is compressible content " * 10

    # --- act --------------------------------
    packed = pack_gzip_b64(raw)

    # --- assert ------------------------------
    recovered = gzip.decompress(base64.b64decode(packed))
    assert recovered == raw


def test_pack_gzip_b64_returns_ascii_string() -> None:
    # --- arrange / act ----------------------
    packed = pack_gzip_b64(b"test data")

    # --- assert ------------------------------
    assert isinstance(packed, str)
    assert packed == packed.encode("ascii").decode("ascii")


@pytest.mark.parametrize(
    ("packed_len", "baseline_len", "expected"),
    [
        (80, 100, True),
        (90, 100, True),
        (91, 100, False),
        (95, 100, False),
        (100, 100, False),
        (0, 0, False),
        (50, 0, False),
    ],
    ids=[
        "20%-saving-passes",
        "exact-10%-passes",
        "just-under-10%-fails",
        "5%-saving-fails",
        "no-saving-fails",
        "zero-baseline-fails",
        "zero-baseline-nonzero-packed-fails",
    ],
)
def test_worth_compressing_boundary(packed_len: int, baseline_len: int, expected: bool) -> None:
    assert worth_compressing(packed_len, baseline_len) is expected


def test_min_saving_is_ten_percent() -> None:
    assert MIN_SAVING == 0.10


def test_try_compress_returns_packed_when_gate_passes() -> None:
    # --- arrange ----------------------------
    raw = b"compressible payload " * 50

    # --- act --------------------------------
    result = try_compress(raw, baseline_len=len(raw))

    # --- assert ------------------------------
    assert result.packed is not None
    assert result.bytes_saved > 0
    assert gzip.decompress(base64.b64decode(result.packed)) == raw


def test_try_compress_returns_none_when_gate_fails() -> None:
    # --- arrange ----------------------------
    raw = b"x"

    # --- act --------------------------------
    result = try_compress(raw, baseline_len=len(raw))

    # --- assert ------------------------------
    assert result.packed is None
    assert result.bytes_saved == 0


def test_try_compress_zero_baseline_returns_none() -> None:
    # --- arrange / act ----------------------
    result = try_compress(b"anything", baseline_len=0)

    # --- assert ------------------------------
    assert result.packed is None
    assert result.bytes_saved == 0


def test_compression_stats_addition() -> None:
    # --- arrange ----------------------------
    a = CompressionStats(compressed=2, bytes_saved=100)
    b = CompressionStats(compressed=3, bytes_saved=250)

    # --- act --------------------------------
    total = a + b

    # --- assert ------------------------------
    assert total == CompressionStats(compressed=5, bytes_saved=350)


def test_compression_stats_sum_with_default_start() -> None:
    # --- arrange ----------------------------
    parts = [
        CompressionStats(compressed=1, bytes_saved=10),
        CompressionStats(compressed=2, bytes_saved=20),
        CompressionStats(compressed=0, bytes_saved=0),
    ]

    # --- act --------------------------------
    total = sum(parts, CompressionStats())

    # --- assert ------------------------------
    assert total == CompressionStats(compressed=3, bytes_saved=30)
