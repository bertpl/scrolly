"""Geometry for the deck mini-map rendered inside the zoom-out control.

The zoom-out control in the top-left chrome renders in one of two styles:

- **Legacy icon** (selected via ``--simplified-zoom-control`` on
  ``scrolly build``): a single small chevron inside a fixed-size button.
  No deck-shape dependency, no precomputed geometry needed.
- **Mini-map** (default): a small grid mirroring the deck's bounding
  box, with one square cell per occupied slide position and a darker
  variant for the currently-selected slide.

This module precomputes the mini-map geometry from the deck shape so the
HTML/CSS can position each cell absolutely at build time; the JS only
toggles the ``selected`` class on slide change.
"""

from __future__ import annotations

from dataclasses import dataclass

from scrolly.deck import Deck

# Sizing constants. The container's minimum (40px) matches the existing
# ``.zoom-out-control`` size in canvas.css so the chrome-safe inset stays
# correctly sized for the mini-map's smallest form. The cap (64px) bounds
# how much screen real estate the control takes for large decks; beyond
# the cap, cell size shrinks to fit while the margin stays fixed.
MIN_SIZE_PX = 40
MAX_SIZE_PX = 64
CELL_PX_DEFAULT = 8
MARGIN_PX_DEFAULT = 4


@dataclass(frozen=True)
class MinimapCell:
    """One cell in the mini-map, positioned relative to the container."""

    slide_id: str
    x: float  # px from container left edge
    y: float  # px from container top edge


@dataclass(frozen=True)
class MinimapGeometry:
    """Precomputed mini-map layout: container size, cell metrics, per-slide cells.

    Container is always square. Cells are always square at ``cell_size``,
    spaced by ``margin_size``. Empty positions in the deck's bounding box
    produce no cell.
    """

    container_size: float  # px, always square
    cell_size: float  # px, always square
    margin_size: float  # px between adjacent cells
    cells: tuple[MinimapCell, ...]


def compute_minimap_geometry(deck: Deck) -> MinimapGeometry:
    """Precompute the mini-map geometry for a deck.

    Two kinds of margin contribute to the layout:

      - **Around-margin**: between the outermost cells and the container
        edge. Always ``MARGIN_PX_DEFAULT`` in every regime, so the cells
        keep a consistent breathing room from the edge regardless of
        how the cells themselves get sized.
      - **Between-margin** (the ``margin_size`` field on the returned
        ``MinimapGeometry``): between adjacent cells. Stays at
        ``MARGIN_PX_DEFAULT`` while the deck fits naturally, and
        shrinks proportionally with the cells in the over-cap regime
        (preserving the 2:1 cell-to-margin ratio of the defaults).

    Sizing algorithm:

      1. Compute the natural mini-map content size on each axis as
         ``2 * MARGIN_PX_DEFAULT + cols * CELL_PX_DEFAULT
          + (cols - 1) * MARGIN_PX_DEFAULT`` — the around-margin on
         both sides plus the cells and the between-margins.
      2. If the larger axis fits within ``MIN_SIZE_PX``, the container
         stays at ``MIN_SIZE_PX`` and the grid is centred inside it.
      3. If it fits between ``MIN_SIZE_PX`` and ``MAX_SIZE_PX``, the
         container grows to match.
      4. If it exceeds ``MAX_SIZE_PX``, the container is pinned at
         ``MAX_SIZE_PX``. The around-margin stays at
         ``MARGIN_PX_DEFAULT``; cell size and between-margin shrink
         proportionally so the grid fits the cap exactly along the
         dominant axis. The 2:1 cell-to-margin ratio is preserved.

    Args:
        deck: The deck whose slides will populate the mini-map.

    Returns:
        ``MinimapGeometry`` carrying the container size, the cell size,
        the between-cell margin, and a tuple of per-slide cell
        positions in container coordinates (already accounting for the
        constant around-margin). The bounding box's empty grid
        positions produce no cell.

        For an empty deck, returns the minimum-size container with no
        cells.
    """
    if not deck.slides:
        return MinimapGeometry(
            container_size=float(MIN_SIZE_PX),
            cell_size=float(CELL_PX_DEFAULT),
            margin_size=float(MARGIN_PX_DEFAULT),
            cells=(),
        )

    min_x = min(s.position.x for s in deck.slides)
    min_y = min(s.position.y for s in deck.slides)
    max_x = max(s.position.x for s in deck.slides)
    max_y = max(s.position.y for s in deck.slides)
    cols = max_x - min_x + 1
    rows = max_y - min_y + 1

    # The around-margin is constant in every regime. The between-margin
    # (and the cells) scale together in the over-cap regime to preserve
    # the cell-to-margin ratio.
    around_margin = float(MARGIN_PX_DEFAULT)

    natural_w = 2 * MARGIN_PX_DEFAULT + cols * CELL_PX_DEFAULT + max(0, cols - 1) * MARGIN_PX_DEFAULT
    natural_h = 2 * MARGIN_PX_DEFAULT + rows * CELL_PX_DEFAULT + max(0, rows - 1) * MARGIN_PX_DEFAULT
    natural_size = max(natural_w, natural_h)

    if natural_size <= MIN_SIZE_PX:
        container_size = float(MIN_SIZE_PX)
        cell_size = float(CELL_PX_DEFAULT)
        between_margin = float(MARGIN_PX_DEFAULT)
    elif natural_size <= MAX_SIZE_PX:
        container_size = float(natural_size)
        cell_size = float(CELL_PX_DEFAULT)
        between_margin = float(MARGIN_PX_DEFAULT)
    else:
        container_size = float(MAX_SIZE_PX)
        # Around-margin stays unscaled; cells + between-margins shrink
        # together so the grid fits the cap exactly along the dominant axis.
        max_dim = max(cols, rows)
        inner_default = max_dim * CELL_PX_DEFAULT + (max_dim - 1) * MARGIN_PX_DEFAULT
        scale = (MAX_SIZE_PX - 2 * MARGIN_PX_DEFAULT) / inner_default
        cell_size = CELL_PX_DEFAULT * scale
        between_margin = MARGIN_PX_DEFAULT * scale

    grid_w = 2 * around_margin + cols * cell_size + max(0, cols - 1) * between_margin
    grid_h = 2 * around_margin + rows * cell_size + max(0, rows - 1) * between_margin
    grid_offset_x = (container_size - grid_w) / 2
    grid_offset_y = (container_size - grid_h) / 2

    cells = tuple(
        MinimapCell(
            slide_id=slide.id,
            x=grid_offset_x + around_margin + (slide.position.x - min_x) * (cell_size + between_margin),
            y=grid_offset_y + around_margin + (slide.position.y - min_y) * (cell_size + between_margin),
        )
        for slide in deck.slides
    )

    return MinimapGeometry(
        container_size=container_size,
        cell_size=cell_size,
        margin_size=between_margin,
        cells=cells,
    )
