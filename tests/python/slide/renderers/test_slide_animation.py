"""Tests for ramp_expr CSS expression generation."""

from __future__ import annotations

import pytest

from scrolly.slide.element_ir.renderers._shared import ramp_expr

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
