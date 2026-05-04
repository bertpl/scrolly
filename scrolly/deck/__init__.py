"""Deck model, parsing, validation, and inference (Layer A).

Pipeline:
    raw_deck = parse_deck(path)
    validate_raw_deck(raw_deck)
    deck = infer_edges(raw_deck)
    validate_deck(deck)
"""

from scrolly.deck.inference import infer_edges
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
from scrolly.deck.parser import parse_deck
from scrolly.deck.schema import deck_source_schema
from scrolly.deck.validator import validate_deck, validate_raw_deck

__all__ = [
    "Deck",
    "Edge",
    "Endpoint",
    "SlideGroup",
    "Position",
    "RawDeck",
    "RawEdge",
    "RawEndpoint",
    "Side",
    "Slide",
    "deck_source_schema",
    "infer_edges",
    "parse_deck",
    "validate_deck",
    "validate_raw_deck",
]
