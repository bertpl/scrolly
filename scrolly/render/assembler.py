"""Assemble the final HTML page from a Deck and its per-slide SlideHTMLs.

Emits every slide as a `slide-container` positioned by grid coordinates,
an SVG overlay of bezier curves for the declared edges, and embeds the
deck's navigation graph as a JSON blob the client-side JS consumes.
"""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from scrolly import __version__
from scrolly.deck import Deck
from scrolly.pipeline._bundler import BundleStats
from scrolly.render.bundled_assets import bundled_css, bundled_js, mermaid_js
from scrolly.render.nav_data import build_nav_data
from scrolly.render.zoom_control import MinimapGeometry, compute_minimap_geometry
from scrolly.slide import SlideHTML

# Reverse of `_MIME_TYPES` in `scrolly/pipeline/assets.py`, plus a sentinel
# for text-mode payloads. Used for help-screen labelling — the canvas.js
# `extLabels` map maps these extension keys to friendly display names
# ("SVG", "PNG", "HTML", etc.).
_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}
_TEXT_EXT = ".html"


def assemble(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    inline: bool = True,
    simplified_zoom_control: bool = False,
    compressed_payload_json: str | None = None,
    bundle_stats: BundleStats | None = None,
) -> str:
    """Render the deck and its chunks into a single HTML string.

    Args:
        deck: The fully-resolved deck.
        chunks: Rendered per-slide HTML chunks, keyed by slide id.
        inline: Inline CSS/JS into the page (vs. emitting separate files).
        simplified_zoom_control: Use the legacy single-icon zoom-out
            control instead of the default deck mini-map.
        compressed_payload_json: JSON payload from the bundler's
            ``build()`` (manifest + base64 blob), to be injected as a
            single ``<script>`` block. ``None`` when the gate failed or
            no compressible payloads were registered.
        bundle_stats: Stats from the bundler's ``build()``, used to
            populate the help-screen statistics. ``None`` when no bundle
            was emitted.

    Returns:
        The rendered HTML page as a single string.
    """
    template = _env().get_template("index.html.j2")
    nav_data = build_nav_data(deck, chunks)
    scoped_css_blocks = _collect_scoped_css(deck, chunks)
    has_mermaid = any(chunk.has_mermaid for chunk in chunks.values())
    minimap: MinimapGeometry | None = None if simplified_zoom_control else compute_minimap_geometry(deck)
    meta = _build_meta(deck, chunks, bundle_stats=bundle_stats)

    inline_vars = {}
    if inline:
        inline_vars["bundled_css"] = bundled_css()
        inline_vars["bundled_js"] = bundled_js()
        if has_mermaid:
            inline_vars["mermaid_js_content"] = mermaid_js()

    html = template.render(
        title=deck.title or "scrolly",
        slides=deck.slides,
        chunks=chunks,
        nav_data_json=json.dumps(nav_data),
        meta_json=json.dumps(meta),
        scoped_css_blocks=scoped_css_blocks,
        has_mermaid=has_mermaid,
        inline=inline,
        minimap=minimap,
        compressed_payload_json=compressed_payload_json,
        **inline_vars,
    )

    meta["stats"]["file_size"] = len(html.encode("utf-8"))
    return html.replace('"__FILE_SIZE_PLACEHOLDER__"', str(meta["stats"]["file_size"]))


def _build_meta(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    bundle_stats: BundleStats | None = None,
) -> dict[str, Any]:
    """Build the metadata dict injected into the HTML for the help screen."""
    return {
        "version": __version__,
        "author": "Bert Pluymers",
        "pypi_url": "https://pypi.org/project/scrolly/",
        "stats": {
            "slides": len(deck.slides),
            "edges": len(deck.edges),
            "payloads": _payload_stats(bundle_stats),
            "file_size": "__FILE_SIZE_PLACEHOLDER__",
        },
    }


def _payload_stats(bundle_stats: BundleStats | None) -> dict[str, Any]:
    """Convert ``BundleStats`` into the help-screen-friendly shape.

    Returns a dict with four keys:

    - ``total``: per-extension counts of every payload binding (pre-dedup),
      e.g. ``{".svg": 5, ".html": 1, ".png": 1}``.
    - ``unique``: per-extension counts of unique payloads (post-dedup).
      Identical to ``total`` when no dedup happened.
    - ``compressed``: ``True`` only when a bundle was emitted into the
      page; ``False`` when bundling was skipped or the gate failed.
    - ``bytes_saved``: ``0`` when ``compressed`` is ``False``.

    Args:
        bundle_stats: Bundler snapshot, or ``None`` when no bundler ran
            (``inline=False`` builds).

    Returns:
        Help-screen payload stats dict.
    """
    if bundle_stats is None:
        return {"total": {}, "unique": {}, "compressed": False, "bytes_saved": 0}

    total: dict[str, int] = {}
    if bundle_stats.text_targets > 0:
        total[_TEXT_EXT] = bundle_stats.text_targets
    for mime, count in bundle_stats.blob_targets_by_mime.items():
        ext = _MIME_TO_EXT.get(mime, mime)
        total[ext] = total.get(ext, 0) + count

    unique: dict[str, int] = {}
    if bundle_stats.text_payloads > 0:
        unique[_TEXT_EXT] = bundle_stats.text_payloads
    for mime, count in bundle_stats.blob_payloads_by_mime.items():
        ext = _MIME_TO_EXT.get(mime, mime)
        unique[ext] = unique.get(ext, 0) + count

    return {
        "total": total,
        "unique": unique,
        "compressed": bundle_stats.compressed,
        "bytes_saved": bundle_stats.bytes_saved,
    }


def _collect_scoped_css(deck: Deck, chunks: dict[str, SlideHTML]) -> list[str]:
    """Return the deck's unique non-empty scoped_css blocks in stable order.

    Order is first-occurrence in deck.slides, so identical scoped_css across
    multiple chunks (e.g. all static slides sharing one block) emits once
    and the surviving copy comes from the deck's first slide that carries
    it. Stable across builds for the same deck.
    """
    blocks: list[str] = []
    seen: set[str] = set()
    for slide in deck.slides:
        scoped = chunks[slide.id].scoped_css
        if scoped and scoped not in seen:
            blocks.append(scoped)
            seen.add(scoped)
    return blocks


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("scrolly.render", "templates"),
        autoescape=select_autoescape(default=False),
        undefined=StrictUndefined,
    )
