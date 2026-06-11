"""Deliver chunk-declared assets to the build output directory.

Type-agnostic: any slide type whose renderer populates ``SlideHTML.assets``
and references them via the ``__asset__/`` prefix in ``html`` or
``scoped_css`` gets its assets copied and references rewritten here.

The delivery is split into two phases so the orchestrator can sequence
them around the output-directory setup:

1. ``rewrite_asset_refs`` — validate sources + rewrite ``__asset__/``
   prefixes in chunk html/scoped_css. Pure data; no filesystem writes
   beyond existence checks.
2. ``copy_assets`` — copy the actual files into the output directory.
   Called after the output directory has been created by ``write_output``.
"""

from __future__ import annotations

import base64
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from scrolly._shared.mime import mime_for, supported_extensions
from scrolly.errors import SlideSourceError
from scrolly.slide import SlideHTML

if TYPE_CHECKING:
    from scrolly.pipeline._bundler import PayloadBundler
    from scrolly.pipeline._reencode import BitmapReencoder

ASSET_REF_PREFIX = "__asset__/"


def rewrite_asset_refs(
    chunks: dict[str, SlideHTML],
    *,
    inline: bool = True,
    bundler: PayloadBundler | None = None,
    reencoder: BitmapReencoder | None = None,
) -> dict[str, SlideHTML]:
    """Validate asset sources and rewrite ``__asset__/`` refs in chunks.

    When ``inline=True`` and ``bundler`` is provided, every
    ``<img>``-referenced asset is registered with the bundler and the
    ``<img>`` tag's ``src="__asset__/<n>"`` is rewritten to a
    ``data-scrolly-target="<id>"`` marker (the JS populates ``src``
    after decompressing the bundle). CSS ``url(__asset__/<n>)``
    references stay as plain ``data:`` URIs (no JS hook for them).

    When ``inline=True`` and ``bundler`` is ``None``, both HTML and CSS
    references become plain ``data:`` URIs (no compression).

    When ``inline=False``, all references are rewritten to
    ``_assets/<slide_id>/`` paths and the bundler is unused.

    Args:
        chunks: Per-slide rendered HTML chunks, keyed by slide id.
        inline: Inline assets as data URIs (vs. separate files).
        bundler: Optional payload bundler for ``<img>`` references.
        reencoder: Optional bitmap re-encoder. When provided (inline
            builds only), each raster asset's bytes/mime pass through it
            before inlining, so a format flip propagates to the data URI,
            the bundler payload, and the help-screen mime labels.

    Returns:
        Rewritten chunks dict.
    """
    result: dict[str, SlideHTML] = {}
    for slide_id, chunk in chunks.items():
        if not chunk.assets:
            result[slide_id] = chunk
            continue
        _validate_assets(slide_id, chunk.assets)
        if inline:
            result[slide_id] = _inline_refs(slide_id, chunk, bundler=bundler, reencoder=reencoder)
        else:
            result[slide_id] = _rewrite_refs(slide_id, chunk)
    return result


def copy_assets(chunks: dict[str, SlideHTML], output_dir: Path) -> None:
    """Copy declared asset files into ``output_dir/_assets/<slide_id>/``."""
    for slide_id, chunk in chunks.items():
        if not chunk.assets:
            continue
        dest_dir = output_dir / "_assets" / slide_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        for path in chunk.assets:
            shutil.copy2(path, dest_dir / path.name)


def _validate_assets(slide_id: str, assets: tuple[Path, ...]) -> None:
    """Check that every declared asset exists and has a unique, non-trivial filename."""
    filenames: set[str] = set()
    for path in assets:
        if not path.exists():
            raise SlideSourceError(code="E401", message=f"slide {slide_id!r}: asset file does not exist: {path}")
        name = path.name
        if not name or name in (".", ".."):
            raise SlideSourceError(code="E402", message=f"slide {slide_id!r}: invalid asset filename: {name!r}")
        if name in filenames:
            raise SlideSourceError(code="E402", message=f"slide {slide_id!r}: duplicate asset filename: {name!r}")
        filenames.add(name)


