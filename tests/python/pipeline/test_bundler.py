"""Tests for scrolly.pipeline._bundler — PayloadBundler and the 5% gate."""

from __future__ import annotations

import base64
import gzip
import json

import pytest

from scrolly.pipeline._bundler import (
    MIN_SAVING,
    BundleStats,
    PayloadBundler,
    _gate_passes,
)


# ==================================================================================================
#  Gate
# ==================================================================================================
def test_min_saving_is_five_percent() -> None:
    assert MIN_SAVING == 0.05


@pytest.mark.parametrize(
    ("compressed_len", "baseline_len", "expected"),
    [
        (50, 100, True),  # 50% saving — passes comfortably
        (94, 100, True),  # 6% saving — passes
        (95, 100, True),  # 5% saving — boundary, passes (<=)
        (96, 100, False),  # 4% saving — just under, fails
        (100, 100, False),  # no saving — fails
        (120, 100, False),  # net larger — fails
        (0, 0, False),  # empty baseline — fails
        (50, 0, False),  # zero baseline, non-zero packed — fails
    ],
    ids=[
        "50%-saving-passes",
        "6%-saving-passes",
        "exact-5%-boundary-passes",
        "4%-saving-fails",
        "no-saving-fails",
        "net-larger-fails",
        "zero-baseline-fails",
        "zero-baseline-nonzero-compressed-fails",
    ],
)
def test_gate_passes_boundary(
    compressed_len: int,
    baseline_len: int,
    expected: bool,
) -> None:
    assert _gate_passes(compressed_len, baseline_len) is expected


# ==================================================================================================
#  add() — slot ids and dedup
# ==================================================================================================
def test_add_returns_sequential_string_ids() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()

    # --- act --------------------------------
    ids = [
        b.add(payload=b"a", mode="text", attr="srcdoc", baseline_len=1),
        b.add(payload=b"b", mode="text", attr="srcdoc", baseline_len=1),
        b.add(payload=b"c", mode="text", attr="srcdoc", baseline_len=1),
    ]

    # --- assert ------------------------------
    assert ids == ["0", "1", "2"]


def test_add_dedups_identical_payload_mode_mime() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    payload = b"<p>hello</p>" * 20

    # --- act --------------------------------
    id0 = b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=240)
    id1 = b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=240)
    id2 = b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=240)

    # --- assert ------------------------------
    # Three distinct targets, all pointing at the same single payload.
    assert (id0, id1, id2) == ("0", "1", "2")
    result = b.build()
    assert result is not None
    manifest = json.loads(result[0])
    assert len(manifest["payloads"]) == 1
    assert len(manifest["targets"]) == 3
    assert all(t["payload"] == 0 for t in manifest["targets"])


def test_add_does_not_dedup_across_mode() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    payload = b"<p>shared compressible content</p>" * 30

    # --- act --------------------------------
    b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=len(payload))
    b.add(payload=payload, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(payload))

    # --- assert ------------------------------
    result = b.build()
    assert result is not None
    manifest = json.loads(result[0])
    assert len(manifest["payloads"]) == 2


def test_add_does_not_dedup_across_mime() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>' * 20

    # --- act --------------------------------
    b.add(payload=payload, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(payload))
    b.add(payload=payload, mode="blob", attr="src", mime="image/png", baseline_len=len(payload))

    # --- assert ------------------------------
    result = b.build()
    assert result is not None
    manifest = json.loads(result[0])
    assert len(manifest["payloads"]) == 2


def test_add_blob_requires_mime() -> None:
    # --- arrange / act / assert -------------
    b = PayloadBundler()
    with pytest.raises(ValueError, match="mime is required"):
        b.add(payload=b"x", mode="blob", attr="src", baseline_len=1)


def test_add_text_rejects_mime() -> None:
    # --- arrange / act / assert -------------
    b = PayloadBundler()
    with pytest.raises(ValueError, match="mime must be None"):
        b.add(payload=b"x", mode="text", attr="srcdoc", mime="text/plain", baseline_len=1)


# ==================================================================================================
#  build() — output shape and round-trip
# ==================================================================================================
def test_build_returns_none_when_empty() -> None:
    # --- arrange / act ----------------------
    result = PayloadBundler().build()

    # --- assert ------------------------------
    assert result is None


def test_build_returns_none_when_gate_fails() -> None:
    # --- arrange ----------------------------
    # Tiny single payload — gzip header overhead exceeds any saving.
    b = PayloadBundler()
    b.add(payload=b"x", mode="text", attr="srcdoc", baseline_len=1)

    # --- act --------------------------------
    result = b.build()

    # --- assert ------------------------------
    assert result is None


def test_build_returns_bundle_when_gate_passes() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = "hello compressible world " * 50
    b.add(payload=text.encode("utf-8"), mode="text", attr="srcdoc", baseline_len=len(text))

    # --- act --------------------------------
    result = b.build()

    # --- assert ------------------------------
    assert result is not None
    payload_json, stats = result
    assert isinstance(payload_json, str)
    assert isinstance(stats, BundleStats)


