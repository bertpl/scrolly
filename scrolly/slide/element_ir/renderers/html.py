"""``HtmlRenderer`` — renders an ``HtmlElement`` primitive."""

from __future__ import annotations

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import HtmlElement


class HtmlRenderer(ElementRenderer):
    """Renders an ``HtmlElement`` to a ``RenderedElement``."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `HtmlElement` instances."""
        return isinstance(ir, HtmlElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Wrap raw HTML in the standard element ``<div>``."""
        assert isinstance(ir, HtmlElement)
        html = wrap_element(ir.html, eid=ctx.eid, el=ir)
        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix)
        return RenderedElement(html=html, scoped_css=substrate)
