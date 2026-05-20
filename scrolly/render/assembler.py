"""Assemble the final HTML page from a Deck and its per-slide SlideHTMLs.

Emits every slide as a `slide-container` positioned by grid coordinates,
an SVG overlay of bezier curves for the declared edges, and embeds the
deck's navigation graph as a JSON blob the client-side JS consumes.
"""

from __future__ import annotations

import json

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from scrolly.deck import Deck
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
) -> str:
    """Render the deck and its chunks into a single HTML string.

    Args:
        deck: The fully-resolved deck.
        chunks: Rendered per-slide HTML chunks, keyed by slide id.
        inline: Inline CSS/JS into the page (vs. emitting separate files).
        simplified_zoom_control: Use the legacy single-icon zoom-out
            control instead of the default deck mini-map.

    Returns:
        The rendered HTML page as a single string.
    """
    template = _env().get_template("index.html.j2")
    nav_data = build_nav_data(deck, chunks)
    scoped_css_blocks = _collect_scoped_css(deck, chunks)
    has_mermaid = any(chunk.has_mermaid for chunk in chunks.values())
    minimap: MinimapGeometry | None = None if simplified_zoom_control else compute_minimap_geometry(deck)

    inline_vars = {}
    if inline:
        inline_vars["bundled_css"] = bundled_css()
        inline_vars["bundled_js"] = bundled_js()
        if has_mermaid:
            inline_vars["mermaid_js_content"] = mermaid_js()

    return template.render(
        title=deck.title or "scrolly",
        slides=deck.slides,
        chunks=chunks,
        nav_data_json=json.dumps(nav_data),
        scoped_css_blocks=scoped_css_blocks,
        has_mermaid=has_mermaid,
        inline=inline,
        minimap=minimap,
        **inline_vars,
    )


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
