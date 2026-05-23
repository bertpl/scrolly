"""End-to-end deck build: parse → validate → infer → render → assemble → write."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from scrolly.deck import (
    Deck,
    Slide,
    infer_edges,
    parse_deck,
    validate_deck,
    validate_raw_deck,
)
from scrolly.errors import SlideSourceError
from scrolly.pipeline._bundler import BundleStats, PayloadBundler
from scrolly.pipeline.assets import copy_assets, rewrite_asset_refs
from scrolly.pipeline.writer import write_output
from scrolly.render.assembler import assemble
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.registry import find_compiler, find_renderer, get_ir_class_for_path


def validate_deck_sources(deck_path: Path) -> Deck:
    """Validate a deck and all its slide sources without rendering or writing."""
    raw_deck = parse_deck(deck_path)
    validate_raw_deck(raw_deck)
    deck = infer_edges(raw_deck)
    validate_deck(deck)

    for slide in deck.slides:
        ir_cls = get_ir_class_for_path(slide.source)
        ir_cls.from_file(slide.source)

    return deck


def build_deck(
    deck_path: Path,
    out_dir: Path,
    *,
    force: bool = False,
    inline: bool = True,
    simplified_zoom_control: bool = False,
    compress: bool = True,
) -> Deck:
    """Build a deck from `deck_path` into `out_dir`. Returns the fully-resolved `Deck`."""
    raw_deck = parse_deck(deck_path)
    validate_raw_deck(raw_deck)
    deck = infer_edges(raw_deck)
    validate_deck(deck)

    # Bundler is used only when both compression and inlining are requested.
    # In every other case (`--no-compress`, separate-files build), payloads
    # flow through their original inline / asset-file paths unchanged.
    bundler: PayloadBundler | None = PayloadBundler() if (compress and inline) else None

    chunks = _render_slides(deck.slides, bundler=bundler)
    chunks = rewrite_asset_refs(chunks, inline=inline, bundler=bundler)

    compressed_payload_json: str | None = None
    bundle_stats: BundleStats | None = None
    if bundler is not None:
        result = bundler.build()
        if result is not None:
            compressed_payload_json, bundle_stats = result
        else:
            # Gate failed (or no payloads registered). Substitute the inline
            # fallback back into each chunk so the output is byte-equivalent
            # to a `--no-compress` build for the same deck.
            fallback = bundler.inline_fallback()
            if fallback:
                chunks = _substitute_fallback(chunks, fallback)

    html = assemble(
        deck,
        chunks,
        inline=inline,
        simplified_zoom_control=simplified_zoom_control,
        compressed_payload_json=compressed_payload_json,
        bundle_stats=bundle_stats,
    )
    has_mermaid = any(chunk.has_mermaid for chunk in chunks.values())

    write_output(out_dir, html, force=force, has_mermaid=has_mermaid, inline=inline)
    if not inline:
        copy_assets(chunks, out_dir)

    return deck


def _render_slides(
    slides: tuple[Slide, ...],
    *,
    bundler: PayloadBundler | None = None,
) -> dict[str, SlideHTML]:
    """Render every slide's source into a ``SlideHTML``, keyed by slide id.

    Dispatches via ``can_process``: parse the source into an IR, then
    check renderers (first match renders to SlideHTML) or compilers (first
    match compiles to a new IR, repeat).  Cycle detection via visited
    IR classes.
    """
    chunks: dict[str, SlideHTML] = {}
    for slide in slides:
        ir_cls = get_ir_class_for_path(slide.source)
        ir = ir_cls.from_file(slide.source)

        visited: set[type[SlideIR]] = set()
        while True:
            renderer = find_renderer(ir)
            if renderer is not None:
                chunks[slide.id] = renderer.render(ir, css_namespace=slide.id, bundler=bundler)
                break

            compiler = find_compiler(ir)
            if compiler is None:
                raise SlideSourceError(f"no renderer or compiler for {type(ir).__name__} (slide '{slide.id}')")

            ir = compiler.compile(ir)
            ir_cls = type(ir)
            if ir_cls in visited:
                raise SlideSourceError(
                    f"conversion cycle detected for slide '{slide.id}': "
                    f"IR type {ir_cls.__name__} produced more than once"
                )
            visited.add(ir_cls)

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
