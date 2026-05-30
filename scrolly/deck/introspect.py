"""Build-time deck introspection — JSON-ready views of resolved deck topology.

The ``*_to_json`` helpers here power the ``scrolly introspect`` CLI
subcommands that surface deck-level state: slide list, edges, groups,
grid geometry. Each helper is pure (no I/O), takes the resolved
``Deck`` + ``slide_irs`` map produced by ``load_deck`` and returns a
``dict`` that's safe to feed into ``json.dumps``.
"""

from __future__ import annotations

from scrolly.deck.model import Deck
from scrolly.slide.ir import SlideIR


def slides_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize deck topology — slides, edges, groups — to a JSON-ready dict.

    The ``slide_ids`` parameter is accepted for signature uniformity with
    the other introspect helpers but ignored: the topology view is
    inherently deck-wide (the relationships between slides are its whole
    point).

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Ignored; topology view is deck-wide.

    Returns:
        Dict with three top-level sections:
            ``slides``: map of slide id → {position, title, scroll_range,
                element_count, snap_position_count}.
            ``edges``: list of {a: {slide, side}, b: {slide, side}}.
            ``groups``: list of {label, color, label_color, slide_ids}.
    """
    del slide_ids  # always deck-wide; param exists for signature uniformity

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        ir = slide_irs[slide.id]
        slides_view[slide.id] = {
            "id": slide.id,
            "position": [slide.position.x, slide.position.y],
            "title": ir.title,
            "scroll_range": ir.scroll_range,
            "element_count": len(ir.elements),
            "snap_position_count": len(ir.snap_positions),
        }

    edges_view = [
        {
            "a": {"slide": edge.a.slide_id, "side": edge.a.side.value},
            "b": {"slide": edge.b.slide_id, "side": edge.b.side.value},
        }
        for edge in deck.edges
    ]

    groups_view = [
        {
            "label": group.label,
            "color": group.color,
            "label_color": group.label_color,
            "slide_ids": list(group.slide_ids),
        }
        for group in deck.groups
    ]

    return {
        "slides": slides_view,
        "edges": edges_view,
        "groups": groups_view,
    }