def _rewrite_refs(slide_id: str, chunk: SlideHTML) -> SlideHTML:
    """Rewrite ``__asset__/`` refs to ``_assets/<slide_id>/`` paths (the non-inline path)."""
    target = f"_assets/{slide_id}/"
    return replace(
        chunk,
        html=chunk.html.replace(ASSET_REF_PREFIX, target),
        scoped_css=chunk.scoped_css.replace(ASSET_REF_PREFIX, target),
    )


def _inline_refs(
    slide_id: str,
    chunk: SlideHTML,
    *,
    bundler: PayloadBundler | None,
    reencoder: BitmapReencoder | None,
) -> SlideHTML:
    """Inline asset references; register ``<img>``-referenced ones with the bundler.

    Args:
        slide_id: Owning slide id (for error messages).
        chunk: The rendered slide chunk.
        bundler: Optional payload bundler. When provided, ``<img>``
            references go to the bundler as ``mode="blob"`` payloads.
        reencoder: Optional bitmap re-encoder applied to each asset's
            bytes/mime before inlining (a no-op for ineligible assets).

    Returns:
        Rewritten chunk with ``__asset__/`` references resolved.
    """
    html = chunk.html
    css = chunk.scoped_css

    for path in chunk.assets:
        mime = _mime_type(path, slide_id)
        raw = path.read_bytes()
        if reencoder is not None:
            raw, mime = reencoder.process(raw, mime)
        encoded = base64.b64encode(raw).decode("ascii")
        data_uri = f"data:{mime};base64,{encoded}"
        ref = f"{ASSET_REF_PREFIX}{path.name}"

        # CSS ``url(__asset__/<n>)`` references always become plain ``data:`` URIs
        # — no JS hook to substitute against.
        css = css.replace(ref, data_uri)

        if bundler is not None:
            html = _bundle_img_refs(html, ref, bundler, raw=raw, mime=mime, baseline_len=len(encoded))

        # Any HTML reference that wasn't an ``<img src="…">`` (or any reference at
        # all when the bundler isn't in use) falls through to a plain ``data:`` URI.
        html = html.replace(ref, data_uri)

    return replace(chunk, html=html, scoped_css=css)


def _bundle_img_refs(
    html: str,
    ref: str,
    bundler: PayloadBundler,
    *,
    raw: bytes,
    mime: str,
    baseline_len: int,
) -> str:
    """Replace ``<img src="<ref>">`` tags with ``data-scrolly-target`` markers.

    Each matching ``<img>`` registers its own target binding with the
    bundler (which dedups identical payloads). Other attributes on the
    tag are preserved verbatim.

    Args:
        html: The HTML to scan.
        ref: The ``__asset__/<n>`` token to match.
        bundler: The payload bundler to register with.
        raw: Raw asset bytes.
        mime: Asset mime type (for the Blob constructor on the JS side).
        baseline_len: Length of the plain ``base64`` form (the inline
            baseline this binding would have produced).

    Returns:
        HTML with each matching ``<img>`` tag's ``src="<ref>"`` replaced
        by ``data-scrolly-target="<id>"``. Tags referencing other assets
        are untouched.
    """
    pat = re.compile(r'(<img\b[^>]*?)\ssrc="' + re.escape(ref) + r'"([^>]*>)')

    def _swap(match: re.Match[str]) -> str:
        target_id = bundler.add(
            payload=raw,
            mode="blob",
            attr="src",
            mime=mime,
            baseline_len=baseline_len,
        )
        return f'{match.group(1)} data-scrolly-target="{target_id}"{match.group(2)}'

    return pat.sub(_swap, html)


def _mime_type(path: Path, slide_id: str) -> str:
    """Return the MIME type for a supported image extension, raising ``E403`` otherwise."""
    mime = mime_for(path)
    if mime is None:
        raise SlideSourceError(
            code="E403",
            message=(
                f"slide {slide_id!r}: unsupported image format '{path.suffix.lower()}' for {path.name}. "
                f"Supported: {', '.join(supported_extensions())}"
            ),
        )
    return mime
