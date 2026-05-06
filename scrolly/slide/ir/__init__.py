"""Slide IR package — base class, element models, animation, and per-type IRs."""

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
    ScalarKeyframes,
    Vec2Keyframes,
)
from scrolly.slide.ir._framework.animation import ElementAnimation, InitialState, Keyframe
from scrolly.slide.ir._framework.base import SlideIR
from scrolly.slide.ir._framework.element import (
    HtmlElement,
    ImageElement,
    MarkdownElement,
    MermaidElement,
    SizeDim,
    SlideElement,
)
from scrolly.slide.ir._framework.utils import parse_json5_ir, resolve_asset_paths

__all__ = [
    "AnimatedScalar",
    "AnimatedSizeDim",
    "AnimatedVec2",
    "ElementAnimation",
    "HtmlElement",
    "ImageElement",
    "InitialState",
    "Keyframe",
    "MarkdownElement",
    "MermaidElement",
    "ScalarKeyframes",
    "SizeDim",
    "SlideElement",
    "SlideIR",
    "Vec2Keyframes",
    "parse_json5_ir",
    "resolve_asset_paths",
]
