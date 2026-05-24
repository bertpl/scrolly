"""Fill in omitted edge sides by inferring from slide positions.

An endpoint with `side=None` has its side inferred from where the other
endpoint's slide sits relative to this one on the grid:

    dx > 0 → right    dx < 0 → left
    dy > 0 → bottom   dy < 0 → top

If the two slides are diagonal (dx ≠ 0 and dy ≠ 0), there is no unique
side and a `DeckInferenceError` is raised.
"""

from __future__ import annotations

from scrolly.deck.model import Deck, Edge, Endpoint, Position, RawDeck, Side
from scrolly.errors import DeckInferenceError


def infer_edges(deck: RawDeck) -> Deck:
    """Return a `Deck` with every edge's sides fully specified."""
    positions = {slide.id: slide.position for slide in deck.slides}
    inferred: list[Edge] = []

    for idx, edge in enumerate(deck.edges):
        a_pos = positions[edge.a.slide_id]
        b_pos = positions[edge.b.slide_id]

        a_side = edge.a.side or _infer_side(a_pos, b_pos, idx, edge.a.slide_id, edge.b.slide_id)
        b_side = edge.b.side or _infer_side(b_pos, a_pos, idx, edge.b.slide_id, edge.a.slide_id)

        inferred.append(
            Edge(
                a=Endpoint(slide_id=edge.a.slide_id, side=a_side),
                b=Endpoint(slide_id=edge.b.slide_id, side=b_side),
            )
        )

    return Deck(title=deck.title, slides=deck.slides, edges=tuple(inferred), groups=deck.groups)


def _infer_side(
    from_pos: Position,
    to_pos: Position,
    edge_idx: int,
    from_id: str,
    to_id: str,
) -> Side:
    """Return the side of `from_pos`'s slide that faces `to_pos`'s slide."""
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y

    if dx != 0 and dy == 0:
        return Side.RIGHT if dx > 0 else Side.LEFT
    if dy != 0 and dx == 0:
        return Side.BOTTOM if dy > 0 else Side.TOP

    # Diagonal or same cell — no unique side.
    raise DeckInferenceError(
        code="E503",
        message=(
            f"edges[{edge_idx}]: cannot infer side for '{from_id}' — "
            f"'{from_id}' and '{to_id}' are not on the same row or column"
        ),
    )
