"""Structural validation for `RawDeck` and `Deck`.

`validate_raw_deck` checks invariants computable pre-inference (unique ids,
edges reference declared slides, one-slide-per-cell).
`validate_deck` checks invariants that need fully-specified edges (no
duplicate edges).
"""

from __future__ import annotations

from scrolly.deck.model import Deck, Position, RawDeck
from scrolly.errors import DeckValidationError


def validate_raw_deck(deck: RawDeck) -> None:
    _check_unique_slide_ids(deck)
    _check_edges_reference_declared_slides(deck)
    _check_one_slide_per_cell(deck)
    _check_unique_group_labels(deck)
    _check_group_slides_exist(deck)
    _check_no_overlapping_group_membership(deck)


def validate_deck(deck: Deck) -> None:
    _check_no_duplicate_edges(deck)


def _check_unique_slide_ids(deck: RawDeck) -> None:
    seen: set[str] = set()
    for slide in deck.slides:
        if slide.id in seen:
            raise DeckValidationError(f"duplicate slide id: '{slide.id}'")
        seen.add(slide.id)


def _check_edges_reference_declared_slides(deck: RawDeck) -> None:
    known = {s.id for s in deck.slides}
    for idx, edge in enumerate(deck.edges):
        if edge.a.slide_id not in known:
            raise DeckValidationError(f"edges[{idx}]: endpoint references unknown slide '{edge.a.slide_id}'")
        if edge.b.slide_id not in known:
            raise DeckValidationError(f"edges[{idx}]: endpoint references unknown slide '{edge.b.slide_id}'")


def _check_one_slide_per_cell(deck: RawDeck) -> None:
    cells: dict[Position, str] = {}
    for slide in deck.slides:
        if slide.position in cells:
            other = cells[slide.position]
            raise DeckValidationError(
                f"slides '{other}' and '{slide.id}' both occupy position ({slide.position.x}, {slide.position.y})"
            )
        cells[slide.position] = slide.id


def _check_unique_group_labels(deck: RawDeck) -> None:
    seen: set[str] = set()
    for group in deck.groups:
        if group.label in seen:
            raise DeckValidationError(f"duplicate group label: '{group.label}'")
        seen.add(group.label)


def _check_group_slides_exist(deck: RawDeck) -> None:
    known = {s.id for s in deck.slides}
    for group in deck.groups:
        for slide_id in group.slide_ids:
            if slide_id not in known:
                raise DeckValidationError(f"group '{group.label}': references unknown slide '{slide_id}'")


def _check_no_overlapping_group_membership(deck: RawDeck) -> None:
    seen: dict[str, str] = {}
    for group in deck.groups:
        for slide_id in group.slide_ids:
            if slide_id in seen:
                raise DeckValidationError(
                    f"slide '{slide_id}' belongs to both group '{seen[slide_id]}' and group '{group.label}'"
                )
            seen[slide_id] = group.label


def _check_no_duplicate_edges(deck: Deck) -> None:
    seen: set[frozenset] = set()
    for idx, edge in enumerate(deck.edges):
        key = frozenset(
            [
                (edge.a.slide_id, edge.a.side),
                (edge.b.slide_id, edge.b.side),
            ]
        )
        if key in seen:
            raise DeckValidationError(f"edges[{idx}]: duplicate edge")
        seen.add(key)
