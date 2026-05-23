"""Shared CSS-expression helpers used by every primitive renderer.

These mirror the helpers that previously lived in the monolithic
``scrolly.slide.renderers.scrollimation`` module. ``substrate_css``
builds the per-element substrate rule (position, size, transform,
opacity, z-index, ``will-change``) plus any renderer-supplied extras;
``wrap_element`` builds the standard ``.scrollimation-element`` wrapper
``<div>`` (including the ``data-opacity-keyframes`` attribute when the
element's opacity is animated).
"""

from __future__ import annotations

import json
from html import escape as html_escape

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
)
from scrolly.slide.ir._framework.element import SlideElement

_SCROLL_VAR = "var(--scroll-position, 0)"


# ==================================================================================================
#  Numeric formatting
# ==================================================================================================
def num(v: float) -> str:
    """Format a float for CSS: drop trailing ``.0`` for integer values."""
    return str(int(v)) if v == int(v) else str(v)


# ==================================================================================================
#  CSS ramp expressions
# ==================================================================================================
def ramp_expr(kfs: list[tuple[float, float]]) -> str | None:
    """Generate a CSS ``calc()``-compatible sum-of-ramps expression.

    Args:
        kfs: Keyframes as ``(scroll_position, value)`` tuples in
            increasing scroll order.

    Returns:
        A CSS expression string, or ``None`` if the timeline is constant
        (all values equal). When ``None``, the caller should emit a
        plain CSS value instead of a ``calc()`` expression.
    """
    if len(kfs) <= 1:
        return None

    if all(v == kfs[0][1] for _, v in kfs):
        return None

    v0 = kfs[0][1]
    slopes = [(kfs[i + 1][1] - kfs[i][1]) / (kfs[i + 1][0] - kfs[i][0]) for i in range(len(kfs) - 1)]

    parts = [num(v0)]
    prev_slope = 0.0
    for i, slope in enumerate(slopes):
        delta = slope - prev_slope
        if abs(delta) > 1e-12:
            ramp = f"max(0, {_SCROLL_VAR} - {num(kfs[i][0])})"
            if delta > 0:
                parts.append(f"+ {num(delta)} * {ramp}")
            else:
                parts.append(f"- {num(-delta)} * {ramp}")
        prev_slope = slope

    if abs(prev_slope) > 1e-12:
        ramp = f"max(0, {_SCROLL_VAR} - {num(kfs[-1][0])})"
        if prev_slope > 0:
            parts.append(f"- {num(prev_slope)} * {ramp}")
        else:
            parts.append(f"+ {num(-prev_slope)} * {ramp}")

    return " ".join(parts)


def scalar_expr(field: AnimatedScalar, unit: str = "") -> str:
    """Generate a CSS value string for a scalar animated field."""
    if not field.is_animated:
        val = num(field.static_value)
        return f"{val}{unit}" if unit else val
    expr = ramp_expr(field.keyframes)
    if expr is None:
        val = num(field.keyframes[0][1])
        return f"{val}{unit}" if unit else val
    if unit:
        return f"calc(({expr}) * 1{unit})"
    return f"calc({expr})"


def vec2_component_expr(field: AnimatedVec2, axis: int, unit: str = "") -> str:
    """Generate a CSS value string for one component (x=0, y=1) of an animated vec2."""
    if not field.is_animated:
        val = num(field.static_value[axis])
        return f"{val}{unit}" if unit else val
    kfs = [(at, v[axis]) for at, v in field.keyframes]
    expr = ramp_expr(kfs)
    if expr is None:
        val = num(kfs[0][1])
        return f"{val}{unit}" if unit else val
    return f"calc(({expr}) * 1{unit})" if unit else f"calc({expr})"


def size_dim_expr(field: AnimatedSizeDim) -> str:
    """Generate a CSS value string for a size dimension (``auto`` or animated %)."""
    if field.is_auto:
        return "auto"
    if not field.is_animated:
        return f"{num(field.static_value)}%"
    expr = ramp_expr(field.keyframes)
    if expr is None:
        return f"{num(field.keyframes[0][1])}%"
    return f"calc(({expr}) * 1%)"


