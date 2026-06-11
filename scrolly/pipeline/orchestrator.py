"""End-to-end deck build: load → render → assemble → write."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from scrolly.deck import Deck, Slide
from scrolly.errors import SlideSourceError
from scrolly.pipeline._bundler import PayloadBundler, gate_passes
from scrolly.pipeline._reencode import BitmapReencoder, ReencodeStats
from scrolly.pipeline.assets import copy_assets, rewrite_asset_refs
from scrolly.pipeline.loader import load_deck
from scrolly.pipeline.writer import write_output
from scrolly.render.assembler import assemble
from scrolly.render.bootstrap import build_compressed_page
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
    minify: bool = True,
    reencode_quality: int | None = 95,
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
        compress: Ship the compressed page (a small bootstrap loader
            plus one gzip+base64 blob holding the whole document and
            its asset payloads) when the ≥5% savings gate passes vs.
            the plain page.
        offline: Skip the mermaid CDN download and use the
            wheel-bundled mermaid instead. Honored together with the
            ``SCROLLY_OFFLINE`` environment variable.
        out_file: Name of the output HTML file inside ``out_dir``.
        minify: Ship the canvas JS and CSS minified (comments
            stripped). On by default in every mode, including
            ``compress=False``; disabled only via the hidden
            ``--no-minification`` debug flag.
        reencode_quality: Bitmap re-encoding quality (``None`` disables
            it). Honored only on inline builds — the re-encoder runs
            inside ``_inline_refs``, so a non-inline build never
            re-encodes regardless of this value.

    Returns:
        The fully-resolved ``Deck``.
    """
    deck, slide_irs = load_deck(deck_path)

    # Bundler is the canonical "compressible payload tracker" whenever
    # we're emitting an inlined build. It's instantiated regardless of the
    # `compress` flag so its stats (counts, dedup info) are always
    # available for the help screen. Whether the compressed page actually
    # ships is a separate decision: only when `compress=True` and the
    # holistic ≥5% gate passes vs. the plain page.
    bundler: PayloadBundler | None = PayloadBundler() if inline else None

    # The re-encoder shares the bundler's "inline builds only" lifetime: it
    # exists whenever assets are inlined, even when re-encoding is off, so it
    # can still count eligible bitmaps for the help-screen display rule.
    reencoder: BitmapReencoder | None = BitmapReencoder(reencode_quality) if inline else None

    chunks = _render_slides(deck.slides, slide_irs, bundler=bundler)
    chunks = rewrite_asset_refs(chunks, inline=inline, bundler=bundler, reencoder=reencoder)
    reencode_stats: ReencodeStats | None = reencoder.stats() if reencoder is not None else None

    # Resolve mermaid once when any chunk needs it — threaded into both
    # assemble (for inlined content + help-screen version) and write_output
    # (for the standalone-file emission under `inline=False`).
    mermaid: MermaidAsset | None = None
    if any(chunk.has_mermaid for chunk in chunks.values()):
        mermaid = mermaid_asset(offline=offline)

    if bundler is None:
        html = assemble(
            deck,
            chunks,
            inline=False,
            simplified_zoom_control=simplified_zoom_control,
            mermaid=mermaid,
            minify=minify,
        )
    else:
        html = _assemble_inlined(
            deck,
            chunks,
            bundler=bundler,
            compress=compress,
            simplified_zoom_control=simplified_zoom_control,
            mermaid=mermaid,
            minify=minify,
            reencode_stats=reencode_stats,
        )

    write_output(out_dir, html, force=force, mermaid=mermaid, inline=inline, out_file=out_file, minify=minify)
    if not inline:
        copy_assets(chunks, out_dir)

    return deck


def _assemble_inlined(
    deck: Deck,
    chunks: dict[str, SlideHTML],
    *,
    bundler: PayloadBundler,
    compress: bool,
    simplified_zoom_control: bool,
    mermaid: MermaidAsset | None,
    minify: bool,
    reencode_stats: ReencodeStats | None,
) -> str:
    """Assemble an inlined build: the compressed page, or the plain page.

    The plain page (bundler targets substituted back to inline forms) is
    always assembled — it is the shipped output for ``compress=False``
    and the gate baseline otherwise. When compression is requested, the
    inner document (targets as markers + payload manifest block) is
    wrapped into the bootstrap page and shipped iff it beats the plain
    page by the holistic ≥5% gate; a gate failure ships the plain page,
    byte-equivalent to a ``--no-compress`` build.
    """
    fallback = bundler.inline_fallback()
    plain_chunks = _substitute_fallback(chunks, fallback) if fallback else chunks
    plain_html = assemble(
        deck,
        plain_chunks,
        inline=True,
        simplified_zoom_control=simplified_zoom_control,
        bundle_stats=bundler.stats(),
        mermaid=mermaid,
        minify=minify,
        reencode_stats=reencode_stats,
    )
    if not compress:
        return plain_html

    manifest_json, asset_stream = bundler.manifest_and_stream()
    inner_html = assemble(
        deck,
        chunks,
        inline=True,
        simplified_zoom_control=simplified_zoom_control,
        payload_manifest_json=manifest_json,
        bundle_stats=bundler.stats(),
        mermaid=mermaid,
        minify=minify,
        deferred_compression_stats=True,
        reencode_stats=reencode_stats,
    )
    plain_size = len(plain_html.encode("utf-8"))
    compressed_html = build_compressed_page(
        inner_html,
        asset_stream,
        title=deck.title or "scrolly",
        slide_count=len(deck.slides),
        plain_size=plain_size,
        minify=minify,
    )
    if gate_passes(len(compressed_html.encode("utf-8")), plain_size):
        return compressed_html
    return plain_html


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
