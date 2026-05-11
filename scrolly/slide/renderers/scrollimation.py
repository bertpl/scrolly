"""Render a ScrollimationIR into a SlideHTML.

Generates CSS with piecewise-linear calc() expressions for animated
properties.  Static properties emit plain CSS values.
"""

from __future__ import annotations

import json
from html import escape as html_escape
from pathlib import Path

import markdown

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import (
    HtmlElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
)
from scrolly.slide.ir._framework.animated_values import AnimatedScalar, AnimatedVec2
from scrolly.slide.ir.scrollimation import AnyElement, ScrollimationIR
from scrolly.slide.processor import Renderer

_MD_EXTENSIONS: tuple[str, ...] = ("fenced_code", "tables", "sane_lists")
_SCROLL_VAR = "var(--scroll-position, 0)"


# ==================================================================================================
#  CSS ramp expression generation
# ==================================================================================================


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


# ==================================================================================================
#  ScrollimationRenderer
# ==================================================================================================


class ScrollimationRenderer(Renderer):
    """Renderer for the `scrollimation` slide type."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        """Return True if this renderer handles the given IR type."""
        return isinstance(ir, ScrollimationIR)

    def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:
        """Render a ScrollimationIR to SlideHTML."""
        assert isinstance(ir, ScrollimationIR)
        element_htmls = []
        asset_paths: list[Path] = []
        prefix = f"{css_namespace}-" if css_namespace else ""

        has_mermaid = False
        for i, el in enumerate(ir.elements):
            content_html = _render_element_content(el)
            attrs = f'class="scrollimation-element" data-element-id="{prefix}{i}"'
            if el.opacity.is_animated:
                kf_json = json.dumps(el.opacity.keyframes, separators=(",", ":"))
                attrs += f" data-opacity-keyframes='{html_escape(kf_json)}'"
            element_htmls.append(f"<div {attrs}>{content_html}</div>")
            if isinstance(el, ImageElement):
                asset_paths.append(el.image)
            elif isinstance(el, ImageSequenceElement):
                asset_paths.extend(el.image_sequence)
            if isinstance(el, MermaidElement):
                has_mermaid = True

        inner = "\n".join(element_htmls)
        slide_type = ir.slide_type
        html = f'<div class="slide-type-{slide_type}">\n{inner}\n</div>'

        scoped_css = _build_scoped_css(ir, slide_type, prefix)

        unique_assets = list(dict.fromkeys(asset_paths))

        return SlideHTML(
            title=ir.title,
            html=html,
            scoped_css=scoped_css,
            scroll_range=int(ir.scroll_range) if ir.scroll_range > 0 else None,
            initial_scroll_position=int(ir.initial_scroll_position),
            scroll_speed=ir.scroll_speed,
            assets=tuple(unique_assets),
            snap_positions=ir.snap_positions,
            reverse=ir.reverse,
            has_mermaid=has_mermaid,
        )


# ==================================================================================================
#  Content rendering
# ==================================================================================================


def _render_element_content(el: AnyElement) -> str:
    """Render an element's content to HTML."""
    if isinstance(el, ImageElement):
        return f'<img src="__asset__/{el.image.name}" alt="">'
    if isinstance(el, ImageSequenceElement):
        return _render_image_sequence_imgs(el)
    if isinstance(el, HtmlElement):
        return el.html
    if isinstance(el, MermaidElement):
        return f'<pre class="mermaid">{html_escape(el.mermaid)}</pre>'
    return markdown.markdown(el.markdown, extensions=list(_MD_EXTENSIONS))


# --------------------------------------------------------------------------
#  Image sequence helpers
# --------------------------------------------------------------------------


def _render_image_sequence_imgs(el: ImageSequenceElement) -> str:
    """Render image-sequence content: one <img> per consecutive-run, each with its own opacity ramp."""
    runs = _image_sequence_runs(list(el.image_sequence))
    img_tags = []
    for run_idx, (path, i_start, _) in enumerate(runs):
        kfs = _image_sequence_run_keyframes(el, runs, run_idx)
        kf_json = json.dumps(kfs, separators=(",", ":"))
        img_tags.append(
            f'<img data-frame-index="{i_start}" '
            f"data-opacity-keyframes='{html_escape(kf_json)}' "
            f'src="__asset__/{path.name}" alt="">'
        )
    return "\n".join(img_tags)


