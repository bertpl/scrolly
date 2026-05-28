"""``RenderedElement`` — the per-element contribution bundle.

A primitive element renderer returns one of these. The slide-level
aggregator concatenates ``html`` and ``scoped_css``, unions
``snap_positions`` and ``assets``, and ORs ``has_mermaid`` across every
element on the slide.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderedElement:
    """Per-element contribution to the containing slide.

    Args:
        html: Rendered HTML fragment, inserted into the slide's content
            container at the element's position.
        scoped_css: Element-specific CSS rules, scoped under the
            element's selector prefix by the renderer that produced
            them. Concatenated into the slide's ``<style>`` block.
        snap_positions: Scroll positions the element registers, unioned
            with the slide's author-supplied snap positions.
        assets: External asset files the element references, unioned
            across the slide for asset bundling.
        has_mermaid: Whether the rendered HTML contains a mermaid
            diagram requiring the mermaid.js runtime. ORed across the
            slide.
    """

    html: str
    scoped_css: str = ""
    snap_positions: tuple[float, ...] = ()
    assets: tuple[Path, ...] = ()
    has_mermaid: bool = False
