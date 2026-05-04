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

    opacity: float = 1.0
    translate: tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0
    rotate: float = 0.0


class Keyframe(BaseModel, frozen=True):
    """A sparse keyframe — only the properties present have a value at this point."""

    at: float
    opacity: float | None = None
    translate: tuple[float, float] | None = None
    scale: float | None = None
    rotate: float | None = None


class ElementAnimation(BaseModel, frozen=True):
    """A slide element wrapped with scroll-driven animation."""

    element: ImageElement | HtmlElement | MarkdownElement | MermaidElement
    initial: InitialState = Field(default_factory=InitialState)
    keyframes: list[Keyframe] = Field(default_factory=list)