def test_build_manifest_has_expected_shape() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>some compressible html</p>" * 20
    blob_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(
        payload=blob_bytes,
        mode="blob",
        attr="src",
        mime="image/png",
        baseline_len=len(base64.b64encode(blob_bytes)),
    )

    # --- act --------------------------------
    result = b.build()

    # --- assert ------------------------------
    assert result is not None
    manifest = json.loads(result[0])
    assert set(manifest) == {"payloads", "targets", "blob"}
    # Text payload entry: {mode, length}; no mime.
    assert manifest["payloads"][0] == {"mode": "text", "length": len(text)}
    # Blob payload entry: {mode, mime, length}.
    assert manifest["payloads"][1] == {
        "mode": "blob",
        "mime": "image/png",
        "length": len(blob_bytes),
    }
    # Target entries: {id, attr, payload}.
    assert manifest["targets"][0] == {"id": "0", "attr": "srcdoc", "payload": 0}
    assert manifest["targets"][1] == {"id": "1", "attr": "src", "payload": 1}


def test_build_roundtrips_payloads() -> None:
    # --- arrange ----------------------------
    # A mix of text and binary, with one dedup.
    b = PayloadBundler()
    text_a = b"<p>alpha alpha alpha</p>" * 10
    text_b = b"<p>bravo bravo bravo</p>" * 10
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect/></svg>' * 5
    b.add(payload=text_a, mode="text", attr="srcdoc", baseline_len=len(text_a))
    b.add(payload=text_b, mode="text", attr="srcdoc", baseline_len=len(text_b))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=text_a, mode="text", attr="srcdoc", baseline_len=len(text_a))  # dedup'd

    # --- act --------------------------------
    result = b.build()
    assert result is not None
    payload_json, _ = result
    manifest = json.loads(payload_json)

    # Decode the blob, decompress, slice per manifest lengths.
    raw = gzip.decompress(base64.b64decode(manifest["blob"]))
    offset = 0
    recovered: list[bytes] = []
    for entry in manifest["payloads"]:
        length = entry["length"]
        recovered.append(raw[offset : offset + length])
        offset += length

    # --- assert ------------------------------
    assert offset == len(raw), "manifest lengths must cover the whole stream"
    assert len(manifest["payloads"]) == 3, "duplicate payload should dedup to one entry"
    assert len(manifest["targets"]) == 4, "each add registers one target"
    assert recovered[0] == text_a
    assert recovered[1] == text_b
    assert recovered[2] == svg
    # The dedup'd 4th target points at payload index 0 (text_a's slot).
    assert manifest["targets"][3]["payload"] == 0


# ==================================================================================================
#  inline_fallback()
# ==================================================================================================
def test_inline_fallback_text_payload_html_escapes() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    b.add(payload=b"<p>x</p>", mode="text", attr="srcdoc", baseline_len=8)

    # --- act --------------------------------
    fallback = b.inline_fallback()

    # --- assert ------------------------------
    assert fallback == {"0": 'srcdoc="&lt;p&gt;x&lt;/p&gt;"'}


def test_inline_fallback_blob_payload_emits_data_uri() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    raw = b"\x00\x01\x02svg-ish"
    b.add(payload=raw, mode="blob", attr="src", mime="image/svg+xml", baseline_len=16)

    # --- act --------------------------------
    fallback = b.inline_fallback()

    # --- assert ------------------------------
    encoded = base64.b64encode(raw).decode("ascii")
    assert fallback == {"0": f'src="data:image/svg+xml;base64,{encoded}"'}


def test_inline_fallback_dedup_produces_one_entry_per_target() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    payload = b"<p>shared</p>"
    b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=13)
    b.add(payload=payload, mode="text", attr="srcdoc", baseline_len=13)

    # --- act --------------------------------
    fallback = b.inline_fallback()

    # --- assert ------------------------------
    assert set(fallback) == {"0", "1"}
    # Both targets resolve to the same substitute string.
    assert fallback["0"] == fallback["1"]


# ==================================================================================================
#  BundleStats
# ==================================================================================================
def test_bundle_stats_counts_and_partition() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>compressible html content</p>" * 30
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>' * 10
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))  # dedup

    # --- act --------------------------------
    result = b.build()
    assert result is not None
    _, stats = result

    # --- assert ------------------------------
    assert stats.payloads_count == 2
    assert stats.targets_count == 3
    assert stats.text_payloads == 1
    assert stats.blob_payloads == 1
    assert stats.text_payloads + stats.blob_payloads == stats.payloads_count


def test_bundle_stats_bytes_saved_property() -> None:
    # --- arrange ----------------------------
    stats = BundleStats(
        payloads_count=1,
        targets_count=1,
        text_payloads=1,
        blob_payloads=0,
        baseline_bytes=1000,
        compressed_bytes=600,
    )

    # --- act / assert ------------------------
    assert stats.bytes_saved == 400


def test_bundle_stats_baseline_sums_across_adds_including_duplicates() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>compressible content</p>" * 40
    # Three calls — baseline accumulates each, even though dedup keeps payloads at 1.
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))

    # --- act --------------------------------
    result = b.build()
    assert result is not None
    _, stats = result

    # --- assert ------------------------------
    assert stats.baseline_bytes == 3 * len(text)
    assert stats.payloads_count == 1
    assert stats.targets_count == 3
