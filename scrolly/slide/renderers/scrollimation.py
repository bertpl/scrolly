"""Render a ScrollimationIR into a SlideHTML.

Includes keyframe expansion and piecewise-linear CSS calc() expression
generation (absorbed from the former animation.py module).
"""

from __future__ import annotations

from html import escape as html_escape
from pathlib import Path

import markdown

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    ImageElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
)
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.processor import Renderer

_MD_EXTENSIONS: tuple[str, ...] = ("fenced_code", "tables", "sane_lists")
_SCROLL_VAR = "var(--scroll-position, 0)"


# ---------------------------------------------------------------------------
# Keyframe expansion and CSS expression generation
# ---------------------------------------------------------------------------


def expand_scalar_timeline(
    prop: str,
    anim: ElementAnimation,
    scroll_range: float,
) -> list[tuple[float, float]]:
    """Expand a scalar property's sparse keyframes into a sorted timeline."""
    kfs = [(kf.at, getattr(kf, prop)) for kf in anim.keyframes if getattr(kf, prop) is not None]
    kfs.sort(key=lambda x: x[0])

    initial_val = getattr(anim.initial, prop)
    if not kfs or kfs[0][0] > 0:
        kfs.insert(0, (0.0, initial_val))

    if scroll_range > 0 and kfs[-1][0] < scroll_range:
        kfs.append((scroll_range, kfs[-1][1]))

    return kfs


