"""Slide IR package — base class, element models, animation, and per-type IRs."""

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
    "ImageElement",
    "ElementAnimation",
    "HtmlElement",
    "InitialState",
    "Keyframe",
    "MarkdownElement",
    "MermaidElement",
    "SizeDim",
    "SlideElement",
    "SlideIR",
    "parse_json5_ir",
    "resolve_asset_paths",
]
