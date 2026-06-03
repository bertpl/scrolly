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
    RenderedElement,
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
        slide_type = ir.slide_type
        ns = f".slide-type-{slide_type}"

        # Wrapper geometry and the .slide-element child rule are
        # identical for every slide, so they live in canvas.css rather
        # than being emitted per-slide. Per-slide blocks for the same
        # selector would cascade by source order, and a numeric-range
        # slide later in the document could leak its counter-translate
        # transform onto every other wrapper — breaking physical scroll
        # on auto-range slides. The `scroll-mode-animation` class opts
        # the wrapper into the counter-translate behavior for numeric-
        # range slides; content-driven slides omit the class and let
        # the chunk's translation reach their content unobstructed.
        is_content_driven = not (isinstance(ir.scroll_range, (int, float)) and ir.scroll_range > 0)
        mode_class = "" if is_content_driven else " scroll-mode-animation"

        rendered_elements = self.render_elements(ir, css_namespace=css_namespace, bundler=bundler)

        element_htmls = [rendered.html for rendered in rendered_elements]
        css_rules = [rendered.scoped_css for rendered in rendered_elements if rendered.scoped_css]
        asset_paths: list[Path] = []
        element_snaps: list[float] = []
        has_mermaid = False
        for rendered in rendered_elements:
            asset_paths.extend(rendered.assets)
            element_snaps.extend(rendered.snap_positions)
            if rendered.has_mermaid:
                has_mermaid = True

        if has_mermaid:
            # `.mermaid svg { height: 100% }` only resolves against a
            # definite-height parent, but the `<pre class="mermaid">` is
            # content-height by default — so the SVG falls back to its
            # intrinsic height and overflows the box. Give the `<pre>` the
            # wrapper's height (and drop its default margin) to restore the
            # chain, so the SVG fits its box like an `<img>` does.
            css_rules.append(f"{ns} .mermaid {{\n  height: 100%;\n  margin: 0;\n}}")
            css_rules.append(f"{ns} .mermaid svg {{\n  width: 100%;\n  height: 100%;\n}}")

        inner = "\n".join(element_htmls)
        html = f'<div class="slide-type-{slide_type}{mode_class}">\n{inner}\n</div>'
        scoped_css = "\n\n".join(css_rules)
        unique_assets = list(dict.fromkeys(asset_paths))

        if is_content_driven:
            # ``"auto"`` (the substrate default) and ``0`` both signal
            # content-driven height to the canvas runtime.
            slide_html_scroll_range: int | None = None
        else:
            slide_html_scroll_range = int(ir.scroll_range)

        # Union author snap positions with element-derived ones (e.g.
        # image-sequence frame snaps), sorted + deduplicated — the same set
        # `scrolly introspect snaps` reports as `merged`.
        merged_snaps = tuple(sorted(set(ir.snap_positions) | set(element_snaps)))

        return SlideHTML(
            title=ir.title,
            html=html,
            scoped_css=scoped_css,
            scroll_range=slide_html_scroll_range,
            initial_scroll_position=int(ir.initial_scroll_position),
            scroll_speed=ir.scroll_speed,
            font_scale=ir.font_scale,
            assets=tuple(unique_assets),
            snap_positions=merged_snaps,
            reverse=ir.reverse,
            has_mermaid=has_mermaid,
        )

    def render_elements(
        self,
        ir: SlideIR,
        css_namespace: str = "",
        *,
        bundler: PayloadBundler | None = None,
    ) -> list[RenderedElement]:
        """Render each authored element to a ``RenderedElement``, in authored order.

        Sibling to :meth:`render`. ``render`` aggregates the per-element
        pieces into a single ``SlideHTML``; this helper returns the per-
        element pieces directly, which is what ``scrolly introspect dom``
        consumes.

        For the current 1:1 authored→primitive mapping (no element
        compilers are registered today, all built-in elements are
        primitives), each authored element produces one primitive and
        thus one ``RenderedElement``. If a future element compiler
        expands an authored element to multiple primitives, the
        primitives' ``html``, ``scoped_css``, ``assets`` and
        ``has_mermaid`` are merged into a single ``RenderedElement`` per
        authored element — preserving the one-entry-per-author-visible-
        element view that ``introspect dom`` and consumers like it
        depend on.

        Args:
            ir: The slide IR to render.
            css_namespace: Slide id used to scope element CSS rules.
            bundler: Optional payload bundler, threaded through to each
                primitive renderer via the ``RenderContext``.

        Returns:
            One ``RenderedElement`` per authored element, in order.
        """
        prefix = f"{css_namespace}-" if css_namespace else ""
        ns = f".slide-type-{ir.slide_type}"

        results: list[RenderedElement] = []
        for i, el in enumerate(ir.elements):
            eid = f"{prefix}{i}"
            selector_prefix = f'{ns} [data-element-id="{eid}"]'
            ctx = RenderContext(eid=eid, index=i, selector_prefix=selector_prefix, bundler=bundler)

            primitives = compile_to_primitives(el)
            htmls: list[str] = []
            csss: list[str] = []
            assets: list[Path] = []
            snaps: list[float] = []
            has_mermaid = False
            for prim in primitives:
                element_renderer = find_element_renderer(prim)
                if element_renderer is None:
                    raise SlideSourceError(
                        code="E601",
                        message=(f"no element renderer registered for {type(prim).__name__} (slide element index {i})"),
                    )
                rendered = element_renderer.render(prim, ctx=ctx)
                htmls.append(rendered.html)
                if rendered.scoped_css:
                    csss.append(rendered.scoped_css)
                assets.extend(rendered.assets)
                snaps.extend(rendered.snap_positions)
                if rendered.has_mermaid:
                    has_mermaid = True

            results.append(
                RenderedElement(
                    html="\n".join(htmls),
                    scoped_css="\n\n".join(csss),
                    assets=tuple(assets),
                    snap_positions=tuple(snaps),
                    has_mermaid=has_mermaid,
                )
            )

        return results
