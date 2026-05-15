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
import shutil
from dataclasses import replace
from pathlib import Path

from scrolly.errors import SlideSourceError
from scrolly.slide import SlideHTML

ASSET_REF_PREFIX = "__asset__/"

_MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


def rewrite_asset_refs(chunks: dict[str, SlideHTML], *, inline: bool = True) -> dict[str, SlideHTML]:
    """Validate asset sources and rewrite ``__asset__/`` refs in chunks.

    When ``inline=True``, references are replaced with ``data:`` URIs.
    When ``inline=False``, references are rewritten to ``_assets/<slide_id>/``.
    Returns a new dict with rewritten chunks (unchanged chunks are reused).
    """
    result: dict[str, SlideHTML] = {}
    for slide_id, chunk in chunks.items():
        if not chunk.assets:
            result[slide_id] = chunk
            continue
        _validate_assets(slide_id, chunk.assets)
        if inline:
            result[slide_id] = _inline_refs(slide_id, chunk)
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
    filenames: set[str] = set()
    for path in assets:
        if not path.exists():
            raise SlideSourceError(f"slide {slide_id!r}: asset file does not exist: {path}")
        name = path.name
        if not name or name in (".", ".."):
            raise SlideSourceError(f"slide {slide_id!r}: invalid asset filename: {name!r}")
        if name in filenames:
            raise SlideSourceError(f"slide {slide_id!r}: duplicate asset filename: {name!r}")
        filenames.add(name)


def _rewrite_refs(slide_id: str, chunk: SlideHTML) -> SlideHTML:
    target = f"_assets/{slide_id}/"
    return replace(
        chunk,
        html=chunk.html.replace(ASSET_REF_PREFIX, target),
        scoped_css=chunk.scoped_css.replace(ASSET_REF_PREFIX, target),
    )


def _inline_refs(slide_id: str, chunk: SlideHTML) -> SlideHTML:
    data_uris = _build_data_uris(slide_id, chunk.assets)
    html = chunk.html
    css = chunk.scoped_css
    for filename, data_uri in data_uris.items():
        ref = f"{ASSET_REF_PREFIX}{filename}"
        html = html.replace(ref, data_uri)
        css = css.replace(ref, data_uri)
    return replace(chunk, html=html, scoped_css=css)


def _build_data_uris(slide_id: str, assets: tuple[Path, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in assets:
        mime = _mime_type(path, slide_id)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        result[path.name] = f"data:{mime};base64,{encoded}"
    return result


def _mime_type(path: Path, slide_id: str) -> str:
    ext = path.suffix.lower()
    if ext not in _MIME_TYPES:
        raise SlideSourceError(
            f"slide {slide_id!r}: unsupported image format '{ext}' for {path.name}. "
            f"Supported: {', '.join(sorted(_MIME_TYPES))}"
        )
    return _MIME_TYPES[ext]
