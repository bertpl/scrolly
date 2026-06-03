"""Tests for the shared CSS-expression helpers (``ramp_expr``, ``anchor_exprs``)."""

from __future__ import annotations

import pytest

from scrolly.slide.element_ir.renderers._shared import anchor_exprs, ramp_expr
from scrolly.slide.ir._framework.animated_values import AnimatedVec2, Vec2Keyframes


def _static(x: float, y: float) -> AnimatedVec2:
    """Build a static anchor vec2."""
    return AnimatedVec2((float(x), float(y)))


def _animated(keyframes: list) -> AnimatedVec2:
    """Build a keyframe-animated anchor vec2."""
    return AnimatedVec2(Vec2Keyframes(keyframes=keyframes))


# ── ramp_expr ─────────────────────────────────────────────────────


def test_constant_returns_none() -> None:
    assert ramp_expr([(0, 1), (1000, 1)]) is None


def test_single_keyframe_returns_none() -> None:
    assert ramp_expr([(0, 0.5)]) is None


def test_empty_returns_none() -> None:
    assert ramp_expr([]) is None


def test_linear_ramp() -> None:
    expr = ramp_expr([(0, 0), (1000, 1)])
    assert expr is not None
    assert "var(--scroll-position, 0)" in expr
    assert "max(0," in expr


def test_two_segment_v_shape() -> None:
    expr = ramp_expr([(0, 0), (500, 1), (1000, 0)])
    assert expr is not None
    assert "max(0," in expr


def test_hold_segment_produces_fewer_terms() -> None:
    expr = ramp_expr([(0, 0), (200, 1), (800, 1), (1000, 0)])
    assert expr is not None


# ── ramp_expr — numerical evaluation ──────────────────────────────


def _eval_expr(expr: str, scroll_pos: float) -> float:
    """Evaluate a ramp expression by substituting the scroll variable."""
    import re

    css = expr.replace("var(--scroll-position, 0)", str(scroll_pos))
    css = css.replace("max", "__max__")
    css = re.sub(r"__max__\(([^,]+),\s*([^)]+)\)", r"max(\1, \2)", css)
    return eval(css)


def test_linear_ramp_evaluates() -> None:
    expr = ramp_expr([(0, 0), (1000, 1)])
    assert expr is not None
    assert abs(_eval_expr(expr, 0) - 0) < 1e-9
    assert abs(_eval_expr(expr, 500) - 0.5) < 1e-9
    assert abs(_eval_expr(expr, 1000) - 1) < 1e-9


def test_v_shape_evaluates() -> None:
    expr = ramp_expr([(0, 0), (500, 1), (1000, 0)])
    assert expr is not None
    assert abs(_eval_expr(expr, 0) - 0) < 1e-9
    assert abs(_eval_expr(expr, 250) - 0.5) < 1e-9
    assert abs(_eval_expr(expr, 500) - 1) < 1e-9
    assert abs(_eval_expr(expr, 750) - 0.5) < 1e-9
    assert abs(_eval_expr(expr, 1000) - 0) < 1e-9


def test_hold_then_ramp_evaluates() -> None:
    expr = ramp_expr([(0, 0), (200, 1), (800, 1), (1000, 0)])
    assert expr is not None
    assert abs(_eval_expr(expr, 0) - 0) < 1e-9
    assert abs(_eval_expr(expr, 200) - 1) < 1e-9
    assert abs(_eval_expr(expr, 500) - 1) < 1e-9
    assert abs(_eval_expr(expr, 1000) - 0) < 1e-9


def test_value_holds_past_last_keyframe() -> None:
    expr = ramp_expr([(0, 0), (500, 1), (1000, 1)])
    assert expr is not None
    assert abs(_eval_expr(expr, 1000) - 1) < 1e-9
    assert abs(_eval_expr(expr, 1500) - 1) < 1e-9


def test_step_function_evaluates() -> None:
    expr = ramp_expr([(0, 0), (500, 0), (500.001, 1), (1000, 1)])
    assert expr is not None
    assert abs(_eval_expr(expr, 0) - 0) < 1e-3
    assert abs(_eval_expr(expr, 499) - 0) < 1e-3
    assert abs(_eval_expr(expr, 501) - 1) < 1e-3
    assert abs(_eval_expr(expr, 1000) - 1) < 1e-3


