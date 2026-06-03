"""Build the navigation data structure the browser-side JS consumes.

The canvas.js script reads this blob at startup to resolve arrow-key presses
into target slides, to position edge arrows in the navigation layer, and
to compute bezier paths at runtime. Edges are undirected, so each declared
edge contributes one entry per endpoint in the per-slide-per-side structure
and one entry in the flat `edges` array.

Per-edge fan composition (`fan_index`, `fan_size`) is computed by
`scrolly.render.fan` and emitted here so canvas.js can derive each arrow's
and bezier endpoint's offset via `CanvasGeometry.fanOffset()`, applying a
min-spacing floor on small viewports. The fan-spacing fraction (0.1 of side
length) travels as a top-level field so canvas.js doesn't duplicate the
constant.

Per-slide titles come from each slide's rendered `SlideHTML`, so the runtime
can show titles (e.g. on edge-arrow hover pills) without reaching back
into source files.
"""

from __future__ import annotations

from typing import Any

from scrolly.deck import Deck
from scrolly.render.color import legible_text_color
from scrolly.render.fan import FAN_SPACING_FACTOR, compute_fan_lookup
from scrolly.slide import SlideHTML

# Default group-background fill, used when a group sets no explicit `color`.
# Mirrors `.slide-group-bg { fill }` in canvas.css so the label auto-contrast
# pick matches the rendered background.
DEFAULT_GROUP_BACKGROUND = "#dcdcdc"


def build_nav_data(deck: Deck, chunks: dict[str, SlideHTML]) -> dict[str, Any]:
    """Return a JSON-serializable representation of the deck for the client.

    Shape::

        {
          "initial_slide": "<id>" | None,
          "fan_spacing_factor": <float>,
          "slides": {
            "<slide_id>": {
              "title": "<human-readable label>",
              "position": [x, y],
              "scroll_range": null | <int>,
              "scroll_speed": <float>,
              "initial_scroll_position": <int>,
              "reverse": <bool>,
              "edges": {
                "left":   [{"target": "<id>", "fan_index": <int>,
                            "fan_size": <int>}, ...],
                "right":  [...],
                "top":    [...],
                "bottom": [...],
              }
            },
            ...
          }
        }

    Each side's array is ordered along the side's axis. `fan_index` and
    `fan_size` describe each entry's position within its fan; canvas.js
    uses these plus the top-level `fan_spacing_factor` to compute each
    arrow's and bezier endpoint's offset via `CanvasGeometry.fanOffset()`,
    applying a min-spacing floor so adjacent arrows stay at least one
    arrow-size apart on small viewports.
    `scroll_range = null` signals content-driven mode (canvas.js attaches
    a `ResizeObserver` and recomputes from content overflow); an int signals
    fixed-timeline mode (scroll position is a logical input to per-element
    keyframe animations).
    """
    slides_data: dict[str, dict[str, Any]] = {
        slide.id: {
            "title": chunks[slide.id].title,
            "position": [slide.position.x, slide.position.y],
            "scroll_range": chunks[slide.id].scroll_range,
            "scroll_speed": chunks[slide.id].scroll_speed,
            "initial_scroll_position": chunks[slide.id].initial_scroll_position,
            "snap_positions": list(chunks[slide.id].snap_positions),
            "reverse": chunks[slide.id].reverse,
            "edges": {},
        }
        for slide in deck.slides
    }

    fan = compute_fan_lookup(deck)
    for (slide_id, side), entries in fan.items():
        slides_data[slide_id]["edges"][side.value] = [
            {
                "target": e.target_id,
                "fan_index": e.fan_index,
                "fan_size": e.fan_size,
            }
            for e in entries
        ]

    edges_data = _build_edges(deck, fan)

    groups_data = []
    for g in deck.groups:
        entry: dict[str, Any] = {"label": g.label, "slide_ids": list(g.slide_ids)}
        if g.color:
            entry["color"] = g.color
        # Resolve the label color here so the client just applies it: an explicit
        # `label_color` override wins, else auto-contrast against the background.
        entry["label_color"] = g.label_color or legible_text_color(g.color or DEFAULT_GROUP_BACKGROUND)
        groups_data.append(entry)

    return {
        "initial_slide": deck.slides[0].id if deck.slides else None,
        "fan_spacing_factor": FAN_SPACING_FACTOR,
        "slides": slides_data,
        "edges": edges_data,
        "groups": groups_data,
    }


def _build_edges(deck: Deck, fan: dict[tuple[str, "Side"], tuple["FanEntry", ...]]) -> list[dict[str, Any]]:
    """Build a flat edge list with fan composition per endpoint."""
    fan_lookup: dict[tuple[str, str, str], tuple[int, int]] = {}
    for (slide_id, side), entries in fan.items():
        for entry in entries:
            fan_lookup[(slide_id, side.value, entry.target_id)] = (
                entry.fan_index,
                entry.fan_size,
            )

    edges: list[dict[str, Any]] = []
    for edge in deck.edges:
        a_fan = fan_lookup.get((edge.a.slide_id, edge.a.side.value, edge.b.slide_id), (0, 1))
        b_fan = fan_lookup.get((edge.b.slide_id, edge.b.side.value, edge.a.slide_id), (0, 1))
        edges.append(
            {
                "a_slide": edge.a.slide_id,
                "a_side": edge.a.side.value,
                "a_fan_index": a_fan[0],
                "a_fan_size": a_fan[1],
                "b_slide": edge.b.slide_id,
                "b_side": edge.b.side.value,
                "b_fan_index": b_fan[0],
                "b_fan_size": b_fan[1],
            }
        )
    return edges
