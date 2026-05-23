"""ABC hierarchy for element processors: compilers and renderers.

Mirrors ``scrolly.slide.processor`` at the element level. Compilers
expand or lower an ``ElementIR`` by one step into one or more
``ElementIR`` results; renderers turn a ``PrimitiveElement`` into a
``RenderedElement`` contribution bundle. Both share the ``can_process``
dispatch classmethod via ``ElementProcessor``.
"""

from __future__ import annotations

import abc

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.rendered import RenderedElement


class ElementProcessor(abc.ABC):
    """Base for all element processors."""

    @classmethod
    @abc.abstractmethod
    def can_process(cls, ir: ElementIR) -> bool: ...


class ElementCompiler(ElementProcessor, abc.ABC):
    """Expands or lowers an ``ElementIR`` by one step into one or more ``ElementIR`` results."""

    @abc.abstractmethod
    def compile(self, ir: ElementIR) -> list[ElementIR]: ...


class ElementRenderer(ElementProcessor, abc.ABC):
    """Renders a ``PrimitiveElement`` into a ``RenderedElement`` contribution bundle."""

    @abc.abstractmethod
    def render(self, ir: PrimitiveElement) -> RenderedElement: ...
