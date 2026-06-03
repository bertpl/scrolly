"""Per-edge fan composition.

When a slide has two or more edges attached on the same side, each edge gets
a distinct fan position along that side. This module is the single source of
truth for fan composition (which edges fan together, in what order, with
what index and size), consumed by `nav_data.py` which emits `fan_index` and
`fan_size` per edge. At runtime, `CanvasGeometry.fanOffset()` in `canvas.js`
uses these plus `FAN_SPACING_FACTOR` to compute each arrow's and bezier
endpoint's offset, applying a min-spacing floor on small viewports.

Targets are ordered along the side by their spatial position on the side's
axis (target `y` for left/right sides, target `x` for top/bottom sides) so
arrows line up with the rough direction of their targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from scrolly.deck.model import Deck, Side

# Fan spacing along the side, expressed as a fraction of the side's length.
# Adjacent arrows in a fan are this far apart (center-to-center) along the
# viewport side. `0.1` gives a tight "just-spread" look — adjacent arrows
# clearly distinct but not splayed across the side.
# Exported (and emitted via nav_data) so `canvas.js` can use this single
# source of truth at runtime when computing the effective fan-spacing
# floor for small viewports.
FAN_SPACING_FACTOR = 0.1


@dataclass(frozen=True)
class FanEntry:
    """One edge fanned out at a slide-side.

    `fan_index` is this entry's 0-based position along its fan;
    `fan_size` is the count of entries in the fan. Default values
    (`0` and `1`) describe the single-edge case. At runtime,
    `CanvasGeometry.fanOffset()` derives the actual offset from these
    values plus the viewport-side length and `FAN_SPACING_FACTOR`.
    """

    target_id: str
    fan_index: int = 0
    fan_size: int = 1


FanLookup = Mapping[tuple[str, Side], tuple[FanEntry, ...]]


def compute_fan_offsets(deck: Deck) -> FanLookup:
    """Return a `(slide_id, side) -> tuple[FanEntry, ...]` lookup.

    A side with no edges has no entry in the lookup. A side with one edge
    has a single `FanEntry` at offset `0.5`. A side with `n >= 2` edges has
    `n` entries spread evenly inside a centered band, ordered along the
    side's axis (see module docstring).
    """
    positions = {s.id: s.position for s in deck.slides}

    # Bucket per (slide_id, side): the *raw* list of (target_id, edge_index)
    # pairs. The edge_index is a stable tiebreaker for repeated targets that
    # would otherwise collapse to the same sort key.
    buckets: dict[tuple[str, Side], list[str]] = {}
    for edge in deck.edges:
        buckets.setdefault((edge.a.slide_id, edge.a.side), []).append(edge.b.slide_id)
        buckets.setdefault((edge.b.slide_id, edge.b.side), []).append(edge.a.slide_id)

    lookup: dict[tuple[str, Side], tuple[FanEntry, ...]] = {}
    for (slide_id, side), targets in buckets.items():
        ordered = sorted(targets, key=_sort_key_for(side, positions))
        lookup[(slide_id, side)] = _entries_for(ordered)
    return lookup


def _sort_key_for(side: Side, positions):
    """Return a sort-key callable for a given side.

    LEFT/RIGHT sides sort by target.y first (smaller y = upper = smaller
    offset); TOP/BOTTOM sides sort by target.x first. Secondary coord and
    target_id are stable tiebreakers.
    """
    if side in (Side.LEFT, Side.RIGHT):

        def key(target_id: str) -> tuple[int, int, str]:
            p = positions[target_id]
            return (p.y, p.x, target_id)
    else:

        def key(target_id: str) -> tuple[int, int, str]:
            p = positions[target_id]
            return (p.x, p.y, target_id)

    return key


def _entries_for(ordered_targets: list[str]) -> tuple[FanEntry, ...]:
    n = len(ordered_targets)
    if n == 1:
        return (FanEntry(target_id=ordered_targets[0], fan_index=0, fan_size=1),)
    return tuple(
        FanEntry(
            target_id=tid,
            fan_index=i,
            fan_size=n,
        )
        for i, tid in enumerate(ordered_targets)
    )
