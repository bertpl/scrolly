"""Element-level IR mechanism — parallel to ``scrolly.slide.ir``.

Where the slide-level IR mechanism dispatches by filename suffix and
lowers slide-source files down to a ``SlideHTML``, the element-level IR
mechanism dispatches by IR type and lowers authored elements down to
``PrimitiveElement`` instances that the per-primitive renderers can
emit. Concrete element types and registrations are not part of this
package — it carries only the abstractions and the compile loop.
"""

from __future__ import annotations

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import (
    ElementCompiler,
    ElementProcessor,
    ElementRenderer,
    RenderContext,
)
from scrolly.slide.element_ir.registry import (
    compile_to_primitives,
    find_element_compiler,
    find_element_renderer,
    register_element_compiler,
    register_element_renderer,
)
from scrolly.slide.element_ir.rendered import RenderedElement

__all__ = [
    "ElementCompiler",
    "ElementIR",
    "ElementProcessor",
    "ElementRenderer",
    "PrimitiveElement",
    "RenderContext",
    "RenderedElement",
    "compile_to_primitives",
    "find_element_compiler",
    "find_element_renderer",
    "register_element_compiler",
    "register_element_renderer",
]