def _image_sequence_runs(paths: list[Path]) -> list[tuple[Path, int, int]]:
    """Group consecutive identical paths into ``(path, start_idx, end_idx)`` runs."""
    runs: list[tuple[Path, int, int]] = []
    i = 0
    while i < len(paths):
        j = i
        while j + 1 < len(paths) and paths[j + 1] == paths[i]:
            j += 1
        runs.append((paths[i], i, j))
        i = j + 1
    return runs


def _image_sequence_run_keyframes(
    el: ImageSequenceElement,
    runs: list[tuple[Path, int, int]],
    run_idx: int,
) -> list[tuple[float, float]]:
    """Build opacity keyframes for one post-dedup run.

    The leading edge is ``fade_in`` for the first run (or absent when ``fade_in == 0``),
    and the inter-frame crossfade for every other run. The trailing edge is ``fade_out``
    for the last run (or absent when ``fade_out == 0``), and the inter-frame crossfade
    for every other run.
    """
    _, i_start, i_end = runs[run_idx]
    hold_start = el.scroll_offset + i_start * el.frame_distance
    hold_end = el.scroll_offset + i_end * el.frame_distance + el.hold
    crossfade = el.frame_distance - el.hold

    is_first = run_idx == 0
    is_last = run_idx == len(runs) - 1

    kfs: list[tuple[float, float]] = []

    if is_first:
        if el.fade_in > 0:
            kfs.append((hold_start - el.fade_in, 0.0))
        kfs.append((hold_start, 1.0))
    else:
        kfs.append((hold_start - crossfade, 0.0))
        kfs.append((hold_start, 1.0))

    kfs.append((hold_end, 1.0))

    if is_last:
        if el.fade_out > 0:
            kfs.append((hold_end + el.fade_out, 0.0))
    else:
        kfs.append((hold_end + crossfade, 0.0))

    return kfs


# ==================================================================================================
#  CSS generation
# ==================================================================================================


def _build_scoped_css(slide: ScrollimationIR, slide_type: str, prefix: str) -> str:
    """Build all scoped CSS rules for a scrollimation slide."""
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
    for i, el in enumerate(slide.elements):
        eid = f"{prefix}{i}"
        rules.append(_element_css(ns, el, eid, i))
        if isinstance(el, ImageElement):
            obj_fit_line = f"  object-fit: {el.object_fit};\n" if el.object_fit else ""
            rules.append(
                f'{ns} [data-element-id="{eid}"] img {{\n'
                f"  width: 100%;\n"
                f"  height: 100%;\n"
                f"{obj_fit_line}"
                f"  display: block;\n"
                f"}}"
            )
        elif isinstance(el, ImageSequenceElement):
            rules.extend(_image_sequence_css(ns, el, eid))
        if isinstance(el, MermaidElement):
            has_mermaid = True

    if has_mermaid:
        rules.append(f"{ns} .mermaid svg {{\n  width: 100%;\n  height: 100%;\n}}")

    return "\n\n".join(rules)


def _image_sequence_css(ns: str, el: ImageSequenceElement, eid: str) -> list[str]:
    """Build CSS rules for an image-sequence element: stacked img layout + per-run opacity ramps.

    The first ``<img>`` sits in normal flow so it establishes the container's intrinsic
    height (important when ``height: auto``); subsequent ``<img>`` tags are absolutely
    positioned to overlay it pixel-for-pixel.
    """
    sel = f'{ns} [data-element-id="{eid}"]'
    obj_fit_line = f"  object-fit: {el.object_fit};\n" if el.object_fit else ""

    rules = [
        f"{sel} img {{\n"
        f"  width: 100%;\n"
        f"  height: 100%;\n"
        f"{obj_fit_line}"
        f"  display: block;\n"
        f"}}",
        f"{sel} img:not(:first-of-type) {{\n  position: absolute;\n  top: 0;\n  left: 0;\n}}",
    ]

    runs = _image_sequence_runs(list(el.image_sequence))
    for run_idx, (_, i_start, _) in enumerate(runs):
        kfs = _image_sequence_run_keyframes(el, runs, run_idx)
        expr = ramp_expr(kfs)
        if expr is None:
            opacity_val = _num(kfs[0][1])
        else:
            opacity_val = f"calc({expr})"
        rules.append(f'{sel} img[data-frame-index="{i_start}"] {{\n  opacity: {opacity_val};\n}}')

    return rules


