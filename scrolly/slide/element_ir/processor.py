"""ABC hierarchy for element processors: compilers and renderers.

Mirrors ``scrolly.slide.processor`` at the element level. Compilers
expand or lower an ``ElementIR`` by one step into one or more
``ElementIR`` results; renderers turn a ``PrimitiveElement`` into a
``RenderedElement`` contribution bundle. Both share the ``can_process``
dispatch classmethod via ``ElementProcessor``. The slide-level
aggregator passes a ``RenderContext`` to every ``ElementRenderer.render``
call so the renderer can produce CSS scoped under the element's selector
and (optionally) bundle inline payloads for compression.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.rendered import RenderedElement

if TYPE_CHECKING:
    from scrolly.pipeline._bundler import PayloadBundler


@dataclass(frozen=True)
class RenderContext:
    """Per-element rendering context passed by the slide-level aggregator.

    Args:
        eid: The ``data-element-id`` attribute value for the element's
            outer wrapper.
        index: The element's position in its slide's element list;
            doubles as the element's ``z-index``.
        selector_prefix: CSS selector prefix under which the renderer
            must scope every rule it emits. Typically
            ``'.slide-type-<type> [data-element-id="<eid>"]'``.
        bundler: Optional ``PayloadBundler``; renderers that emit
            compressible inline payloads (iframe ``srcdoc``) register
            them here and emit a ``data-scrolly-target`` marker instead.
    """

    eid: str
    index: int
    selector_prefix: str
    bundler: PayloadBundler | None = None


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
    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement: ...
