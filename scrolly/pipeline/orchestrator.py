"""End-to-end deck build: load → render → assemble → write."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from scrolly.deck import Deck, Slide
from scrolly.errors import SlideSourceError
from scrolly.pipeline._bundler import BundleStats, PayloadBundler
from scrolly.pipeline.assets import copy_assets, rewrite_asset_refs
from scrolly.pipeline.loader import load_deck
from scrolly.pipeline.writer import write_output
from scrolly.render.assembler import assemble
from scrolly.render.bundled_assets import MermaidAsset, mermaid_asset
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.registry import find_renderer


def build_deck(
    deck_path: Path,
    out_dir: Path,
    *,
    force: bool = False,
    inline: bool = True,
    simplified_zoom_control: bool = False,
    compress: bool = True,
    offline: bool = False,
    out_file: str = "index.html",
) -> Deck:
    """Build a deck from `deck_path` into `out_dir`. Returns the fully-resolved `Deck`.

    Args:
        deck_path: Path to the ``.deck.json`` source.
        out_dir: Destination directory for the output HTML (and bundled
            assets when ``inline=False``).
        force: Allow overwriting a non-empty ``out_dir``.
        inline: Inline CSS/JS/mermaid into the output HTML (default)
            vs. emit separate files.
        simplified_zoom_control: Use the legacy single-icon zoom-out
            control instead of the default deck mini-map.
        compress: Emit the combined-payload gzip+base64 bundle when the
            ≥5% savings gate passes.
        offline: Skip the mermaid CDN download and use the
            wheel-bundled mermaid instead. Honored together with the
            ``SCROLLY_OFFLINE`` environment variable.
        out_file: Name of the output HTML file inside ``out_dir``.

    Returns:
        The fully-resolved ``Deck``.
    """
    deck, slide_irs = load_deck(deck_path)

    # Bundler is the canonical "compressible payload tracker" whenever
    # we're emitting an inlined build. It's instantiated regardless of the
    # `compress` flag so its stats (counts, baseline bytes, dedup info)
    # are always available for the help screen. Whether we actually emit
    # the bundle `<script>` block is a separate decision: only when
    # `compress=True` and the gate passes.
    bundler: PayloadBundler | None = PayloadBundler() if inline else None

    chunks = _render_slides(deck.slides, slide_irs, bundler=bundler)
    chunks = rewrite_asset_refs(chunks, inline=inline, bundler=bundler)

    compressed_payload_json: str | None = None
    bundle_stats: BundleStats | None = None
    if bundler is not None:
        if compress:
            result = bundler.build()
            if result is not None:
                compressed_payload_json, bundle_stats = result
        if compressed_payload_json is None:
            # Either compression disabled, or the gate failed. Snapshot stats
            # (with `compressed=False`) and substitute the inline fallback so
            # chunk HTML matches a `--no-compress` build byte-for-byte.
            bundle_stats = bundler.stats()
            fallback = bundler.inline_fallback()
            if fallback:
                chunks = _substitute_fallback(chunks, fallback)

    # Resolve mermaid once when any chunk needs it — threaded into both
    # assemble (for inlined content + help-screen version) and write_output
    # (for the standalone-file emission under `inline=False`).
    mermaid: MermaidAsset | None = None
    if any(chunk.has_mermaid for chunk in chunks.values()):
        mermaid = mermaid_asset(offline=offline)

    html = assemble(
        deck,
        chunks,
        inline=inline,
        simplified_zoom_control=simplified_zoom_control,
        compressed_payload_json=compressed_payload_json,
        bundle_stats=bundle_stats,
        mermaid=mermaid,
    )

    write_output(out_dir, html, force=force, mermaid=mermaid, inline=inline, out_file=out_file)
    if not inline:
        copy_assets(chunks, out_dir)

    return deck


def _render_slides(
    slides: tuple[Slide, ...],
    slide_irs: dict[str, SlideIR],
    *,
    bundler: PayloadBundler | None = None,
) -> dict[str, SlideHTML]:
    """Render each slide's pre-loaded IR into a ``SlideHTML``, keyed by slide id.

    Renderer dispatch is via ``find_renderer`` against the IR instance —
    a one-entry match against the single registered slide type.
    """
    chunks: dict[str, SlideHTML] = {}
    for slide in slides:
        ir = slide_irs[slide.id]
        renderer = find_renderer(ir)
        if renderer is None:
            raise SlideSourceError(
                code="E603",
                message=f"no renderer for {type(ir).__name__} (slide '{slide.id}')",
            )
        chunks[slide.id] = renderer.render(ir, css_namespace=slide.id, bundler=bundler)

    return chunks


def _substitute_fallback(
    chunks: dict[str, SlideHTML],
    fallback: dict[str, str],
) -> dict[str, SlideHTML]:
    """Replace every ``data-scrolly-target="<id>"`` marker with its inline form.

    Used when the bundler's gate fails: each registered target is rewritten
    back to the equivalent inline attribute fragment (``srcdoc="…"`` for
    text payloads, ``src="data:…"`` for blob payloads), so the rendered
    HTML is byte-equivalent to a ``--no-compress`` build.

    Args:
        chunks: Per-slide rendered chunks containing ``data-scrolly-target``
            markers.
        fallback: Map from target id to its inline attribute fragment
            (as returned by :meth:`PayloadBundler.inline_fallback`).

    Returns:
        Rewritten chunks dict.
    """
    result: dict[str, SlideHTML] = {}
    for slide_id, chunk in chunks.items():
        html = chunk.html
        for target_id, attr_fragment in fallback.items():
            html = html.replace(f'data-scrolly-target="{target_id}"', attr_fragment)
        result[slide_id] = replace(chunk, html=html)
    return result
