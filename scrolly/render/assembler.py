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
from scrolly._shared.mime import ext_for
from scrolly.deck import Deck
from scrolly.pipeline._bundler import BundleStats
from scrolly.pipeline._reencode import ReencodeStats
from scrolly.render.bundled_assets import MermaidAsset, bundled_css, bundled_js
from scrolly.render.nav_data import build_nav_data
from scrolly.render.zoom_control import MinimapGeometry, compute_minimap_geometry
from scrolly.slide import SlideHTML

# Sentinel extension for text-mode (iframe HTML) payloads. Image payloads
# get their extension label from `_shared.mime.ext_for`; the canvas.js
# `extLabels` map turns these keys into friendly display names ("SVG",
# "PNG", "HTML", etc.).
_TEXT_EXT = ".html"


def assemble(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    inline: bool = True,
    simplified_zoom_control: bool = False,
    payload_manifest_json: str | None = None,
    bundle_stats: BundleStats | None = None,
    mermaid: MermaidAsset | None = None,
    minify: bool = True,
    deferred_compression_stats: bool = False,
    reencode_stats: ReencodeStats | None = None,
) -> str:
    """Render the deck and its chunks into a single HTML string.

    Args:
        deck: The fully-resolved deck.
        chunks: Rendered per-slide HTML chunks, keyed by slide id.
        inline: Inline CSS/JS into the page (vs. emitting separate files).
        minify: Inline the canvas JS and CSS minified (comments
            stripped) rather than as readable source. Only meaningful
            when ``inline=True``.
        simplified_zoom_control: Use the legacy single-icon zoom-out
            control instead of the default deck mini-map.
        payload_manifest_json: Payload manifest from the bundler's
            ``manifest_and_stream()`` (payload schema + target
            bindings, no bytes), injected as a single ``<script>``
            block for canvas.js's target populator. ``None`` for plain
            builds, whose targets carry inline forms instead.
        bundle_stats: Bundler stats snapshot, used to populate the
            help-screen statistics. ``None`` when no bundler ran
            (``inline=False`` builds).
        mermaid: Resolved mermaid asset (content + version + source
            tier), or ``None`` when the deck has no mermaid elements.
            Inlined into the page when ``inline=True`` and present;
            its version always lands in the help-screen meta.
        deferred_compression_stats: ``True`` when assembling the inner
            document of a compressed build: the help-screen file-size
            and space-saved figures depend on the compressed page this
            document ends up inside, so both are emitted as
            placeholders for ``scrolly.render.bootstrap`` to resolve,
            and the payload stats report ``compressed: true``.
        reencode_stats: Bitmap re-encoding snapshot for the help-screen
            payload stats. ``None`` when no bundler ran (non-inline
            builds), matching ``bundle_stats``.

    Returns:
        The rendered HTML page as a single string.
    """
    template = _env().get_template("index.html.j2")
    nav_data = build_nav_data(deck, chunks)
    scoped_css_blocks = _collect_scoped_css(deck, chunks)
    has_mermaid = mermaid is not None
    minimap: MinimapGeometry | None = None if simplified_zoom_control else compute_minimap_geometry(deck)
    meta = _build_meta(
        deck,
        chunks,
        bundle_stats=bundle_stats,
        mermaid=mermaid,
        deferred_compression_stats=deferred_compression_stats,
        reencode_stats=reencode_stats,
    )

    inline_vars = {}
    if inline:
        inline_vars["bundled_css"] = bundled_css(minify=minify)
        inline_vars["bundled_js"] = bundled_js(minify=minify)
        if mermaid is not None:
            inline_vars["mermaid_js_content"] = mermaid.content.decode("utf-8")

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
        payload_manifest_json=payload_manifest_json,
        **inline_vars,
    )

    if deferred_compression_stats:
        # Both size placeholders stay in place for bootstrap resolution.
        return html

    meta["stats"]["file_size"] = len(html.encode("utf-8"))
    return html.replace('"__FILE_SIZE_PLACEHOLDER__"', str(meta["stats"]["file_size"]))


