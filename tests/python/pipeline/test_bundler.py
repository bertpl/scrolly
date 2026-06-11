"""Tests for scrolly.pipeline._bundler — PayloadBundler and the 5% gate."""

from __future__ import annotations

import base64
import json

import pytest

from scrolly.pipeline._bundler import (
    MIN_SAVING,
    BundleStats,
    PayloadBundler,
    gate_passes,
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
    assert gate_passes(compressed_len, baseline_len) is expected


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
    manifest = json.loads(b.manifest_and_stream()[0])
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
    manifest = json.loads(b.manifest_and_stream()[0])
    assert len(manifest["payloads"]) == 2


def test_add_does_not_dedup_across_mime() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>' * 20

    # --- act --------------------------------
    b.add(payload=payload, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(payload))
    b.add(payload=payload, mode="blob", attr="src", mime="image/png", baseline_len=len(payload))

    # --- assert ------------------------------
    manifest = json.loads(b.manifest_and_stream()[0])
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
#  manifest_and_stream() — output shape and round-trip
# ==================================================================================================
def test_manifest_and_stream_empty_bundler() -> None:
    # --- arrange / act ----------------------
    manifest_json, stream = PayloadBundler().manifest_and_stream()

    # --- assert ------------------------------
    assert json.loads(manifest_json) == {"payloads": [], "targets": []}
    assert stream == b""


def test_manifest_has_expected_shape() -> None:
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
    manifest_json, _ = b.manifest_and_stream()

    # --- assert ------------------------------
    manifest = json.loads(manifest_json)
    assert set(manifest) == {"payloads", "targets"}
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


def test_stream_concatenates_payloads_per_manifest_lengths() -> None:
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
    manifest_json, stream = b.manifest_and_stream()
    manifest = json.loads(manifest_json)

    offset = 0
    recovered: list[bytes] = []
    for entry in manifest["payloads"]:
        length = entry["length"]
        recovered.append(stream[offset : offset + length])
        offset += length

    # --- assert ------------------------------
    assert offset == len(stream), "manifest lengths must cover the whole stream"
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
def test_bundle_stats_counts_split_by_mode_and_mime() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>compressible html content</p>" * 30
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>' * 10
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))  # dedup

    # --- act --------------------------------
    stats = b.stats()

    # --- assert ------------------------------
    assert stats.text_payloads == 1
    assert stats.text_targets == 2  # two srcdoc refs sharing one payload
    assert stats.blob_payloads_by_mime == {"image/svg+xml": 1}
    assert stats.blob_targets_by_mime == {"image/svg+xml": 1}
    assert stats.total_payloads == 2
    assert stats.total_targets == 3


def test_bundle_stats_bytes_saved_property() -> None:
    # --- arrange ----------------------------
    stats = BundleStats(
        text_targets=1,
        text_payloads=1,
        blob_targets_by_mime={},
        blob_payloads_by_mime={},
        baseline_bytes=1000,
        compressed_bytes=600,
        compressed=True,
    )

    # --- act / assert ------------------------
    assert stats.bytes_saved == 400


def test_bundle_stats_bytes_saved_zero_when_not_compressed() -> None:
    # --- arrange ----------------------------
    stats = BundleStats(
        text_targets=1,
        text_payloads=1,
        blob_targets_by_mime={},
        blob_payloads_by_mime={},
        baseline_bytes=1000,
        compressed_bytes=0,
        compressed=False,
    )

    # --- act / assert ------------------------
    assert stats.bytes_saved == 0


def test_bundle_stats_baseline_sums_across_adds_including_duplicates() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>compressible content</p>" * 40
    # Three calls — baseline accumulates each, even though dedup keeps payloads at 1.
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))

    # --- act --------------------------------
    stats = b.stats()

    # --- assert ------------------------------
    assert stats.baseline_bytes == 3 * len(text)
    assert stats.total_payloads == 1
    assert stats.total_targets == 3


def test_bundle_stats_blob_breakdown_includes_every_mime() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>' * 5
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
    avif = b"\x00\x00\x00\x1cftypavif" + b"\x00" * 200
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=png, mode="blob", attr="src", mime="image/png", baseline_len=len(png))
    b.add(payload=avif, mode="blob", attr="src", mime="image/avif", baseline_len=len(avif))

    # --- act --------------------------------
    stats = b.stats()

    # --- assert ------------------------------
    assert stats.blob_payloads_by_mime == {
        "image/svg+xml": 1,
        "image/png": 1,
        "image/avif": 1,
    }
    assert stats.blob_targets_by_mime == {
        "image/svg+xml": 2,
        "image/png": 1,
        "image/avif": 1,
    }


# ==================================================================================================
#  stats() — read-only snapshot
# ==================================================================================================
def test_stats_on_empty_bundler() -> None:
    # --- arrange / act ----------------------
    stats = PayloadBundler().stats()

    # --- assert ------------------------------
    assert stats.compressed is False
    assert stats.compressed_bytes == 0
    assert stats.bytes_saved == 0
    assert stats.text_targets == 0
    assert stats.text_payloads == 0
    assert stats.blob_targets_by_mime == {}
    assert stats.blob_payloads_by_mime == {}
    assert stats.total_targets == 0
    assert stats.total_payloads == 0