# ── anchor_exprs ──────────────────────────────────────────────────
#
# Characterization tests pinning the exact (origin_x, origin_y,
# anchor_translate) tuple for every anchor shape. `anchor_translate`
# is the negation of the origin, prepended to the `transform:` value so
# the element's anchor point lands on its position.


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        # Static [0, 0]: no translate fragment emitted at all.
        ((0, 0), ("0%", "0%", "")),
        ((50, 50), ("50%", "50%", "translate(-50%, -50%) ")),
        # One axis zero -> that axis's translate component is "0%".
        ((50, 0), ("50%", "0%", "translate(-50%, 0%) ")),
        ((0, 50), ("0%", "50%", "translate(0%, -50%) ")),
        ((25, 75), ("25%", "75%", "translate(-25%, -75%) ")),
        # Fractional value -> num() keeps the decimal.
        ((12.5, 0), ("12.5%", "0%", "translate(-12.5%, 0%) ")),
    ],
)
def test_anchor_exprs_static(anchor: tuple[float, float], expected: tuple[str, str, str]) -> None:
    assert anchor_exprs(_static(*anchor)) == expected


def test_anchor_exprs_static_negative_documents_current_output() -> None:
    # Documents (and locks) the CURRENT output for a negative static anchor:
    # the per-axis negation produces a double-minus "--10%", which is invalid
    # CSS. This is a pre-existing latent bug, not introduced here — the test
    # exists so the per-axis refactor preserves behavior exactly. Tracked for
    # a separate fix.
    assert anchor_exprs(_static(-10, 0)) == ("-10%", "0%", "translate(--10%, 0%) ")


def test_anchor_exprs_animated_both_axes_vary() -> None:
    # --- arrange ----------------------
    field = _animated([[0, [0, 0]], [1000, [100, 100]]])
    expr = ramp_expr([(0, 0.0), (1000, 100.0)])

    # --- act --------------------------
    origin_x, origin_y, translate = anchor_exprs(field)

    # --- assert -----------------------
    # The animated origin wraps the ramp expr as `calc(<expr> * 1%)` WITHOUT
    # parens around <expr> (so `* 1%` binds only the last term — a pre-existing
    # latent bug locked here); the translate side parenthesizes as
    # `calc(-1 * (<expr>) * 1%)`. Both reproduced verbatim by the refactor.
    assert origin_x == f"calc({expr} * 1%)"
    assert origin_y == f"calc({expr} * 1%)"
    assert translate == f"translate(calc(-1 * ({expr}) * 1%), calc(-1 * ({expr}) * 1%)) "


def test_anchor_exprs_animated_constant_axis_uses_plain_percent() -> None:
    # --- arrange ----------------------
    # x holds constant at 50 (ramp_expr -> None), y varies. Animated fields
    # always emit a translate fragment, even for the held axis.
    field = _animated([[0, [50, 0]], [1000, [50, 100]]])
    expr_y = ramp_expr([(0, 0.0), (1000, 100.0)])

    # --- act --------------------------
    origin_x, origin_y, translate = anchor_exprs(field)

    # --- assert -----------------------
    assert origin_x == "50%"
    assert origin_y == f"calc({expr_y} * 1%)"
    assert translate == f"translate(-50%, calc(-1 * ({expr_y}) * 1%)) "


def test_anchor_exprs_animated_constant_zero_axis() -> None:
    # --- arrange ----------------------
    # x holds constant at 0 -> origin "0%" and translate component "0%".
    field = _animated([[0, [0, 0]], [1000, [0, 100]]])
    expr_y = ramp_expr([(0, 0.0), (1000, 100.0)])

    # --- act --------------------------
    origin_x, origin_y, translate = anchor_exprs(field)

    # --- assert -----------------------
    assert origin_x == "0%"
    assert origin_y == f"calc({expr_y} * 1%)"
    assert translate == f"translate(0%, calc(-1 * ({expr_y}) * 1%)) "
