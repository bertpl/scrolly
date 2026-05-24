"""``MarkdownRenderer`` — renders a ``MarkdownElement`` primitive.

In v0.2.0 this is the single home of markdown-to-HTML conversion in the
scrollimation path. (The legacy ``static`` slide-type renderer still
runs its own conversion; that path is removed in a later collapsing PR.)
"""

from __future__ import annotations

import markdown

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import MarkdownElement

_MD_EXTENSIONS: tuple[str, ...] = ("fenced_code", "tables", "sane_lists")


class MarkdownRenderer(ElementRenderer):
    """Renders a ``MarkdownElement`` to a ``RenderedElement``."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `MarkdownElement` instances."""
        return isinstance(ir, MarkdownElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render markdown to HTML and wrap in the standard ``.scrollimation-element`` div.

        Markdown-specific properties (``color``, ``text_align``) become
        extra lines on the substrate CSS rule so the output keys
        byte-identically against the pre-mechanism renderer.
        """
        assert isinstance(ir, MarkdownElement)
        rendered_html = markdown.markdown(ir.markdown, extensions=list(_MD_EXTENSIONS))
        html = wrap_element(rendered_html, eid=ctx.eid, el=ir)

        # Skip emitting `color: inherit` since that's the CSS default
        # anyway — keeps the rendered <style> tidy when no explicit
        # colour is set.
        extras = ""
        if ir.color != "inherit":
            extras += f"  color: {ir.color};\n"
        if ir.text_align != "left":
            extras += f"  text-align: {ir.text_align};\n"

        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix, extras=extras)
        return RenderedElement(html=html, scoped_css=substrate)
