"""Tests for `scrolly.render.zoom_control.compute_minimap_geometry`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.deck.model import Deck, Position, Slide
from scrolly.render.zoom_control import (
    CELL_PX_DEFAULT,
    MARGIN_PX_DEFAULT,
    MAX_SIZE_PX,
    MIN_SIZE_PX,
    compute_minimap_geometry,
)


# ==================================================================================================
#  Helpers
# ==================================================================================================
def _slide(id_: str, x: int, y: int) -> Slide:
    """Build a Slide at (x, y) with a dummy static-markdown source path."""
    return Slide(id=id_, position=Position(x, y), source=Path(f"/{id_}.slide.json"))


def _deck(*slides: Slide) -> Deck:
    """Build a Deck with no edges or groups around the given slides."""
    return Deck(title=None, slides=tuple(slides), edges=())


# ==================================================================================================
#  Tests
# ==================================================================================================
def test_empty_deck_returns_minimum_container_and_no_cells() -> None:
    # --- act --------------------------
    geo = compute_minimap_geometry(_deck())

    # --- assert -----------------------
    assert geo.container_size == MIN_SIZE_PX
    assert geo.cell_size == CELL_PX_DEFAULT
    assert geo.margin_size == MARGIN_PX_DEFAULT
    assert geo.cells == ()


def test_small_deck_fits_inside_minimum_container_with_grid_centred() -> None:
    # --- arrange ----------------------
    deck = _deck(_slide("a", 0, 0), _slide("b", 1, 0))

    # --- act --------------------------
    geo = compute_minimap_geometry(deck)

    # --- assert -----------------------
    # Natural grid (margin around AND between) is 2*8 + 3*4 = 28px wide,
    # 1*8 + 2*4 = 16px tall — both under MIN.
    assert geo.container_size == MIN_SIZE_PX
    assert geo.cell_size == CELL_PX_DEFAULT
    assert geo.margin_size == MARGIN_PX_DEFAULT
    # Grid (including the 4px around-margins) centered: x offset
    # = (40 - 28) / 2 = 6, plus 4px around-margin = 10. y offset
    # = (40 - 16) / 2 = 12, plus 4px around-margin = 16.
    assert [(c.slide_id, c.x, c.y) for c in geo.cells] == [
        ("a", 10.0, 16.0),
        ("b", 22.0, 16.0),
    ]


def test_medium_deck_grows_container_to_natural_size_under_cap() -> None:
    # --- arrange ----------------------
    # 4x4 deck → 4*8 + 5*4 = 52px natural (margin around + between),
    # between MIN (40) and MAX (64).
    deck = _deck(*(_slide(f"s{x}-{y}", x, y) for x in range(4) for y in range(4)))

    # --- act --------------------------
    geo = compute_minimap_geometry(deck)

    # --- assert -----------------------
    assert geo.container_size == 52.0
    assert geo.cell_size == CELL_PX_DEFAULT
    assert geo.margin_size == MARGIN_PX_DEFAULT


def test_large_deck_pins_container_at_cap_and_shrinks_cells_with_between_margins() -> None:
    # --- arrange ----------------------
    # 8x8 deck → 8 + 8*8 + 7*4 = 100px natural, exceeds MAX (64).
    deck = _deck(*(_slide(f"s{x}-{y}", x, y) for x in range(8) for y in range(8)))

    # --- act --------------------------
    geo = compute_minimap_geometry(deck)

    # --- assert -----------------------
    assert geo.container_size == MAX_SIZE_PX
    # Around-margin stays at 4 (unscaled — consistent edge breathing room).
    # Cells and between-margins shrink together preserving the 2:1 ratio:
    # scale = (64 - 8) / (8*8 + 7*4) = 56 / 92 ≈ 0.6087.
    scale = (MAX_SIZE_PX - 2 * MARGIN_PX_DEFAULT) / (8 * CELL_PX_DEFAULT + 7 * MARGIN_PX_DEFAULT)
    assert geo.cell_size == pytest.approx(CELL_PX_DEFAULT * scale)
    assert geo.margin_size == pytest.approx(MARGIN_PX_DEFAULT * scale)
    # Resulting grid fills the container exactly along the dominant axis,
    # including the constant 4px around-margin on both sides.
    grid_w = 2 * MARGIN_PX_DEFAULT + 8 * geo.cell_size + 7 * geo.margin_size
    assert grid_w == pytest.approx(MAX_SIZE_PX)


def test_off_origin_deck_lays_out_identically_to_at_origin_same_shape() -> None:
    # --- arrange ----------------------
    at_origin = _deck(_slide("a", 0, 0), _slide("b", 1, 0))
    shifted = _deck(_slide("a", 3, 2), _slide("b", 4, 2))

    # --- act --------------------------
    geo_origin = compute_minimap_geometry(at_origin)
    geo_shifted = compute_minimap_geometry(shifted)

    # --- assert -----------------------
    assert geo_shifted.container_size == geo_origin.container_size
    assert geo_shifted.cell_size == geo_origin.cell_size
    assert geo_shifted.margin_size == geo_origin.margin_size
    # Cells share the same in-container positions; only slide_ids differ
    # if the slide order differs (it doesn't here).
    assert [(c.x, c.y) for c in geo_shifted.cells] == [(c.x, c.y) for c in geo_origin.cells]


def test_sparse_deck_only_emits_cells_for_occupied_positions() -> None:
    # --- arrange ----------------------
    # 3-wide bounding box but only 2 slides — the middle column is empty.
    deck = _deck(_slide("a", 0, 0), _slide("c", 2, 0))

    # --- act --------------------------
    geo = compute_minimap_geometry(deck)

    # --- assert -----------------------
    assert len(geo.cells) == 2
    assert {c.slide_id for c in geo.cells} == {"a", "c"}
    # The two cells sit at columns 0 and 2 within the bounding box —
    # exactly cell_size + margin_size apart per column, with column 1
    # skipped (no cell emitted at the middle x position).
    pitch = geo.cell_size + geo.margin_size
    a, c = sorted(geo.cells, key=lambda cell: cell.x)
    assert c.x - a.x == pytest.approx(2 * pitch)


def test_each_cell_carries_its_slide_id_for_js_to_track_selection() -> None:
    # --- arrange ----------------------
    deck = _deck(_slide("intro", 0, 0), _slide("body", 1, 0), _slide("outro", 2, 0))

    # --- act --------------------------
    geo = compute_minimap_geometry(deck)

    # --- assert -----------------------
    assert [c.slide_id for c in geo.cells] == ["intro", "body", "outro"]
