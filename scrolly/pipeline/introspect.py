"""Build-time pipeline introspection — JSON-ready views of asset references.

The ``*_to_json`` helpers here power the ``scrolly introspect`` CLI
subcommands that surface pipeline-level state: the asset table today.
Each helper is pure (no I/O beyond ``Path.stat``), takes the resolved
``Deck`` + ``slide_irs`` map produced by ``load_deck`` and returns a
``dict`` that's safe to feed into ``json.dumps``.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from scrolly.deck.model import Deck
from scrolly.slide.ir import SlideIR
from scrolly.slide.ir._framework.element import (
    ImageElement,
    ImageSequenceElement,
    SlideElement,
)


def assets_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize per-asset metadata + per-slide references to a JSON-ready dict.

    Walks each slide's ``ImageElement`` and ``ImageSequenceElement``
    instances, collecting referenced asset paths. For each unique asset,
    reports its absolute path, file size in bytes (or ``null`` if missing),
    an ``exists`` flag, mime type guessed from the extension (or ``null``
    when unknown), and the list of slide ids that reference it.

    Note that asset existence/format isn't validated by ``load_deck`` —
    those checks run in ``build_deck``'s render pass — so introspect can
    legitimately encounter missing files; the output flags them rather
    than raising.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to scope to; ``None``
            (or empty) walks every slide.

    Returns:
        Dict ``{"assets": [{path, name, size_bytes, exists, mime,
        referenced_by}, ...]}`` sorted by ``path``.
    """
    target_ids = set(slide_ids) if slide_ids else None

    refs: dict[Path, list[str]] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]
        for el in ir.elements:
            for path in _asset_paths_in_element(el):
                refs.setdefault(path, [])
                if slide.id not in refs[path]:
                    refs[path].append(slide.id)

    assets_view = []
    for path in sorted(refs):
        exists = path.exists()
        size = path.stat().st_size if exists else None
        mime, _ = mimetypes.guess_type(str(path))
        assets_view.append(
            {
                "path": str(path),
                "name": path.name,
                "size_bytes": size,
                "exists": exists,
                "mime": mime,
                "referenced_by": refs[path],
            }
        )

    return {"assets": assets_view}


def _asset_paths_in_element(el: SlideElement) -> list[Path]:
    """Return the asset ``Path`` references inside an element, empty if none."""
    if isinstance(el, ImageElement):
        return [el.image]
    if isinstance(el, ImageSequenceElement):
        return [p for p in el.image_sequence if p is not None]
    return []
