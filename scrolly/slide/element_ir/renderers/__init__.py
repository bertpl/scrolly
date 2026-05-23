"""Per-primitive element renderers — one per concrete ``SlideElement`` type.

Importing this package registers all built-in renderers with the
element-IR registry. The slide-level driver in
``scrolly.slide.renderers.scrollimation`` looks them up via
``find_element_renderer`` and aggregates the ``RenderedElement`` bundles.
"""

from __future__ import annotations

from scrolly.slide.element_ir.registry import register_element_renderer
from scrolly.slide.element_ir.renderers.html import HtmlRenderer
from scrolly.slide.element_ir.renderers.iframe import IframeRenderer
from scrolly.slide.element_ir.renderers.image import ImageRenderer
from scrolly.slide.element_ir.renderers.image_sequence import ImageSequenceRenderer
from scrolly.slide.element_ir.renderers.markdown import MarkdownRenderer
from scrolly.slide.element_ir.renderers.mermaid import MermaidRenderer

register_element_renderer(ImageRenderer)
register_element_renderer(ImageSequenceRenderer)
register_element_renderer(HtmlRenderer)
register_element_renderer(IframeRenderer)
register_element_renderer(MarkdownRenderer)
register_element_renderer(MermaidRenderer)

__all__ = [
    "HtmlRenderer",
    "IframeRenderer",
    "ImageRenderer",
    "ImageSequenceRenderer",
    "MarkdownRenderer",
    "MermaidRenderer",
]
