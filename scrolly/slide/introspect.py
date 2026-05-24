"""Build-time slide introspection — JSON-ready views of resolved slide IRs.

The ``*_to_json`` helpers here power the ``scrolly introspect`` CLI
subcommands that surface slide-level state: the resolved element tree
today, scroll-driven views (snaps, visibility, snapshot) in later
versions. Each helper is pure (no I/O), takes the resolved ``Deck`` +
``slide_irs`` map produced by ``load_deck`` and returns a ``dict``
that's safe to feed into ``json.dumps``.
"""

from __future__ import annotations

from scrolly.deck.model import Deck
from scrolly.slide.ir import SlideIR


def element_tree_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize per-slide element trees to a JSON-ready dict.

    Each element is dumped via Pydantic's ``model_dump(mode="json")``
    then augmented with ``index`` and ``type`` fields. Animated values
    surface as their underlying root form — a static scalar, an
    ``[x, y]`` list, the literal string ``"auto"`` for size dims, or a
    ``{"keyframes": [...]}`` dict for animated values.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to include; ``None``
            (or empty) returns all slides.

    Returns:
        Dict ``{"slides": {<id>: {title, scroll_range, elements: [...]}}}``.
    """
    target_ids = set(slide_ids) if slide_ids else None

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]
        elements_view = []
        for index, el in enumerate(ir.elements):
            element_dict = el.model_dump(mode="json")
            element_dict["index"] = index
            element_dict["type"] = type(el).__name__
            elements_view.append(element_dict)
        slides_view[slide.id] = {
            "title": ir.title,
            "scroll_range": ir.scroll_range,
            "elements": elements_view,
        }

    return {"slides": slides_view}
