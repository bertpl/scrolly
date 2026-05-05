"""Tests for scrollimation keyframe expansion and calc() expression generation."""

from __future__ import annotations

import pytest

from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    InitialState,
    Keyframe,
)
from scrolly.slide.renderers.scrollimation import (
    expand_scalar_timeline,
    expand_translate_timelines,
    ramp_expr,
)


def _anim(
    initial: dict | None = None,
    keyframes: list[dict] | None = None,
) -> ElementAnimation:
    return ElementAnimation(
        element=HtmlElement(
            name="L",
            html="<p>hi</p>",
            position=(0, 0),
            size=(100, 100),
        ),
        initial=InitialState(**(initial or {})),
        keyframes=[Keyframe(**kf) for kf in (keyframes or [])],
    )


# ── expand_scalar_timeline ────────────────────────────────────────


class TestExpandScalar:
    def test_no_keyframes_seeds_from_initial(self) -> None:
        anim = _anim(initial={"opacity": 0.5})
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert kfs == [(0, 0.5), (1000, 0.5)]

    def test_keyframe_at_zero_overrides_initial(self) -> None:
        anim = _anim(
            initial={"opacity": 0.5},
            keyframes=[{"at": 0, "opacity": 1}],
        )
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert kfs[0] == (0, 1)

    def test_seeds_initial_when_first_keyframe_not_at_zero(self) -> None:
        anim = _anim(
            initial={"opacity": 0},
            keyframes=[{"at": 500, "opacity": 1}],
        )
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert kfs[0] == (0, 0)
        assert kfs[1] == (500, 1)

    def test_extends_to_scroll_range(self) -> None:
        anim = _anim(keyframes=[{"at": 0, "opacity": 0}, {"at": 500, "opacity": 1}])
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert kfs[-1] == (1000, 1)

    def test_no_extension_when_last_at_equals_scroll_range(self) -> None:
        anim = _anim(keyframes=[{"at": 0, "opacity": 0}, {"at": 1000, "opacity": 1}])
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert len(kfs) == 2
        assert kfs[-1] == (1000, 1)

    def test_scroll_range_zero(self) -> None:
        anim = _anim(initial={"opacity": 0.5})
        kfs = expand_scalar_timeline("opacity", anim, 0)
        assert kfs == [(0, 0.5)]

    def test_ignores_other_properties(self) -> None:
        anim = _anim(
            keyframes=[
                {"at": 100, "scale": 2},
                {"at": 200, "opacity": 0.5},
            ]
        )
        kfs = expand_scalar_timeline("opacity", anim, 1000)
        assert any(v == 0.5 for _, v in kfs)
        assert not any(v == 2 for _, v in kfs)


# ── expand_translate_timelines ────────────────────────────────────


class TestExpandTranslate:
    def test_no_keyframes_seeds_from_initial(self) -> None:
        anim = _anim(initial={"translate": (10, 20)})
        kfs_x, kfs_y = expand_translate_timelines(anim, 1000)
        assert kfs_x == [(0, 10), (1000, 10)]
        assert kfs_y == [(0, 20), (1000, 20)]

    def test_keyframes_split_into_components(self) -> None:
        anim = _anim(
            keyframes=[
                {"at": 0, "translate": (0, 0)},
                {"at": 500, "translate": (50, -20)},
            ]
        )
        kfs_x, kfs_y = expand_translate_timelines(anim, 1000)
        assert (500, 50) in kfs_x
        assert (500, -20) in kfs_y


# ── ramp_expr ─────────────────────────────────────────────────────


class TestRampExpr:
    def test_constant_returns_none(self) -> None:
        assert ramp_expr([(0, 1), (1000, 1)]) is None

    def test_single_keyframe_returns_none(self) -> None:
        assert ramp_expr([(0, 0.5)]) is None

    def test_empty_returns_none(self) -> None:
        assert ramp_expr([]) is None

    def test_linear_ramp(self) -> None:
        expr = ramp_expr([(0, 0), (1000, 1)])
        assert expr is not None
        assert "var(--scroll-position, 0)" in expr
        assert "max(0," in expr

    def test_two_segment_v_shape(self) -> None:
        expr = ramp_expr([(0, 0), (500, 1), (1000, 0)])
        assert expr is not None
        assert "max(0," in expr

    def test_hold_segment_produces_fewer_terms(self) -> None:
        expr = ramp_expr([(0, 0), (200, 1), (800, 1), (1000, 0)])
        assert expr is not None


class TestRampExprEvaluation:
    """Evaluate the generated expressions numerically to verify correctness."""

    @staticmethod
    def _eval_expr(expr: str, scroll_pos: float) -> float:
        """Evaluate a ramp expression by substituting the scroll variable."""
        css = expr.replace("var(--scroll-position, 0)", str(scroll_pos))
        css = css.replace("max", "__max__")
        import re

        css = re.sub(r"__max__\(([^,]+),\s*([^)]+)\)", r"max(\1, \2)", css)
        return eval(css)

    def test_linear_ramp_evaluates(self) -> None:
        expr = ramp_expr([(0, 0), (1000, 1)])
        assert expr is not None
        assert abs(self._eval_expr(expr, 0) - 0) < 1e-9
        assert abs(self._eval_expr(expr, 500) - 0.5) < 1e-9
        assert abs(self._eval_expr(expr, 1000) - 1) < 1e-9

    def test_v_shape_evaluates(self) -> None:
        expr = ramp_expr([(0, 0), (500, 1), (1000, 0)])
        assert expr is not None
        assert abs(self._eval_expr(expr, 0) - 0) < 1e-9
        assert abs(self._eval_expr(expr, 250) - 0.5) < 1e-9
        assert abs(self._eval_expr(expr, 500) - 1) < 1e-9
        assert abs(self._eval_expr(expr, 750) - 0.5) < 1e-9
        assert abs(self._eval_expr(expr, 1000) - 0) < 1e-9

    def test_hold_then_ramp_evaluates(self) -> None:
        expr = ramp_expr([(0, 0), (200, 1), (800, 1), (1000, 0)])
        assert expr is not None
        assert abs(self._eval_expr(expr, 0) - 0) < 1e-9
        assert abs(self._eval_expr(expr, 200) - 1) < 1e-9
        assert abs(self._eval_expr(expr, 500) - 1) < 1e-9
        assert abs(self._eval_expr(expr, 1000) - 0) < 1e-9

    def test_value_holds_past_last_keyframe(self) -> None:
        expr = ramp_expr([(0, 0), (500, 1), (1000, 1)])
        assert expr is not None
        assert abs(self._eval_expr(expr, 1000) - 1) < 1e-9
        assert abs(self._eval_expr(expr, 1500) - 1) < 1e-9

    def test_step_function_evaluates(self) -> None:
        expr = ramp_expr([(0, 0), (500, 0), (500.001, 1), (1000, 1)])
        assert expr is not None
        assert abs(self._eval_expr(expr, 0) - 0) < 1e-3
        assert abs(self._eval_expr(expr, 499) - 0) < 1e-3
        assert abs(self._eval_expr(expr, 501) - 1) < 1e-3
        assert abs(self._eval_expr(expr, 1000) - 1) < 1e-3
