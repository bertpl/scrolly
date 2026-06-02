"""Layer B — ``SlideHTML`` contract, ``SlideIR`` model, ``Renderer`` ABC.

Importing this package registers the single built-in slide type and its
renderer with the slide-level registry, plus the per-primitive element
renderers with the element-IR registry.
"""

from scrolly.slide.element_ir import renderers as _element_renderers  # noqa: F401 — register element renderers
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR, element_source_types
from scrolly.slide.processor import Renderer
from scrolly.slide.registry import (
    find_renderer,
    get_ir_class_for_path,
    register_ir,
    register_renderer,
    registered_ir_types,
    registered_suffixes,
)
from scrolly.slide.renderers.slide import SlideRenderer

register_ir(SlideIR)
register_renderer(SlideRenderer)

__all__ = [
    "Renderer",
    "SlideHTML",
    "SlideIR",
    "element_source_types",
    "find_renderer",
    "get_ir_class_for_path",
    "register_ir",
    "register_renderer",
    "registered_ir_types",
    "registered_suffixes",
]
