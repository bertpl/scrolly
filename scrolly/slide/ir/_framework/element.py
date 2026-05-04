"""Shared slide-element models.

``SlideElement`` is the base for all positioned visual units within a
slide.  Concrete types (``ImageElement``, ``HtmlElement``,
``MarkdownElement``) carry content-specific fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

SizeDim = float | Literal["auto"]


class SlideElement(BaseModel, frozen=True):
    """Base for all positioned visual units within a slide."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    position: tuple[float, float]
    size: tuple[SizeDim, SizeDim]
    transform_origin: tuple[float, float] = (50.0, 50.0)

    @model_validator(mode="after")
    def _validate_size(self) -> SlideElement:
        w, h = self.size
        w_numeric = isinstance(w, (int, float)) and not isinstance(w, bool)
        h_numeric = isinstance(h, (int, float)) and not isinstance(h, bool)
        if not w_numeric and not h_numeric:
            raise ValueError('at least one size dimension must be numeric; got ["auto", "auto"]')
        if w_numeric and w <= 0:
            raise ValueError(f"numeric size width must be > 0, got {w}")
        if h_numeric and h <= 0:
            raise ValueError(f"numeric size height must be > 0, got {h}")
        return self


class ImageElement(SlideElement, frozen=True):
    """An element backed by an external image file (PNG, JPEG, SVG, etc.)."""

    image: Path
    object_fit: Literal["cover", "contain", "fill"] | None = None

    @model_validator(mode="after")
    def _validate_object_fit(self) -> ImageElement:
        w, h = self.size
        both_numeric = (
            isinstance(w, (int, float))
            and not isinstance(w, bool)
            and isinstance(h, (int, float))
            and not isinstance(h, bool)
        )
        if both_numeric and self.object_fit is None:
            raise ValueError("object_fit is required when both size dimensions are numeric")
        if not both_numeric and self.object_fit is not None:
            raise ValueError('object_fit is forbidden when a size dimension is "auto"')
        return self


class HtmlElement(SlideElement, frozen=True):
    """An element with inline HTML content."""

    html: str


class MarkdownElement(SlideElement, frozen=True):
    """An element with markdown content, rendered to HTML at build time."""

    markdown: str
    color: str = "#808080"


class MermaidElement(SlideElement, frozen=True):
    """An element with mermaid diagram source, rendered client-side."""

    mermaid: str
