"""Slide IR package — base class, element models, animated value types, and per-type IRs."""

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
    ScalarKeyframes,
    Vec2Keyframes,
)
from scrolly.slide.ir._framework.base import SlideIR
from scrolly.slide.ir._framework.element import (
    HtmlElement,
    ImageElement,
    MarkdownElement,
    MermaidElement,
    SlideElement,
)
from scrolly.slide.ir._framework.utils import parse_json5_ir, resolve_asset_paths

__all__ = [
    "AnimatedScalar",
    "AnimatedSizeDim",
    "AnimatedVec2",
    "HtmlElement",
    "ImageElement",
    "MarkdownElement",
    "MermaidElement",
    "ScalarKeyframes",
    "SlideElement",
    "SlideIR",
    "Vec2Keyframes",
    "parse_json5_ir",
    "resolve_asset_paths",
]
