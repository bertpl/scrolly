"""``MermaidRenderer`` — renders a ``MermaidElement`` primitive."""

from __future__ import annotations

from html import escape as html_escape

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import MermaidElement


class MermaidRenderer(ElementRenderer):
    """Renders a ``MermaidElement`` to a ``RenderedElement``.

    Signals via ``RenderedElement.has_mermaid`` that the slide aggregator
    must emit the slide-level ``.mermaid svg { … }`` rule and the page
    assembler must include the mermaid.js runtime.
    """

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `MermaidElement` instances."""
        return isinstance(ir, MermaidElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render a ``<pre class="mermaid">`` element inside the standard wrapper."""
        assert isinstance(ir, MermaidElement)
        inner = f'<pre class="mermaid">{html_escape(ir.mermaid)}</pre>'
        html = wrap_element(inner, eid=ctx.eid, el=ir)
        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix)
        return RenderedElement(html=html, scoped_css=substrate, has_mermaid=True)
