"""Slide IR package — the single slide IR, element models, and animated value types."""

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
    ScalarKeyframes,
    Vec2Keyframes,
)
from scrolly.slide.ir._framework.element import (
    AnyElement,
    ContainerElement,
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideElement,
    element_source_types,
)
from scrolly.slide.ir._framework.utils import parse_json5_ir, resolve_asset_paths
from scrolly.slide.ir.slide import SlideIR

__all__ = [
    "AnimatedScalar",
    "AnimatedSizeDim",
    "AnimatedVec2",
    "AnyElement",
    "ContainerElement",
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
    "element_source_types",
    "parse_json5_ir",
    "resolve_asset_paths",
]