def _build_meta(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    bundle_stats: BundleStats | None = None,
    mermaid: MermaidAsset | None = None,
    deferred_compression_stats: bool = False,
    reencode_stats: ReencodeStats | None = None,
) -> dict[str, Any]:
    """Build the metadata dict injected into the HTML for the help screen.

    Args:
        deck: The fully-resolved deck.
        chunks: Rendered per-slide HTML chunks.
        bundle_stats: Bundler snapshot for the payload-stats section.
        mermaid: Resolved mermaid asset, whose version is surfaced in
            the help-screen statistics. ``None`` for decks without
            mermaid elements.
        deferred_compression_stats: Emit compressed-build placeholders
            (see :func:`assemble`).
        reencode_stats: Bitmap re-encoding snapshot for the payload-stats
            section. ``None`` when no bundler ran.

    Returns:
        Help-screen metadata dict.
    """
    return {
        "version": __version__,
        "author": "Bert Pluymers",
        "pypi_url": "https://pypi.org/project/scrolly/",
        "stats": {
            "slides": len(deck.slides),
            "edges": len(deck.edges),
            "payloads": _payload_stats(
                bundle_stats,
                deferred_compression_stats=deferred_compression_stats,
                reencode_stats=reencode_stats,
            ),
            "mermaid_version": mermaid.version if mermaid is not None else None,
            "file_size": "__FILE_SIZE_PLACEHOLDER__",
        },
    }


def _payload_stats(
    bundle_stats: BundleStats | None,
    *,
    deferred_compression_stats: bool = False,
    reencode_stats: ReencodeStats | None = None,
) -> dict[str, Any]:
    """Convert ``BundleStats`` into the help-screen-friendly schema.

    Returns a dict with five keys:

    - ``total``: per-extension counts of every payload binding (pre-dedup),
      e.g. ``{".svg": 5, ".html": 1, ".png": 1}``.
    - ``unique``: per-extension counts of unique payloads (post-dedup).
      Identical to ``total`` when no dedup happened.
    - ``compressed``: ``True`` only in the inner document of a
      compressed build (``deferred_compression_stats``).
    - ``bytes_saved``: ``0`` for plain builds; in the deferred case a
      placeholder string resolved by ``scrolly.render.bootstrap``.
    - ``reencoding``: the bitmap re-encoding block (``quality``,
      ``considered``, ``reencoded``, ``bytes_saved``), or ``None`` when no
      bundler ran. The JS shows the line only when ``considered`` > 0.

    Args:
        bundle_stats: Bundler snapshot, or ``None`` when no bundler ran
            (``inline=False`` builds).
        deferred_compression_stats: Emit compressed-build placeholders
            (see :func:`assemble`).
        reencode_stats: Bitmap re-encoding snapshot, ``None`` alongside a
            ``None`` ``bundle_stats``.

    Returns:
        Help-screen payload stats dict.
    """
    reencoding = reencode_stats.as_dict() if reencode_stats is not None else None
    if bundle_stats is None:
        return {"total": {}, "unique": {}, "compressed": False, "bytes_saved": 0, "reencoding": reencoding}

    total: dict[str, int] = {}
    if bundle_stats.text_targets > 0:
        total[_TEXT_EXT] = bundle_stats.text_targets
    for mime, count in bundle_stats.blob_targets_by_mime.items():
        ext = ext_for(mime) or mime
        total[ext] = total.get(ext, 0) + count

    unique: dict[str, int] = {}
    if bundle_stats.text_payloads > 0:
        unique[_TEXT_EXT] = bundle_stats.text_payloads
    for mime, count in bundle_stats.blob_payloads_by_mime.items():
        ext = ext_for(mime) or mime
        unique[ext] = unique.get(ext, 0) + count

    if deferred_compression_stats:
        return {
            "total": total,
            "unique": unique,
            "compressed": True,
            "bytes_saved": "__BYTES_SAVED_PLACEHOLDER__",
            "reencoding": reencoding,
        }
    return {
        "total": total,
        "unique": unique,
        "compressed": bundle_stats.compressed,
        "bytes_saved": bundle_stats.bytes_saved,
        "reencoding": reencoding,
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
    """Build the Jinja environment for the canvas templates (no autoescape, strict undefined)."""
    return Environment(
        loader=PackageLoader("scrolly.render", "templates"),
        autoescape=select_autoescape(default=False),
        undefined=StrictUndefined,
    )