def test_stats_never_marks_compressed() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    text = b"<p>some iframe html</p>" * 5
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))
    b.add(payload=svg, mode="blob", attr="src", mime="image/svg+xml", baseline_len=len(svg))

    # --- act --------------------------------
    stats = b.stats()

    # --- assert ------------------------------
    # stats() is a read-only snapshot; the shipped-page figures are
    # substituted later by the bootstrap builder when compression ships.
    assert stats.compressed is False
    assert stats.compressed_bytes == 0
    assert stats.text_payloads == 1
    assert stats.text_targets == 1
    assert stats.blob_payloads_by_mime == {"image/svg+xml": 1}
    assert stats.blob_targets_by_mime == {"image/svg+xml": 2}
    # Baseline still reflects every add() call (no dedup).
    assert stats.baseline_bytes == len(text) + 2 * len(svg)


# ==================================================================================================
#  manifest_and_stream() — stream ordering
# ==================================================================================================
def _add_blob(b: PayloadBundler, payload: bytes, mime: str) -> str:
    """Register a blob payload with a derived baseline; return the target id."""
    return b.add(payload=payload, mode="blob", attr="src", mime=mime, baseline_len=len(base64.b64encode(payload)))


def _recovered_payloads(manifest: dict, stream: bytes) -> list[bytes]:
    """Slice the stream back into per-payload bytes via the manifest lengths."""
    out: list[bytes] = []
    offset = 0
    for entry in manifest["payloads"]:
        out.append(stream[offset : offset + entry["length"]])
        offset += entry["length"]
    assert offset == len(stream)
    return out


def test_stream_orders_text_then_svg_then_bitmaps() -> None:
    # --- arrange ----------------------------
    # Registered in the reverse of the intended stream order.
    b = PayloadBundler()
    png = b"\x89PNG fake bitmap payload"
    svg = b"<svg>vector payload</svg>"
    text = b"<p>iframe html payload</p>"
    _add_blob(b, png, "image/png")
    _add_blob(b, svg, "image/svg+xml")
    b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))

    # --- act --------------------------------
    manifest_json, stream = b.manifest_and_stream()
    manifest = json.loads(manifest_json)

    # --- assert ------------------------------
    assert [p["mode"] for p in manifest["payloads"]] == ["text", "blob", "blob"]
    assert [p.get("mime") for p in manifest["payloads"]] == [None, "image/svg+xml", "image/png"]
    assert _recovered_payloads(manifest, stream) == [text, svg, png]


def test_stream_orders_bitmaps_by_mime_then_registration() -> None:
    # --- arrange ----------------------------
    b = PayloadBundler()
    webp_first = b"RIFF small"
    png_large = b"\x89PNG " + b"x" * 50
    png_small = b"\x89PNG tiny"
    _add_blob(b, webp_first, "image/webp")
    _add_blob(b, png_large, "image/png")
    _add_blob(b, png_small, "image/png")

    # --- act --------------------------------
    manifest_json, stream = b.manifest_and_stream()
    manifest = json.loads(manifest_json)

    # --- assert ------------------------------
    # png before webp (mime alphabetical); within png, registration order
    # is preserved — large-before-small as registered, never re-sorted by
    # size (registration order is the similarity proxy).
    assert _recovered_payloads(manifest, stream) == [png_large, png_small, webp_first]


def test_stream_order_within_mime_preserves_registration_order() -> None:
    # --- arrange ----------------------------
    # Same group and mime, different sizes — registration order must
    # decide, stably (filmstrip frames register in their natural
    # similarity order; reordering them hurts compression).
    b = PayloadBundler()
    first = b"<svg>aaaa frame one</svg>"
    second = b"<svg>b2</svg>"
    _add_blob(b, first, "image/svg+xml")
    _add_blob(b, second, "image/svg+xml")

    # --- act --------------------------------
    manifest_json, stream = b.manifest_and_stream()
    manifest = json.loads(manifest_json)

    # --- assert ------------------------------
    assert _recovered_payloads(manifest, stream) == [first, second]


def test_stream_reorder_remaps_target_indices() -> None:
    # --- arrange ----------------------------
    # Bitmap registered first lands last in the stream; every target must
    # still resolve to its own payload bytes through the manifest.
    b = PayloadBundler()
    png = b"\x89PNG fake bitmap payload"
    text = b"<p>iframe html payload</p>"
    png_target = _add_blob(b, png, "image/png")
    text_target = b.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    expected = {png_target: png, text_target: text}

    # --- act --------------------------------
    manifest_json, stream = b.manifest_and_stream()
    manifest = json.loads(manifest_json)
    recovered = _recovered_payloads(manifest, stream)
    resolved = {t["id"]: recovered[t["payload"]] for t in manifest["targets"]}

    # --- assert ------------------------------
    assert resolved == expected


def test_stream_order_is_deterministic_across_builds() -> None:
    # --- arrange ----------------------------
    def _build() -> tuple[str, bytes]:
        b = PayloadBundler()
        _add_blob(b, b"\x89PNG payload one", "image/png")
        b.add(payload=b"<p>html</p>", mode="text", attr="srcdoc", baseline_len=11)
        _add_blob(b, b"<svg>v</svg>", "image/svg+xml")
        return b.manifest_and_stream()

    # --- act / assert -----------------------
    assert _build() == _build()
