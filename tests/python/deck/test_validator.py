from pathlib import Path

import pytest

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
    SlideGroup,
)
from scrolly.deck.validator import validate_deck, validate_raw_deck
from scrolly.errors import DeckValidationError


def _slide(id_: str, x: int, y: int) -> Slide:
    return Slide(id=id_, position=Position(x, y), source=Path(f"/{id_}.slide.json"))


def test_valid_empty_raw_deck():
    validate_raw_deck(RawDeck(title=None, slides=(), edges=()))


def test_valid_raw_deck_with_slides_and_edge():
    deck = RawDeck(
        title="x",
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(RawEdge(RawEndpoint("a", Side.RIGHT), RawEndpoint("b", Side.LEFT)),),
    )
    validate_raw_deck(deck)


def test_duplicate_slide_id_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("a", 1, 0)),
        edges=(),
    )
    with pytest.raises(DeckValidationError, match="duplicate slide id"):
        validate_raw_deck(deck)


def test_duplicate_cell_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 0, 0)),
        edges=(),
    )
    with pytest.raises(DeckValidationError, match="both occupy position"):
        validate_raw_deck(deck)


def test_edge_to_unknown_slide_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0),),
        edges=(RawEdge(RawEndpoint("a", None), RawEndpoint("ghost", None)),),
    )
    with pytest.raises(DeckValidationError, match="unknown slide 'ghost'"):
        validate_raw_deck(deck)


def test_validate_deck_accepts_single_edge():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    validate_deck(deck)


def test_duplicate_edge_with_swapped_endpoints_rejected():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
            Edge(Endpoint("b", Side.LEFT), Endpoint("a", Side.RIGHT)),
        ),
    )
    with pytest.raises(DeckValidationError, match="duplicate edge"):
        validate_deck(deck)


def test_identical_duplicate_edge_rejected():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
        ),
    )
    with pytest.raises(DeckValidationError, match="duplicate edge"):
        validate_deck(deck)


def test_edges_on_different_sides_not_duplicates():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
            Edge(Endpoint("a", Side.TOP), Endpoint("b", Side.BOTTOM)),
        ),
    )
    validate_deck(deck)


# ── Group validation ─────────────────────────────────────────────


def test_valid_groups():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0), _slide("c", 0, 1)),
        edges=(),
        groups=(SlideGroup(label="G1", slide_ids=("a", "b")),),
    )
    validate_raw_deck(deck)


def test_duplicate_group_label_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
        groups=(
            SlideGroup(label="Same", slide_ids=("a",)),
            SlideGroup(label="Same", slide_ids=("b",)),
        ),
    )
    with pytest.raises(DeckValidationError, match="duplicate group label"):
        validate_raw_deck(deck)


def test_group_references_unknown_slide_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0),),
        edges=(),
        groups=(SlideGroup(label="G", slide_ids=("a", "ghost")),),
    )
    with pytest.raises(DeckValidationError, match="unknown slide 'ghost'"):
        validate_raw_deck(deck)


def test_overlapping_group_membership_rejected():
    deck = RawDeck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
        groups=(
            SlideGroup(label="G1", slide_ids=("a", "b")),
            SlideGroup(label="G2", slide_ids=("b",)),
        ),
    )
    with pytest.raises(DeckValidationError, match="belongs to both"):
        validate_raw_deck(deck)