def expand_translate_timelines(
    anim: ElementAnimation,
    scroll_range: float,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Expand translate into separate x and y timelines."""
    kfs_x: list[tuple[float, float]] = []
    kfs_y: list[tuple[float, float]] = []
    for kf in anim.keyframes:
        if kf.translate is not None:
            kfs_x.append((kf.at, kf.translate[0]))
            kfs_y.append((kf.at, kf.translate[1]))
    kfs_x.sort(key=lambda x: x[0])
    kfs_y.sort(key=lambda x: x[0])

    ix, iy = anim.initial.translate
    if not kfs_x or kfs_x[0][0] > 0:
        kfs_x.insert(0, (0.0, ix))
    if not kfs_y or kfs_y[0][0] > 0:
        kfs_y.insert(0, (0.0, iy))

    if scroll_range > 0:
        if kfs_x[-1][0] < scroll_range:
            kfs_x.append((scroll_range, kfs_x[-1][1]))
        if kfs_y[-1][0] < scroll_range:
            kfs_y.append((scroll_range, kfs_y[-1][1]))

    return kfs_x, kfs_y


def ramp_expr(kfs: list[tuple[float, float]]) -> str | None:
    """Generate a CSS calc()-compatible sum-of-ramps expression.

    Returns ``None`` if the timeline is constant (all values equal),
    meaning the caller should emit a static CSS value instead.
    """
    if len(kfs) <= 1:
        return None

    if all(v == kfs[0][1] for _, v in kfs):
        return None

    v0 = kfs[0][1]
    slopes = [(kfs[i + 1][1] - kfs[i][1]) / (kfs[i + 1][0] - kfs[i][0]) for i in range(len(kfs) - 1)]

    parts = [_num(v0)]
    prev_slope = 0.0
    for i, slope in enumerate(slopes):
        delta = slope - prev_slope
        if abs(delta) > 1e-12:
            ramp = f"max(0, {_SCROLL_VAR} - {_num(kfs[i][0])})"
            if delta > 0:
                parts.append(f"+ {_num(delta)} * {ramp}")
            else:
                parts.append(f"- {_num(-delta)} * {ramp}")
        prev_slope = slope

    if abs(prev_slope) > 1e-12:
        ramp = f"max(0, {_SCROLL_VAR} - {_num(kfs[-1][0])})"
        if prev_slope > 0:
            parts.append(f"- {_num(prev_slope)} * {ramp}")
        else:
            parts.append(f"+ {_num(-prev_slope)} * {ramp}")

    return " ".join(parts)


def _num(v: float) -> str:
    """Format a float for CSS: drop trailing '.0' for integers."""
    return str(int(v)) if v == int(v) else str(v)


# ---------------------------------------------------------------------------
# ScrollimationRenderer
# ---------------------------------------------------------------------------


class ScrollimationRenderer(Renderer):
    """Renderer for the `scrollimation` slide type."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, ScrollimationIR)

    def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:
        assert isinstance(ir, ScrollimationIR)
        element_htmls = []
        asset_paths: list[Path] = []
        prefix = f"{css_namespace}-" if css_namespace else ""

        has_mermaid = False
        for i, anim in enumerate(ir.elements):
            el = anim.element
            content_html = _render_element_content(el)
            element_htmls.append(
                f'<div class="scrollimation-element" data-element-id="{prefix}{i}">{content_html}</div>'
            )
            if isinstance(el, ImageElement):
                asset_paths.append(el.image)
            if isinstance(el, MermaidElement):
                has_mermaid = True

        inner = "\n".join(element_htmls)
        slide_type = ir.slide_type
        html = f'<div class="slide-type-{slide_type}">\n{inner}\n</div>'

        scoped_css = _build_scoped_css(ir, slide_type, prefix)

        return SlideHTML(
            title=ir.title,
            html=html,
            scoped_css=scoped_css,
            scroll_range=int(ir.scroll_range) if ir.scroll_range > 0 else None,
            initial_scroll_position=int(ir.initial_scroll_position),
            scroll_speed=ir.scroll_speed,
            assets=tuple(asset_paths),
            snap_positions=ir.snap_positions,
            has_mermaid=has_mermaid,
        )


def _render_element_content(
    el: ImageElement | HtmlElement | MarkdownElement | MermaidElement,
) -> str:
    if isinstance(el, ImageElement):
        return f'<img src="__asset__/{el.image.name}" alt="">'
    if isinstance(el, HtmlElement):
        return el.html
    if isinstance(el, MermaidElement):
        return f'<pre class="mermaid">{html_escape(el.mermaid)}</pre>'
    return markdown.markdown(el.markdown, extensions=list(_MD_EXTENSIONS))


def _build_scoped_css(slide: ScrollimationIR, slide_type: str, prefix: str) -> str:
    ns = f".slide-type-{slide_type}"
    rules: list[str] = []

    rules.append(
        f"{ns} {{\n"
        f"  position: absolute;\n"
        f"  top: 0;\n"
        f"  left: 0;\n"
        f"  width: 100%;\n"
        f"  height: 100%;\n"
        f"  transform: translateY(calc(1px * var(--scroll-position, 0)));\n"
        f"}}"
    )

    rules.append(f"{ns} .scrollimation-element {{\n  position: absolute;\n  overflow: hidden;\n}}")

    has_mermaid = False
    for i, anim in enumerate(slide.elements):
        el = anim.element
        eid = f"{prefix}{i}"
        rules.append(_element_css(ns, anim, eid, i, slide.scroll_range))
        if isinstance(el, ImageElement):
            # width/height 100% works for all three valid size combinations:
            #  - both numeric + object_fit: img fills container, object-fit handles aspect ratio
            #  - width numeric + height "auto": container height is auto, so img height 100%
            #    resolves to auto (CSS circular dependency rule) — fills width, aspect ratio
            #  - width "auto" + height numeric: symmetric — img width resolves to auto
            obj_fit_line = f"  object-fit: {el.object_fit};\n" if el.object_fit else ""
            rules.append(
                f'{ns} [data-element-id="{eid}"] img {{\n'
                f"  width: 100%;\n"
                f"  height: 100%;\n"
                f"{obj_fit_line}"
                f"  display: block;\n"
                f"}}"
            )
        if isinstance(el, MermaidElement):
            has_mermaid = True

    if has_mermaid:
        rules.append(f"{ns} .mermaid svg {{\n  width: 100%;\n  height: 100%;\n}}")

    return "\n\n".join(rules)


def _element_css(
    ns: str,
    anim: ElementAnimation,
    eid: str,
    index: int,
    scroll_range: float,
) -> str:
    el = anim.element
    sel = f'{ns} [data-element-id="{eid}"]'
    px, py = el.position

    left_val = _position_expr(px, 0, anim, scroll_range)
    top_val = _position_expr(py, 1, anim, scroll_range)

    w, h = el.size
    width = "auto" if w == "auto" else f"{_num(w)}%"
    height = "auto" if h == "auto" else f"{_num(h)}%"

    ax, ay = el.anchor

    opacity_val = _scalar_expr("opacity", anim, scroll_range)
    scale_val = _scalar_expr("scale", anim, scroll_range)
    rotate_val = _scalar_expr("rotate", anim, scroll_range)

    anchor_translate = ""
    if ax != 0 or ay != 0:
        tx = f"-{_num(ax)}%" if ax != 0 else "0%"
        ty = f"-{_num(ay)}%" if ay != 0 else "0%"
        anchor_translate = f"translate({tx}, {ty}) "

    color_line = ""
    if isinstance(el, MarkdownElement):
        color_line = f"  color: {el.color};\n"

    return (
        f"{sel} {{\n"
        f"  left: {left_val};\n"
        f"  top: {top_val};\n"
        f"  width: {width};\n"
        f"  height: {height};\n"
        f"  transform-origin: {_num(ax)}% {_num(ay)}%;\n"
        f"  transform: {anchor_translate}scale({scale_val}) rotate({rotate_val});\n"
        f"  opacity: {opacity_val};\n"
        f"  z-index: {index};\n"
        f"{color_line}"
        f"}}"
    )


def _scalar_expr(
    prop: str,
    anim: ElementAnimation,
    scroll_range: float,
) -> str:
    """Generate CSS value for a scalar property (opacity, scale, rotate)."""
    kfs = expand_scalar_timeline(prop, anim, scroll_range)
    expr = ramp_expr(kfs)
    if expr is None:
        val = _num(kfs[0][1]) if kfs else _num(getattr(anim.initial, prop))
        if prop == "rotate":
            return f"{val}deg"
        return val
    if prop == "rotate":
        return f"calc(({expr}) * 1deg)"
    return f"calc({expr})"


def _position_expr(
    pos: float,
    axis: int,
    anim: ElementAnimation,
    scroll_range: float,
) -> str:
    """Generate CSS value for left or top (position + translate component)."""
    tx_kfs, ty_kfs = expand_translate_timelines(anim, scroll_range)
    kfs = tx_kfs if axis == 0 else ty_kfs
    expr = ramp_expr(kfs)
    if expr is None:
        static_translate = kfs[0][1] if kfs else anim.initial.translate[axis]
        return f"{_num(pos + static_translate)}%"
    return f"calc(({_num(pos)} + {expr}) * 1%)"
