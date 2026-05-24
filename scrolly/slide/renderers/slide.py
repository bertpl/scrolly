"""Render a ``SlideIR`` to a ``SlideHTML`` by driving the element-IR mechanism.

The renderer is a thin driver: for each authored element it runs the
element-IR compile loop to lower the element to primitives, looks up
the matching ``ElementRenderer`` for each primitive, and aggregates the
returned ``RenderedElement`` contribution bundles. Type-specific
HTML / CSS generation lives in ``scrolly.slide.element_ir.renderers``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from scrolly.errors import SlideSourceError
from scrolly.slide.element_ir import (
    RenderContext,
    compile_to_primitives,
    find_element_renderer,
)
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Renderer

if TYPE_CHECKING:
    from scrolly.pipeline._bundler import PayloadBundler


class SlideRenderer(Renderer):
    """Renderer for the single slide type."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        """Return True for exactly-``SlideIR`` instances.

        Uses an exact-type match rather than ``isinstance`` so that
        future subclasses can register their own renderers without
        being intercepted by the built-in.
        """
        return type(ir) is SlideIR

    def render(
        self,
        ir: SlideIR,
        css_namespace: str = "",
        *,
        bundler: PayloadBundler | None = None,
    ) -> SlideHTML:
        """Render a ``SlideIR`` to ``SlideHTML``.

        Args:
            ir: The IR to render.
            css_namespace: Slide id used to scope element CSS rules.
            bundler: Optional payload bundler. When provided, iframe
                ``srcdoc`` payloads are registered with the bundler and
                emitted as slotted ``data-scrolly-target`` markers
                instead of inline ``srcdoc="…"``. When ``None``, the
                renderer emits the uncompressed inline form.

        Returns:
            The rendered ``SlideHTML``.
        """
        assert isinstance(ir, SlideIR)
        prefix = f"{css_namespace}-" if css_namespace else ""
        slide_type = ir.slide_type
        ns = f".slide-type-{slide_type}"

        element_htmls: list[str] = []
        css_rules: list[str] = [
            f"{ns} {{\n"
            f"  position: absolute;\n"
            f"  top: 0;\n"
            f"  left: 0;\n"
            f"  width: 100%;\n"
            f"  height: 100%;\n"
            f"  transform: translateY(calc(1px * var(--scroll-position, 0)));\n"
            f"}}",
            f"{ns} .scrollimation-element {{\n  position: absolute;\n  overflow: hidden;\n}}",
        ]
        asset_paths: list[Path] = []
        has_mermaid = False

        for i, el in enumerate(ir.elements):
            eid = f"{prefix}{i}"
            selector_prefix = f'{ns} [data-element-id="{eid}"]'
            ctx = RenderContext(
                eid=eid,
                index=i,
                selector_prefix=selector_prefix,
                bundler=bundler,
            )

            primitives = compile_to_primitives(el)
            for prim in primitives:
                renderer = find_element_renderer(prim)
                if renderer is None:
                    raise SlideSourceError(
                        f"no element renderer registered for {type(prim).__name__} (slide element index {i})"
                    )
                rendered = renderer.render(prim, ctx=ctx)
                element_htmls.append(rendered.html)
                if rendered.scoped_css:
                    css_rules.append(rendered.scoped_css)
                asset_paths.extend(rendered.assets)
                if rendered.has_mermaid:
                    has_mermaid = True

        if has_mermaid:
            css_rules.append(f"{ns} .mermaid svg {{\n  width: 100%;\n  height: 100%;\n}}")

        inner = "\n".join(element_htmls)
        html = f'<div class="slide-type-{slide_type}">\n{inner}\n</div>'
        scoped_css = "\n\n".join(css_rules)
        unique_assets = list(dict.fromkeys(asset_paths))

        if isinstance(ir.scroll_range, (int, float)) and ir.scroll_range > 0:
            slide_html_scroll_range: int | None = int(ir.scroll_range)
        else:
            # ``"auto"`` (the substrate default) and ``0`` both signal
            # content-driven height to the canvas runtime.
            slide_html_scroll_range = None

        return SlideHTML(
            title=ir.title,
            html=html,
            scoped_css=scoped_css,
            scroll_range=slide_html_scroll_range,
            initial_scroll_position=int(ir.initial_scroll_position),
            scroll_speed=ir.scroll_speed,
            font_scale=ir.font_scale,
            assets=tuple(unique_assets),
            snap_positions=ir.snap_positions,
            reverse=ir.reverse,
            has_mermaid=has_mermaid,
        )
