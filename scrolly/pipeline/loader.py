"""Read a deck from disk and resolve it into a render-ready in-memory form.

Pipeline:
    raw_deck = parse_deck(path)
    validate_raw_deck(raw_deck)
    deck = infer_edges(raw_deck)
    validate_deck(deck)
    slide_irs[id] = SlideIR.from_file(slide.source)   # per slide

The first four steps are the deck-level chain documented in
``scrolly.deck``; the fifth resolves each declared slide source to a
loaded ``SlideIR``. Validation is implicit: any malformed deck or slide
source raises before the chain completes.
"""

from __future__ import annotations

from pathlib import Path

from scrolly.deck import (
    Deck,
    infer_edges,
    parse_deck,
    validate_deck,
    validate_raw_deck,
)
from scrolly.slide.ir import SlideIR
from scrolly.slide.registry import get_ir_class_for_path


def load_deck(deck_path: Path) -> tuple[Deck, dict[str, SlideIR]]:
    """Parse, validate, and resolve a deck, returning it with its loaded slide IRs.

    Runs the full deck-loading chain: parse → validate raw → infer edges
    → validate → load each slide IR. The IRs are returned alongside the
    deck so callers (notably ``build_deck``) don't re-load them
    downstream. Validation is implicit in the load: any malformed or
    missing source raises before this function returns.

    Args:
        deck_path: Path to the ``.deck.json`` file.

    Returns:
        A tuple ``(deck, slide_irs)`` where ``deck`` is the fully-resolved
        :class:`Deck` and ``slide_irs`` maps slide id to the loaded
        :class:`SlideIR` instance.

    Raises:
        ScrollyError: For any parse, validation, or slide-source failure.
    """
    raw_deck = parse_deck(deck_path)
    validate_raw_deck(raw_deck)
    deck = infer_edges(raw_deck)
    validate_deck(deck)

    slide_irs: dict[str, SlideIR] = {}
    for slide in deck.slides:
        ir_cls = get_ir_class_for_path(slide.source)
        slide_irs[slide.id] = ir_cls.from_file(slide.source)

    return deck, slide_irs
