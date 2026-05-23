"""``ImageRenderer`` — renders an ``ImageElement`` primitive."""

from __future__ import annotations

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import ImageElement


class ImageRenderer(ElementRenderer):
    """Renders an ``ImageElement`` to a ``RenderedElement``."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `ImageElement` instances."""
        return isinstance(ir, ImageElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render a single ``<img>`` element inside the standard wrapper.

        Args:
            ir: The ``ImageElement`` to render.
            ctx: Per-element rendering context.

        Returns:
            A ``RenderedElement`` whose ``html`` is the wrapped ``<img>``
            and whose ``scoped_css`` is the substrate rule plus the
            inner-``img`` sizing rule.
        """
        assert isinstance(ir, ImageElement)
        inner = f'<img src="__asset__/{ir.image.name}" alt="">'
        html = wrap_element(inner, eid=ctx.eid, el=ir)

        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix)
        obj_fit_line = f"  object-fit: {ir.object_fit};\n" if ir.object_fit else ""
        img_rule = f"{ctx.selector_prefix} img {{\n  width: 100%;\n  height: 100%;\n{obj_fit_line}  display: block;\n}}"

        return RenderedElement(
            html=html,
            scoped_css=f"{substrate}\n\n{img_rule}",
            assets=(ir.image,),
        )
