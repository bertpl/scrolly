"""Data model for the deck (Layer A).

The parser produces a `RawDeck` (edges may have omitted sides). The inference
step fills in omitted sides and produces a `Deck` (every edge side is known).
Downstream layers work exclusively with the fully-specified `Deck`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Side(Enum):
    """One of the four sides of a slide. Edges attach to sides."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class Position:
    """Integer grid position. x increases left → right, y increases top → bottom."""

    x: int
    y: int


@dataclass(frozen=True)
class Slide:
    """One slide on the canvas.

    The slide's *type* (which renderer handles it) is encoded in the
    `source` filename's suffix and resolved at render time via
    `scrolly.slide.get_renderer_for_path`. No `type` field on the model.
    """

    id: str
    position: Position
    source: Path


@dataclass(frozen=True)
class RawEndpoint:
    """Edge endpoint pre-inference — the side may be omitted."""

    slide_id: str
    side: Side | None


@dataclass(frozen=True)
class Endpoint:
    """Edge endpoint post-inference — the side is always known."""

    slide_id: str
    side: Side


@dataclass(frozen=True)
class RawEdge:
    """Undirected edge between two slides, pre-inference."""

    a: RawEndpoint
    b: RawEndpoint


@dataclass(frozen=True)
class Edge:
    """Undirected edge between two slides, fully specified."""

    a: Endpoint
    b: Endpoint


@dataclass(frozen=True)
class SlideGroup:
    """A named group of slides, visualised as a background rectangle in deck view."""

    label: str
    slide_ids: tuple[str, ...]
    color: str | None = None
    label_color: str | None = None


@dataclass(frozen=True)
class RawDeck:
    """Deck as parsed from disk, with edges potentially missing side info."""

    title: str | None
    slides: tuple[Slide, ...]
    edges: tuple[RawEdge, ...]
    groups: tuple[SlideGroup, ...] = ()


@dataclass(frozen=True)
class Deck:
    """Deck after inference, with every edge side fully specified."""

    title: str | None
    slides: tuple[Slide, ...]
    edges: tuple[Edge, ...]
    groups: tuple[SlideGroup, ...] = ()