def anchor_exprs(field: AnimatedVec2) -> tuple[str, str, str]:
    """Build the three CSS strings the anchor field contributes to a substrate rule.

    Args:
        field: The element's animated anchor field.

    Returns:
        Tuple ``(transform_origin_x, transform_origin_y,
        anchor_translate)``. ``anchor_translate`` is either an empty
        string (anchor is statically [0, 0]) or a ``translate(...) ``
        fragment with trailing space, ready to be concatenated with the
        rest of the ``transform: …`` value.
    """
    if not field.is_animated:
        ax, ay = field.static_value
        origin_x = f"{num(ax)}%"
        origin_y = f"{num(ay)}%"
        if ax != 0 or ay != 0:
            tx = f"-{num(ax)}%" if ax != 0 else "0%"
            ty = f"-{num(ay)}%" if ay != 0 else "0%"
            anchor_translate = f"translate({tx}, {ty}) "
        else:
            anchor_translate = ""
        return origin_x, origin_y, anchor_translate

    kfs_x = [(at, v[0]) for at, v in field.keyframes]
    kfs_y = [(at, v[1]) for at, v in field.keyframes]

    ax_expr = ramp_expr(kfs_x)
    ay_expr = ramp_expr(kfs_y)

    if ax_expr is None:
        origin_x = f"{num(kfs_x[0][1])}%"
        tx = f"-{num(kfs_x[0][1])}%" if kfs_x[0][1] != 0 else "0%"
    else:
        origin_x = f"calc({ax_expr} * 1%)"
        tx = f"calc(-1 * ({ax_expr}) * 1%)"

    if ay_expr is None:
        origin_y = f"{num(kfs_y[0][1])}%"
        ty = f"-{num(kfs_y[0][1])}%" if kfs_y[0][1] != 0 else "0%"
    else:
        origin_y = f"calc({ay_expr} * 1%)"
        ty = f"calc(-1 * ({ay_expr}) * 1%)"

    anchor_translate = f"translate({tx}, {ty}) "
    return origin_x, origin_y, anchor_translate


# ==================================================================================================
#  Substrate CSS rule
# ==================================================================================================
def substrate_css(
    el: SlideElement,
    *,
    index: int,
    selector_prefix: str,
    extras: str = "",
) -> str:
    """Build the per-element substrate CSS rule.

    Emits the standard properties shared by every element type (position,
    size, transform-origin, transform, opacity, z-index, and
    ``will-change`` when any transform input is animated), followed by
    any renderer-specific extras. The order of lines below matches the
    pre-element-mechanism rule emitted by the legacy monolithic
    renderer, so output stays byte-identical.

    Args:
        el: The element being rendered.
        index: Element index in its slide; doubles as ``z-index``.
        selector_prefix: CSS selector under which to emit the rule.
        extras: Additional pre-formatted CSS lines (each terminated by
            ``;\\n`` and indented by two spaces) injected just before
            the closing brace.

    Returns:
        A single CSS rule, no trailing newline.
    """
    left_val = vec2_component_expr(el.position, 0, "%")
    top_val = vec2_component_expr(el.position, 1, "%")
    width = size_dim_expr(el.width)
    height = size_dim_expr(el.height)
    opacity_val = scalar_expr(el.opacity)
    scale_val = scalar_expr(el.scale)
    angle_val = scalar_expr(el.angle, unit="deg")
    origin_x, origin_y, anchor_translate = anchor_exprs(el.anchor)

    will_change = ""
    if el.position.is_animated or el.anchor.is_animated or el.angle.is_animated:
        will_change = "  will-change: transform;\n"

    return (
        f"{selector_prefix} {{\n"
        f"  left: {left_val};\n"
        f"  top: {top_val};\n"
        f"  width: {width};\n"
        f"  height: {height};\n"
        f"  transform-origin: {origin_x} {origin_y};\n"
        f"  transform: {anchor_translate}scale({scale_val}) rotate({angle_val});\n"
        f"  opacity: {opacity_val};\n"
        f"  z-index: {index};\n"
        f"{will_change}{extras}"
        f"}}"
    )


# ==================================================================================================
#  Outer-wrapper HTML
# ==================================================================================================
def wrap_element(inner_html: str, *, eid: str, el: SlideElement) -> str:
    """Build the standard ``.scrollimation-element`` wrapper around inner HTML.

    Includes the ``data-opacity-keyframes`` attribute when the element's
    opacity is animated — consumed at runtime by ``canvas.js`` for
    scroll-driven opacity updates.
    """
    attrs = f'class="scrollimation-element" data-element-id="{eid}"'
    if el.opacity.is_animated:
        kf_json = json.dumps(el.opacity.keyframes, separators=(",", ":"))
        attrs += f" data-opacity-keyframes='{html_escape(kf_json)}'"
    return f"<div {attrs}>{inner_html}</div>"
