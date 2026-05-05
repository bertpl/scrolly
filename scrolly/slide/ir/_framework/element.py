"""Shared slide-element models.

``SlideElement`` is the base for all positioned visual units within a
slide.  Concrete types (``ImageElement``, ``HtmlElement``,
``MarkdownElement``) carry content-specific fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SizeDim = float | Literal["auto"]


class SlideElement(BaseModel, frozen=True):
    """Base for all positioned visual units within a slide."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description="Optional human-readable label. Used in error messages only, not for rendering.",
    )
    position: tuple[float, float] = Field(
        description=(
            "Element position as [x%, y%] of the slide viewport. "
            "[0, 0] = top-left corner, [100, 100] = bottom-right corner. "
            "The anchor point of the element is placed at this position."
        ),
    )
    size: tuple[SizeDim, SizeDim] = Field(
        description=(
            "Element dimensions as [width%, height%] of the slide viewport. "
            'Use "auto" for one dimension to preserve aspect ratio (images) or '
            "size to content (text). At least one dimension must be numeric."
        ),
    )
    anchor: tuple[float, float] = Field(
        default=(0.0, 0.0),
        description=(
            "Reference point within the element as [x%, y%] of the element's own box. "
            "[0, 0] = top-left corner placed at position (default), "
            "[50, 50] = center placed at position. "
            "Also serves as the pivot for scale and rotate transforms."
        ),
    )

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

    image: Path = Field(
        description="Path to the image file, relative to the slide source file.",
    )
    object_fit: Literal["cover", "contain", "fill"] | None = Field(
        default=None,
        description=(
            "How the image fills its box. Required when both size dimensions are numeric, "
            'forbidden when one is "auto". '
            '"cover" fills the box (may crop), "contain" fits inside (may letterbox), '
            '"fill" stretches to fill exactly.'
        ),
    )

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

    html: str = Field(description="Raw HTML content, inserted verbatim into the slide.")


class MarkdownElement(SlideElement, frozen=True):
    """An element with markdown content, rendered to HTML at build time."""

    markdown: str = Field(description="Markdown content, rendered to HTML at build time.")
    color: str = Field(
        default="#808080",
        description="CSS color value for the rendered text.",
    )


class MermaidElement(SlideElement, frozen=True):
    """An element with mermaid diagram source, rendered client-side."""

    mermaid: str = Field(description="Mermaid diagram source code, rendered client-side by mermaid.js.")
