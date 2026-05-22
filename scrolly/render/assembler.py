"""Assemble the final HTML page from a Deck and its per-slide SlideHTMLs.

Emits every slide as a `slide-container` positioned by grid coordinates,
an SVG overlay of bezier curves for the declared edges, and embeds the
deck's navigation graph as a JSON blob the client-side JS consumes.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from scrolly import __version__
from scrolly.deck import Deck
from scrolly.pipeline._compress import CompressionStats
from scrolly.render.bundled_assets import bundled_css, bundled_js, mermaid_js
from scrolly.render.nav_data import build_nav_data
from scrolly.render.zoom_control import MinimapGeometry, compute_minimap_geometry
from scrolly.slide import SlideHTML


def assemble(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    inline: bool = True,
    simplified_zoom_control: bool = False,
    compression_stats: CompressionStats | None = None,
) -> str:
    """Render the deck and its chunks into a single HTML string.

    Args:
        deck: The fully-resolved deck.
        chunks: Rendered per-slide HTML chunks, keyed by slide id.
        inline: Inline CSS/JS into the page (vs. emitting separate files).
        simplified_zoom_control: Use the legacy single-icon zoom-out
            control instead of the default deck mini-map.
        compression_stats: Aggregate stats from inlined-asset compression.

    Returns:
        The rendered HTML page as a single string.
    """
    template = _env().get_template("index.html.j2")
    nav_data = build_nav_data(deck, chunks)
    scoped_css_blocks = _collect_scoped_css(deck, chunks)
    has_mermaid = any(chunk.has_mermaid for chunk in chunks.values())
    minimap: MinimapGeometry | None = None if simplified_zoom_control else compute_minimap_geometry(deck)
    meta = _build_meta(deck, chunks, compression_stats=compression_stats)

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
        **inline_vars,
    )

    meta["stats"]["file_size"] = len(html.encode("utf-8"))
    return html.replace('"__FILE_SIZE_PLACEHOLDER__"', str(meta["stats"]["file_size"]))


def _build_meta(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    compression_stats: CompressionStats | None = None,
) -> dict[str, Any]:
    """Build the metadata dict injected into the HTML for the help screen."""
    asset_counts: Counter[str] = Counter()
    for chunk in chunks.values():
        for path in chunk.assets:
            asset_counts[path.suffix.lower()] += 1

    cs = compression_stats or CompressionStats()
    return {
        "version": __version__,
        "author": "Bert Pluymers",
        "pypi_url": "https://pypi.org/project/scrolly/",
        "stats": {
            "slides": len(deck.slides),
            "edges": len(deck.edges),
            "assets": dict(asset_counts),
            "compressed": cs.compressed,
            "bytes_saved": cs.bytes_saved,
            "file_size": "__FILE_SIZE_PLACEHOLDER__",
        },
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
