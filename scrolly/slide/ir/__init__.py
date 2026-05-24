"""Slide IR package — the single slide IR, element models, and animated value types."""

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
    ScalarKeyframes,
    Vec2Keyframes,
)
from scrolly.slide.ir._framework.element import (
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideElement,
)
from scrolly.slide.ir._framework.utils import parse_json5_ir, resolve_asset_paths
from scrolly.slide.ir.slide import SlideIR

__all__ = [
    "AnimatedScalar",
    "AnimatedSizeDim",
    "AnimatedVec2",
    "HtmlElement",
    "IframeElement",
    "ImageElement",
    "ImageSequenceElement",
    "MarkdownElement",
    "MermaidElement",
    "ScalarKeyframes",
    "SlideElement",
    "SlideIR",
    "Vec2Keyframes",
    "parse_json5_ir",
    "resolve_asset_paths",
]
