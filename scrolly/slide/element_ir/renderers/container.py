"""``ContainerRenderer`` — renders a ``ContainerElement`` and its children.

The container renders as one positioned ``<div>`` establishing a
%-coordinate system; children are rendered recursively (through the
compile loop, so nested containers and future high-level elements
work) and absolutely positioned within it. Coordinate mapping,
transform composition, and opacity multiplication all come from CSS
nesting — there is no coordinate rewriting.
"""

from __future__ import annotations

from pathlib import Path

from scrolly.errors import SlideSourceError
from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.registry import compile_to_primitives, find_element_renderer
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import substrate_css, wrap_element
from scrolly.slide.ir._framework.element import ContainerElement


class ContainerRenderer(ElementRenderer):
    """Renders a ``ContainerElement`` to a ``RenderedElement``."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `ContainerElement` instances."""
        return isinstance(ir, ContainerElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render the container div and, recursively, every child within it."""
        assert isinstance(ir, ContainerElement)

        # `isolation: isolate` forces a stacking context even when the
        # container has no transform and full opacity, so children's
        # z-indices stay local and the container occupies exactly one
        # z-slot in its parent's stacking order.
        extras = "  isolation: isolate;\n"

        htmls: list[str] = []
        csss: list[str] = [substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix, extras=extras)]
        assets: list[Path] = []
        snaps: list[float] = []
        has_mermaid = False

        for j, child in enumerate(ir.container):
            child_eid = f"{ctx.eid}.{j}"
            child_ctx = RenderContext(
                eid=child_eid,
                index=j,
                selector_prefix=f'{ctx.selector_prefix} > [data-element-id="{child_eid}"]',
                bundler=ctx.bundler,
            )
            for prim in compile_to_primitives(child):
                element_renderer = find_element_renderer(prim)
                if element_renderer is None:
                    raise SlideSourceError(
                        code="E601",
                        message=(
                            f"no element renderer registered for {type(prim).__name__} (container child index {j})"
                        ),
                    )
                rendered = element_renderer.render(prim, ctx=child_ctx)
                htmls.append(rendered.html)
                if rendered.scoped_css:
                    csss.append(rendered.scoped_css)
                assets.extend(rendered.assets)
                snaps.extend(rendered.snap_positions)
                if rendered.has_mermaid:
                    has_mermaid = True

        html = wrap_element("\n".join(htmls), eid=ctx.eid, el=ir)
        return RenderedElement(
            html=html,
            scoped_css="\n\n".join(csss),
            assets=tuple(assets),
            snap_positions=tuple(snaps),
            has_mermaid=has_mermaid,
        )
