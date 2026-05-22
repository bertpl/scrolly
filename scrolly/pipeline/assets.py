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
from dataclasses import dataclass, replace
from pathlib import Path

from scrolly.errors import SlideSourceError
from scrolly.pipeline._compress import CompressionStats, try_compress
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


def rewrite_asset_refs(
    chunks: dict[str, SlideHTML],
    *,
    inline: bool = True,
    compress: bool = True,
) -> tuple[dict[str, SlideHTML], CompressionStats]:
    """Validate asset sources and rewrite ``__asset__/`` refs in chunks.

    When ``inline=True``, references are replaced with ``data:`` URIs
    (optionally compressed when ``compress=True``).
    When ``inline=False``, references are rewritten to ``_assets/<slide_id>/``.

    Args:
        chunks: Per-slide rendered HTML chunks, keyed by slide id.
        inline: Inline assets as data URIs (vs. separate files).
        compress: Enable gzip compression for inlined image assets.

    Returns:
        Tuple of (rewritten chunks dict, aggregate compression stats).
    """
    result: dict[str, SlideHTML] = {}
    total = CompressionStats()
    for slide_id, chunk in chunks.items():
        if not chunk.assets:
            result[slide_id] = chunk
            continue
        _validate_assets(slide_id, chunk.assets)
        if inline:
            rewritten, stats = _inline_refs(slide_id, chunk, compress=compress)
            result[slide_id] = rewritten
            total = total + stats
        else:
            result[slide_id] = _rewrite_refs(slide_id, chunk)
    return result, total


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


def _inline_refs(
    slide_id: str, chunk: SlideHTML, *, compress: bool = True,
) -> tuple[SlideHTML, CompressionStats]:
    """Inline asset references, optionally compressing image payloads.

    Args:
        slide_id: Owning slide id (for error messages).
        chunk: The rendered slide chunk.
        compress: Enable gzip compression for image payloads.

    Returns:
        Tuple of (rewritten chunk, compression stats for this chunk).
    """
    asset_info = _build_asset_info(slide_id, chunk.assets, compress=compress)
    html = chunk.html
    css = chunk.scoped_css
    stats = CompressionStats()

    for filename, info in asset_info.items():
        ref = f"{ASSET_REF_PREFIX}{filename}"
        css = css.replace(ref, info.data_uri)
        html, asset_stats = _apply_to_html(html, ref, info)
        stats = stats + asset_stats

    return replace(chunk, html=html, scoped_css=css), stats


def _apply_to_html(
    html: str, ref: str, info: _AssetInfo,
) -> tuple[str, CompressionStats]:
    """Substitute one asset reference in HTML.

    When ``info.packed`` is set, attempt to rewrite the ``<img>`` tag carrying
    ``src="<ref>"`` with the compressed-payload attributes. If no matching
    ``<img>`` is found (e.g. the asset is referenced only from CSS), fall back
    to the plain data URI substitution.

    Args:
        html: The HTML to substitute into.
        ref: The asset reference token to match.
        info: Per-asset inlining info.

    Returns:
        Tuple of (rewritten html, compression stats for this asset).
    """
    if info.packed is None:
        return html.replace(ref, info.data_uri), CompressionStats()

    pat = re.compile(
        r'(<img\b[^>]*?)\ssrc="' + re.escape(ref) + r'"([^>]*>)'
    )
    repl = (
        r'\1 data-scrolly-gz="' + info.packed + r'" '
        r'data-scrolly-sink="img" data-scrolly-mime="' + info.mime + r'"\2'
    )
    new_html = pat.sub(repl, html)
    if new_html != html:
        return new_html, CompressionStats(compressed=1, bytes_saved=info.bytes_saved)
    return html.replace(ref, info.data_uri), CompressionStats()


@dataclass(frozen=True)
class _AssetInfo:
    """Per-asset inlining info."""

    data_uri: str
    mime: str
    packed: str | None
    bytes_saved: int


def _build_asset_info(
    slide_id: str, assets: tuple[Path, ...], *, compress: bool,
) -> dict[str, _AssetInfo]:
    """Build per-asset inlining info including optional compression candidates.

    Args:
        slide_id: Owning slide id (for error messages).
        assets: Asset file paths.
        compress: Whether to compute compressed candidates.

    Returns:
        Dict mapping filename to its inlining info.
    """
    result: dict[str, _AssetInfo] = {}
    for path in assets:
        mime = _mime_type(path, slide_id)
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        data_uri = f"data:{mime};base64,{encoded}"
        packed: str | None = None
        bytes_saved = 0
        if compress:
            cresult = try_compress(raw, len(encoded))
            if cresult.packed is not None:
                packed = cresult.packed
                bytes_saved = cresult.bytes_saved
        result[path.name] = _AssetInfo(
            data_uri=data_uri, mime=mime, packed=packed, bytes_saved=bytes_saved,
        )
    return result


def _mime_type(path: Path, slide_id: str) -> str:
    ext = path.suffix.lower()
    if ext not in _MIME_TYPES:
        raise SlideSourceError(
            f"slide {slide_id!r}: unsupported image format '{ext}' for {path.name}. "
            f"Supported: {', '.join(sorted(_MIME_TYPES))}"
        )
    return _MIME_TYPES[ext]
