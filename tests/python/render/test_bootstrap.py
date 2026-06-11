"""Tests for scrolly.render.bootstrap — the compressed bootstrap page builder."""

from __future__ import annotations

import base64
import gzip
import re

from scrolly.render.bootstrap import build_compressed_page

_INNER = (
    "<!DOCTYPE html><html><head><title>t</title></head><body>"
    '<script id="scrolly-meta">{"stats": {"file_size": "__FILE_SIZE_PLACEHOLDER__", '
    '"payloads": {"bytes_saved": "__BYTES_SAVED_PLACEHOLDER__"}}}</script>'
    "<p>inner body</p></body></html>"
)


def _build(inner: str = _INNER, assets: bytes = b"", **overrides) -> str:
    """Build a compressed page with small defaults."""
    kwargs = {"title": "My Deck", "slide_count": 3, "plain_size": 100_000, "minify": True}
    kwargs.update(overrides)
    return build_compressed_page(inner, assets, **kwargs)


def _inflate(page: str) -> tuple[str, bytes]:
    """Pull the blob out of a bootstrap page and split it at doc-length."""
    match = re.search(r'id="scrolly-document" data-doc-length="(\d+)">([^<]*)</script>', page)
    assert match is not None
    doc_length = int(match.group(1))
    buf = gzip.decompress(base64.b64decode(match.group(2)))
    return buf[:doc_length].decode("utf-8"), buf[doc_length:]


def test_blob_roundtrips_document_and_assets() -> None:
    # --- arrange ----------------------
    assets = b"\x89PNG-ish raw bytes\x00\x01" * 10

    # --- act --------------------------
    page = _build(assets=assets)
    doc, payload_bytes = _inflate(page)

    # --- assert -----------------------
    assert "<p>inner body</p>" in doc
    assert payload_bytes == assets


def test_placeholders_resolved_inside_blob() -> None:
    # --- act --------------------------
    page = _build()
    doc, _ = _inflate(page)

    # --- assert -----------------------
    assert "__FILE_SIZE_PLACEHOLDER__" not in doc
    assert "__BYTES_SAVED_PLACEHOLDER__" not in doc
    file_size = int(re.search(r'"file_size": (\d+)', doc).group(1))
    bytes_saved = int(re.search(r'"bytes_saved": (\d+)', doc).group(1))
    # file_size approximates the page size (measured one pass earlier);
    # bytes_saved is plain_size minus that figure.
    assert abs(file_size - len(page.encode("utf-8"))) < 100
    assert bytes_saved == 100_000 - file_size


def test_bootstrap_carries_title_and_og_tags() -> None:
    # --- act --------------------------
    page = _build()

    # --- assert -----------------------
    assert "<title>My Deck</title>" in page
    assert '<meta property="og:title" content="My Deck">' in page
    assert '<meta property="og:description" content="Interactive presentation — 3 slides.">' in page


def test_bootstrap_escapes_title() -> None:
    # --- act --------------------------
    page = _build(title='Deck <name> & "quotes"')

    # --- assert -----------------------
    assert "<title>Deck &lt;name&gt; &amp; &quot;quotes&quot;</title>" in page
    assert "<name>" not in page


def test_bootstrap_has_black_screen_noscript_and_loader() -> None:
    # --- act --------------------------
    page = _build()

    # --- assert -----------------------
    assert "background: #000" in page
    assert "<noscript>" in page
    assert "DecompressionStream" in page
    assert "document.write" in page


def test_minified_loader_has_no_comments() -> None:
    # --- act --------------------------
    minified = _build(minify=True)
    readable = _build(minify=False)

    # --- assert -----------------------
    assert "/*" not in minified
    assert "/*" in readable
    assert len(minified) < len(readable)


def test_negative_savings_clamp_to_zero() -> None:
    # --- arrange / act ----------------
    # A plain size smaller than the compressed page (degenerate input).
    page = _build(plain_size=1)
    doc, _ = _inflate(page)

    # --- assert -----------------------
    assert int(re.search(r'"bytes_saved": (\d+)', doc).group(1)) == 0
