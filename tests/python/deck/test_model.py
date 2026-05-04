from pathlib import Path

from scrolly.deck.model import (
    Deck,
    Edge,
    Endpoint,
    Position,
    RawDeck,
    RawEdge,
    RawEndpoint,
    Side,
    Slide,
)


def test_side_values():
    assert Side.TOP.value == "top"
    assert Side.BOTTOM.value == "bottom"
    assert Side.LEFT.value == "left"
    assert Side.RIGHT.value == "right"


def test_position_is_hashable_and_equal_by_value():
    assert Position(1, 2) == Position(1, 2)
    assert hash(Position(1, 2)) == hash(Position(1, 2))
    assert Position(1, 2) != Position(2, 1)


def test_slide_construction():
    s = Slide(id="x", position=Position(0, 0), source=Path("/tmp/x.static.md"))
    assert s.id == "x"
    assert s.position == Position(0, 0)
    assert s.source == Path("/tmp/x.static.md")


def test_raw_endpoint_allows_none_side():
    e = RawEndpoint(slide_id="x", side=None)
    assert e.side is None


def test_endpoint_requires_defined_side():
    e = Endpoint(slide_id="x", side=Side.TOP)
    assert e.side is Side.TOP


def test_raw_and_cooked_are_distinct_types():
    raw = RawDeck(
        title=None,
        slides=(),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("b", None)),),
    )
    cooked = Deck(
        title=None,
        slides=(),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    assert type(raw) is not type(cooked)
    assert raw.edges[0].a.side is None
    assert cooked.edges[0].a.side is Side.RIGHT
