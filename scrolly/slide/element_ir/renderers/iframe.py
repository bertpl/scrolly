"""``IframeRenderer`` — renders an ``IframeElement`` primitive."""

from __future__ import annotations

from html import escape as html_escape

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import IframeElement


class IframeRenderer(ElementRenderer):
    """Renders an ``IframeElement`` to a ``RenderedElement``.

    When the rendering context carries a ``PayloadBundler``, the iframe's
    ``srcdoc`` payload is registered with the bundler and the iframe
    emits a ``data-scrolly-target`` marker (hydrated client-side after
    decompression). Otherwise, the uncompressed ``srcdoc="…"`` form is
    emitted directly.
    """

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `IframeElement` instances."""
        return isinstance(ir, IframeElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render an ``<iframe>`` element inside the standard wrapper.

        Args:
            ir: The ``IframeElement`` to render.
            ctx: Per-element rendering context. ``ctx.bundler`` controls
                whether ``srcdoc`` is inlined or slotted via the bundler.

        Returns:
            A ``RenderedElement`` whose ``html`` is the wrapped iframe
            and whose ``scoped_css`` is the substrate rule (extended with
            optional border / shadow extras) plus the inner-iframe
            sizing rule.
        """
        assert isinstance(ir, IframeElement)

        title_attr = f' title="{html_escape(ir.name)}"' if ir.name else ""
        if ctx.bundler is not None:
            srcdoc_bytes = ir.iframe_html.encode("utf-8")
            target_id = ctx.bundler.add(
                payload=srcdoc_bytes,
                mode="text",
                attr="srcdoc",
                baseline_len=len(html_escape(ir.iframe_html)),
            )
            src_attrs = f'data-scrolly-target="{target_id}"'
        else:
            src_attrs = f'srcdoc="{html_escape(ir.iframe_html)}"'
        inner = f'<iframe {src_attrs} sandbox="allow-scripts"{title_attr}></iframe>'
        html = wrap_element(inner, eid=ctx.eid, el=ir)

        extras = ""
        if ir.border_width > 0 or ir.shadow_size > 0:
            extras += "  box-sizing: border-box;\n"
        if ir.border_width > 0:
            extras += f"  border: {ir.border_width}px solid {ir.border_color};\n"
        if ir.shadow_size > 0:
            extras += f"  box-shadow: 0 0 {ir.shadow_size}px {ir.shadow_color};\n"

        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix, extras=extras)
        iframe_rule = (
            f"{ctx.selector_prefix} iframe {{\n  width: 100%;\n  height: 100%;\n  border: 0;\n  display: block;\n}}"
        )

        return RenderedElement(html=html, scoped_css=f"{substrate}\n\n{iframe_rule}")
