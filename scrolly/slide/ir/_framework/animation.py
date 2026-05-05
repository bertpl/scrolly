"""Scroll-driven animation models.

``ElementAnimation`` wraps a ``SlideElement`` with animation state
(initial property values + sparse keyframes).  Scrollimation slides
use ``ElementAnimation``; storyboard slides use bare elements and the
compiler wraps them during compilation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from scrolly.slide.ir._framework.element import HtmlElement, ImageElement, MarkdownElement, MermaidElement


class InitialState(BaseModel, frozen=True):
    """Property values at scroll position 0.

    Seeds the per-property timeline when no keyframe exists at ``at: 0``.
    """

    opacity: float = Field(default=1.0, description="Initial opacity. 0.0 = invisible, 1.0 = fully visible.")
    translate: tuple[float, float] = Field(
        default=(0.0, 0.0),
        description=(
            "Initial translation offset as [dx%, dy%] of the slide viewport. "
            "Added to position. Positive x = rightward, positive y = downward."
        ),
    )
    scale: float = Field(default=1.0, description="Initial scale factor. 1.0 = original size.")
    rotate: float = Field(default=0.0, description="Initial rotation in degrees. Positive = clockwise.")
    anchor: tuple[float, float] | None = Field(
        default=None,
        description=(
            "Anchor point at scroll position 0 as [x%, y%] of the element box. "
            "[0, 0] = top-left, [50, 50] = center, [100, 100] = bottom-right. "
            "Mutually exclusive with the element-level anchor field. "
            "Note: value is at scroll position 0, not at initial_scroll_position."
        ),
    )


class Keyframe(BaseModel, frozen=True):
    """A sparse keyframe — only the properties present have a value at this point."""

    at: float = Field(description="Scroll position (in scroll-range units) where this keyframe takes effect.")
    opacity: float | None = Field(default=None, description="Opacity at this scroll position (0.0 to 1.0).")
    translate: tuple[float, float] | None = Field(
        default=None,
        description="Translation offset as [dx%, dy%] of the slide viewport at this scroll position.",
    )
    scale: float | None = Field(default=None, description="Scale factor at this scroll position.")
    rotate: float | None = Field(default=None, description="Rotation in degrees at this scroll position.")
    anchor: tuple[float, float] | None = Field(
        default=None,
        description="Anchor point as [x%, y%] of the element box at this scroll position.",
    )


class ElementAnimation(BaseModel, frozen=True):
    """A slide element wrapped with scroll-driven animation."""

    element: ImageElement | HtmlElement | MarkdownElement | MermaidElement = Field(
        description="The visual element to animate.",
    )
    initial: InitialState = Field(
        default_factory=InitialState,
        description="Property values at scroll position 0, before any keyframes take effect.",
    )
    keyframes: list[Keyframe] = Field(
        default_factory=list,
        description=(
            "Sparse keyframes defining property values at specific scroll positions. "
            "Properties not present in a keyframe are unaffected at that point. "
            "The renderer interpolates linearly between keyframes."
        ),
    )