def _element_css(ns: str, el: AnyElement, eid: str, index: int) -> str:
    """Generate the CSS rule for a single element."""
    sel = f'{ns} [data-element-id="{eid}"]'

    left_val = _vec2_component_expr(el.position, 0, "%")
    top_val = _vec2_component_expr(el.position, 1, "%")

    width = _size_dim_expr(el.width)
    height = _size_dim_expr(el.height)

    opacity_val = _scalar_expr(el.opacity)
    scale_val = _scalar_expr(el.scale)
    angle_val = _scalar_expr(el.angle, unit="deg")

    origin_x, origin_y, anchor_translate = _anchor_exprs(el.anchor)

    extra_lines = ""
    if el.position.is_animated or el.anchor.is_animated or el.angle.is_animated:
        extra_lines += "  will-change: transform;\n"
    if isinstance(el, MarkdownElement):
        extra_lines += f"  color: {el.color};\n"
        if el.text_align != "left":
            extra_lines += f"  text-align: {el.text_align};\n"

    return (
        f"{sel} {{\n"
        f"  left: {left_val};\n"
        f"  top: {top_val};\n"
        f"  width: {width};\n"
        f"  height: {height};\n"
        f"  transform-origin: {origin_x} {origin_y};\n"
        f"  transform: {anchor_translate}scale({scale_val}) rotate({angle_val});\n"
        f"  opacity: {opacity_val};\n"
        f"  z-index: {index};\n"
        f"{extra_lines}"
        f"}}"
    )


# --------------------------------------------------------------------------
#  Expression helpers
# --------------------------------------------------------------------------


def _scalar_expr(field: AnimatedScalar, unit: str = "") -> str:
    """Generate CSS value for a scalar animated field."""
    if not field.is_animated:
        val = _num(field.static_value)
        return f"{val}{unit}" if unit else val
    expr = ramp_expr(field.keyframes)
    if expr is None:
        val = _num(field.keyframes[0][1])
        return f"{val}{unit}" if unit else val
    if unit:
        return f"calc(({expr}) * 1{unit})"
    return f"calc({expr})"


def _vec2_component_expr(field: AnimatedVec2, axis: int, unit: str = "") -> str:
    """Generate CSS value for one component (x=0, y=1) of an animated vec2."""
    if not field.is_animated:
        val = _num(field.static_value[axis])
        return f"{val}{unit}" if unit else val
    kfs = [(at, v[axis]) for at, v in field.keyframes]
    expr = ramp_expr(kfs)
    if expr is None:
        val = _num(kfs[0][1])
        return f"{val}{unit}" if unit else val
    return f"calc(({expr}) * 1{unit})" if unit else f"calc({expr})"


def _size_dim_expr(field) -> str:
    """Generate CSS value for a size dimension."""
    if field.is_auto:
        return "auto"
    if not field.is_animated:
        return f"{_num(field.static_value)}%"
    expr = ramp_expr(field.keyframes)
    if expr is None:
        return f"{_num(field.keyframes[0][1])}%"
    return f"calc(({expr}) * 1%)"


def _anchor_exprs(field: AnimatedVec2) -> tuple[str, str, str]:
    """Generate CSS transform-origin and translate expressions for anchor."""
    if not field.is_animated:
        ax, ay = field.static_value
        origin_x = f"{_num(ax)}%"
        origin_y = f"{_num(ay)}%"
        if ax != 0 or ay != 0:
            tx = f"-{_num(ax)}%" if ax != 0 else "0%"
            ty = f"-{_num(ay)}%" if ay != 0 else "0%"
            anchor_translate = f"translate({tx}, {ty}) "
        else:
            anchor_translate = ""
        return origin_x, origin_y, anchor_translate

    kfs_x = [(at, v[0]) for at, v in field.keyframes]
    kfs_y = [(at, v[1]) for at, v in field.keyframes]

    ax_expr = ramp_expr(kfs_x)
    ay_expr = ramp_expr(kfs_y)

    if ax_expr is None:
        origin_x = f"{_num(kfs_x[0][1])}%"
        tx = f"-{_num(kfs_x[0][1])}%" if kfs_x[0][1] != 0 else "0%"
    else:
        origin_x = f"calc({ax_expr} * 1%)"
        tx = f"calc(-1 * ({ax_expr}) * 1%)"

    if ay_expr is None:
        origin_y = f"{_num(kfs_y[0][1])}%"
        ty = f"-{_num(kfs_y[0][1])}%" if kfs_y[0][1] != 0 else "0%"
    else:
        origin_y = f"calc({ay_expr} * 1%)"
        ty = f"calc(-1 * ({ay_expr}) * 1%)"

    anchor_translate = f"translate({tx}, {ty}) "
    return origin_x, origin_y, anchor_translate
