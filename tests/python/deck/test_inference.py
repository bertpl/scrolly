from pathlib import Path

import pytest

from scrolly.deck.inference import infer_edges
from scrolly.deck.model import (
    Position,
    RawDeck,
    RawEdge,
    RawEndpoint,
    Side,
    Slide,
    SlideGroup,
)
from scrolly.errors import DeckInferenceError


def _slide(id_: str, x: int, y: int) -> Slide:
    return Slide(id=id_, position=Position(x, y), source=Path(f"/{id_}.slide.json"))


def test_horizontal_inference():
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.RIGHT
    assert deck.edges[0].b.side is Side.LEFT


def test_horizontal_inference_reverse_order():
    # a at (1, 0), b at (0, 0) — b is to the left of a.
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 1, 0), _slide("b", 0, 0)),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.LEFT
    assert deck.edges[0].b.side is Side.RIGHT


def test_vertical_inference():
    # a at (0, 0), b at (0, 1) — b is below a (y grows top → bottom).
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 0, 1)),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.BOTTOM
    assert deck.edges[0].b.side is Side.TOP


def test_inference_preserves_explicit_sides():
    # Explicit sides win even if they don't match the positional hint.
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(RawEdge(RawEndpoint("a", Side.TOP), RawEndpoint("b", Side.BOTTOM)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.TOP
    assert deck.edges[0].b.side is Side.BOTTOM


def test_inference_fills_only_the_missing_side():
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(RawEdge(RawEndpoint("a", Side.TOP), RawEndpoint("b", None)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.TOP
    assert deck.edges[0].b.side is Side.LEFT


def test_diagonal_placement_with_omitted_side_raises():
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 1)),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
    )
    with pytest.raises(DeckInferenceError, match="not on the same row or column"):
        infer_edges(raw)


def test_diagonal_placement_with_explicit_sides_is_ok():
    # Diagonal positions are fine when both sides are explicit.
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 1)),
        edges=(RawEdge(RawEndpoint("a", Side.RIGHT), RawEndpoint("b", Side.LEFT)),),
    )
    deck = infer_edges(raw)
    assert deck.edges[0].a.side is Side.RIGHT
    assert deck.edges[0].b.side is Side.LEFT


def test_groups_pass_through_inference():
    groups = (SlideGroup(label="G", slide_ids=("a",)),)
    raw = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
        groups=groups,
    )
    deck = infer_edges(raw)
    assert deck.groups == groups
