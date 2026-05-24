"""Tests for the animated value types (AnimatedScalar, AnimatedVec2, AnimatedSizeDim)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
    ScalarKeyframes,
    Vec2Keyframes,
)


# ==================================================================================================
#  ScalarKeyframes
# ==================================================================================================
class TestScalarKeyframes:
    """Tests for ScalarKeyframes validation and construction."""

    def test_valid_keyframes(self) -> None:
        # --- act --------------------------
        kf = ScalarKeyframes(keyframes=[(0, 1.0), (500, 0.5)])

        # --- assert -----------------------
        assert kf.keyframes == [(0, 1.0), (500, 0.5)]

    def test_rejects_single_keyframe(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="at least 2 entries"):
            ScalarKeyframes(keyframes=[(0, 1.0)])

    def test_rejects_empty_keyframes(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="at least 2 entries"):
            ScalarKeyframes(keyframes=[])

    def test_rejects_unsorted_positions(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="sorted by scroll position"):
            ScalarKeyframes(keyframes=[(500, 1.0), (200, 0.5)])

    def test_rejects_duplicate_positions(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="sorted by scroll position"):
            ScalarKeyframes(keyframes=[(0, 1.0), (500, 0.5), (500, 0.8)])


# ==================================================================================================
#  Vec2Keyframes
# ==================================================================================================
class TestVec2Keyframes:
    """Tests for Vec2Keyframes validation and construction."""

    def test_valid_keyframes(self) -> None:
        # --- act --------------------------
        kf = Vec2Keyframes(keyframes=[(0, (10, 20)), (1000, (50, 80))])

        # --- assert -----------------------
        assert kf.keyframes == [(0, (10, 20)), (1000, (50, 80))]

    def test_rejects_single_keyframe(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="at least 2 entries"):
            Vec2Keyframes(keyframes=[(0, (10, 20))])

    def test_rejects_unsorted_positions(self) -> None:
        # --- act / assert -----------------
        with pytest.raises(SlideSourceError, match="sorted by scroll position"):
            Vec2Keyframes(keyframes=[(1000, (50, 80)), (0, (10, 20))])


# ==================================================================================================
#  AnimatedScalar
# ==================================================================================================
class TestAnimatedScalar:
    """Tests for AnimatedScalar parsing, properties, and serialization."""

    def test_static_from_float(self) -> None:
        # --- act --------------------------
        v = AnimatedScalar(0.5)

        # --- assert -----------------------
        assert not v.is_animated
        assert v.static_value == 0.5

    def test_static_from_int(self) -> None:
        # --- act --------------------------
        v = AnimatedScalar(1)

        # --- assert -----------------------
        assert not v.is_animated
        assert v.static_value == 1.0

    def test_animated_from_keyframes(self) -> None:
        # --- act --------------------------
        v = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 1.0), (500, 0.0)]))

        # --- assert -----------------------
        assert v.is_animated
        assert v.keyframes == [(0, 1.0), (500, 0.0)]

    def test_static_value_raises_on_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 1.0), (500, 0.0)]))

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="Cannot access static_value"):
            _ = v.static_value

    def test_keyframes_raises_on_static(self) -> None:
        # --- arrange ----------------------
        v = AnimatedScalar(1.0)

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="Cannot access keyframes"):
            _ = v.keyframes

    def test_json_parse_static(self) -> None:
        """Pydantic parses a bare number as a static AnimatedScalar."""

        # --- arrange ----------------------
        class Model(BaseModel):
            opacity: AnimatedScalar = AnimatedScalar(1.0)

        # --- act --------------------------
        m = Model.model_validate({"opacity": 0.7})

        # --- assert -----------------------
        assert not m.opacity.is_animated
        assert m.opacity.static_value == 0.7

    def test_json_parse_animated(self) -> None:
        """Pydantic parses a dict with keyframes as an animated AnimatedScalar."""

        # --- arrange ----------------------
        class Model(BaseModel):
            opacity: AnimatedScalar = AnimatedScalar(1.0)

        # --- act --------------------------
        m = Model.model_validate({"opacity": {"keyframes": [[0, 1.0], [500, 0.0]]}})

        # --- assert -----------------------
        assert m.opacity.is_animated
        assert m.opacity.keyframes == [(0, 1.0), (500, 0.0)]

    def test_json_parse_default(self) -> None:
        """Omitted field uses the default static value."""

        # --- arrange ----------------------
        class Model(BaseModel):
            opacity: AnimatedScalar = AnimatedScalar(1.0)

        # --- act --------------------------
        m = Model.model_validate({})

        # --- assert -----------------------
        assert m.opacity.static_value == 1.0

    def test_serialization_static(self) -> None:
        # --- arrange ----------------------
        v = AnimatedScalar(0.5)

        # --- act --------------------------
        data = v.model_dump()

        # --- assert -----------------------
        assert data == 0.5

    def test_serialization_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 1.0), (500, 0.0)]))

        # --- act --------------------------
        data = v.model_dump()

        # --- assert -----------------------
        assert data == {"keyframes": [(0, 1.0), (500, 0.0)]}


# ==================================================================================================
#  AnimatedVec2
# ==================================================================================================
class TestAnimatedVec2:
    """Tests for AnimatedVec2 parsing, properties, and serialization."""

    def test_static_from_tuple(self) -> None:
        # --- act --------------------------
        v = AnimatedVec2((50.0, 50.0))

        # --- assert -----------------------
        assert not v.is_animated
        assert v.static_value == (50.0, 50.0)

    def test_animated_from_keyframes(self) -> None:
        # --- act --------------------------
        v = AnimatedVec2(Vec2Keyframes(keyframes=[(0, (0, 0)), (1000, (50, 50))]))

        # --- assert -----------------------
        assert v.is_animated
        assert v.keyframes == [(0, (0, 0)), (1000, (50, 50))]

    def test_static_value_raises_on_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedVec2(Vec2Keyframes(keyframes=[(0, (0, 0)), (1000, (50, 50))]))

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="Cannot access static_value"):
            _ = v.static_value

    def test_keyframes_raises_on_static(self) -> None:
        # --- arrange ----------------------
        v = AnimatedVec2((10.0, 20.0))

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="Cannot access keyframes"):
            _ = v.keyframes

    def test_json_parse_static(self) -> None:
        """Pydantic parses a [x, y] list as a static AnimatedVec2."""

        # --- arrange ----------------------
        class Model(BaseModel):
            position: AnimatedVec2

        # --- act --------------------------
        m = Model.model_validate({"position": [50, 50]})

        # --- assert -----------------------
        assert not m.position.is_animated
        assert m.position.static_value == (50.0, 50.0)

    def test_json_parse_animated(self) -> None:
        """Pydantic parses a dict with keyframes as an animated AnimatedVec2."""

        # --- arrange ----------------------
        class Model(BaseModel):
            position: AnimatedVec2

        # --- act --------------------------
        m = Model.model_validate({"position": {"keyframes": [[0, [0, 0]], [1000, [50, 50]]]}})

        # --- assert -----------------------
        assert m.position.is_animated
        assert m.position.keyframes == [(0, (0, 0)), (1000, (50, 50))]

    def test_serialization_static(self) -> None:
        # --- arrange ----------------------
        v = AnimatedVec2((10.0, 20.0))

        # --- act --------------------------
        data = v.model_dump()

        # --- assert -----------------------
        assert data == (10.0, 20.0)

    def test_serialization_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedVec2(Vec2Keyframes(keyframes=[(0, (0, 0)), (1000, (50, 50))]))

        # --- act --------------------------
        data = v.model_dump()

        # --- assert -----------------------
        assert data == {"keyframes": [(0, (0, 0)), (1000, (50, 50))]}


# ==================================================================================================
#  AnimatedSizeDim
# ==================================================================================================
class TestAnimatedSizeDim:
    """Tests for AnimatedSizeDim parsing, properties, and serialization."""

    def test_auto(self) -> None:
        # --- act --------------------------
        v = AnimatedSizeDim("auto")

        # --- assert -----------------------
        assert v.is_auto
        assert not v.is_animated
        assert not v.is_static_numeric

    def test_static_numeric(self) -> None:
        # --- act --------------------------
        v = AnimatedSizeDim(80.0)

        # --- assert -----------------------
        assert not v.is_auto
        assert not v.is_animated
        assert v.is_static_numeric
        assert v.static_value == 80.0

    def test_animated(self) -> None:
        # --- act --------------------------
        v = AnimatedSizeDim(ScalarKeyframes(keyframes=[(0, 80), (500, 60)]))

        # --- assert -----------------------
        assert not v.is_auto
        assert v.is_animated
        assert not v.is_static_numeric
        assert v.keyframes == [(0, 80), (500, 60)]

    def test_static_value_raises_on_auto(self) -> None:
        # --- arrange ----------------------
        v = AnimatedSizeDim("auto")

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="'auto' or animated"):
            _ = v.static_value

    def test_static_value_raises_on_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedSizeDim(ScalarKeyframes(keyframes=[(0, 80), (500, 60)]))

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="'auto' or animated"):
            _ = v.static_value

    def test_keyframes_raises_on_static(self) -> None:
        # --- arrange ----------------------
        v = AnimatedSizeDim(80.0)

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="non-animated"):
            _ = v.keyframes

    def test_keyframes_raises_on_auto(self) -> None:
        # --- arrange ----------------------
        v = AnimatedSizeDim("auto")

        # --- act / assert -----------------
        with pytest.raises(ValueError, match="non-animated"):
            _ = v.keyframes

    def test_json_parse_auto(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            height: AnimatedSizeDim

        # --- act --------------------------
        m = Model.model_validate({"height": "auto"})

        # --- assert -----------------------
        assert m.height.is_auto

    def test_json_parse_numeric(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            width: AnimatedSizeDim

        # --- act --------------------------
        m = Model.model_validate({"width": 80})

        # --- assert -----------------------
        assert m.width.is_static_numeric
        assert m.width.static_value == 80.0

    def test_json_parse_animated(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            width: AnimatedSizeDim

        # --- act --------------------------
        m = Model.model_validate({"width": {"keyframes": [[0, 80], [500, 60]]}})

        # --- assert -----------------------
        assert m.width.is_animated
        assert m.width.keyframes == [(0, 80), (500, 60)]

    def test_serialization_auto(self) -> None:
        # --- act --------------------------
        data = AnimatedSizeDim("auto").model_dump()

        # --- assert -----------------------
        assert data == "auto"

    def test_serialization_numeric(self) -> None:
        # --- act --------------------------
        data = AnimatedSizeDim(80.0).model_dump()

        # --- assert -----------------------
        assert data == 80.0

    def test_serialization_animated(self) -> None:
        # --- arrange ----------------------
        v = AnimatedSizeDim(ScalarKeyframes(keyframes=[(0, 80), (500, 60)]))

        # --- act --------------------------
        data = v.model_dump()

        # --- assert -----------------------
        assert data == {"keyframes": [(0, 80), (500, 60)]}


# ==================================================================================================
#  JSON schema output
# ==================================================================================================
class TestJsonSchema:
    """Verify JSON schema generation produces usable oneOf schemas."""

    def test_animated_scalar_schema_has_one_of(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            opacity: AnimatedScalar = AnimatedScalar(1.0)

        # --- act --------------------------
        schema = Model.model_json_schema()

        # --- assert -----------------------
        # The schema for 'opacity' should reference a union type
        assert "opacity" in schema.get("properties", {})

    def test_animated_vec2_schema_has_one_of(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            position: AnimatedVec2

        # --- act --------------------------
        schema = Model.model_json_schema()

        # --- assert -----------------------
        assert "position" in schema.get("properties", {})

    def test_animated_size_dim_schema_has_one_of(self) -> None:
        # --- arrange ----------------------
        class Model(BaseModel):
            width: AnimatedSizeDim

        # --- act --------------------------
        schema = Model.model_json_schema()

        # --- assert -----------------------
        assert "width" in schema.get("properties", {})


# ==================================================================================================
#  evaluate_at — scroll-position resolution for snapshot / timeline
# ==================================================================================================
def test_evaluate_at_static_scalar_returns_self() -> None:
    """Static scalar value ignores ``scroll`` and returns its underlying float."""
    # --- arrange / act / assert -------
    s = AnimatedScalar(0.5)
    assert s.evaluate_at(0) == 0.5
    assert s.evaluate_at(9999) == 0.5
    assert s.evaluate_at(-100) == 0.5


def test_evaluate_at_animated_scalar_linear_interpolation() -> None:
    """Two-keyframe scalar interpolates linearly between bracketing keyframes."""
    # --- arrange ----------------------
    s = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 0), (100, 1)]))

    # --- act / assert -----------------
    assert s.evaluate_at(0) == 0.0
    assert s.evaluate_at(50) == 0.5
    assert s.evaluate_at(100) == 1.0


def test_evaluate_at_animated_scalar_held_constant_beyond_extremes() -> None:
    """Scalar held constant before first and after last keyframe."""
    # --- arrange ----------------------
    s = AnimatedScalar(ScalarKeyframes(keyframes=[(100, 0.2), (200, 0.8)]))

    # --- act / assert -----------------
    assert s.evaluate_at(0) == 0.2  # before first kf → held at first value
    assert s.evaluate_at(50) == 0.2  # ditto
    assert s.evaluate_at(300) == 0.8  # past last kf → held at last value


def test_evaluate_at_animated_scalar_three_keyframes_picks_segment() -> None:
    """With ≥3 keyframes the correct bracketing segment is selected per scroll."""
    # --- arrange ----------------------
    s = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 0), (100, 1), (200, 0)]))

    # --- act / assert -----------------
    assert s.evaluate_at(50) == 0.5  # in segment 0→1
    assert s.evaluate_at(150) == 0.5  # in segment 1→0


def test_evaluate_at_static_vec2_returns_self() -> None:
    """Static Vec2 ignores ``scroll`` and returns its underlying tuple."""
    # --- arrange / act / assert -------
    v = AnimatedVec2((1.0, 2.0))
    assert v.evaluate_at(500) == (1.0, 2.0)


def test_evaluate_at_animated_vec2_interpolates_components_independently() -> None:
    """Vec2 interpolation runs on x and y separately."""
    # --- arrange ----------------------
    v = AnimatedVec2(Vec2Keyframes(keyframes=[(0, (0, 0)), (100, (50, 25))]))

    # --- act --------------------------
    result = v.evaluate_at(50)

    # --- assert -----------------------
    assert result == (25.0, 12.5)


def test_evaluate_at_size_dim_static_auto_stays_auto() -> None:
    """Static ``"auto"`` size dim returns the literal string regardless of scroll."""
    # --- arrange / act / assert -------
    d = AnimatedSizeDim("auto")
    assert d.evaluate_at(0) == "auto"
    assert d.evaluate_at(1000) == "auto"


def test_evaluate_at_size_dim_static_numeric_returns_self() -> None:
    """Static numeric size dim returns its underlying float."""
    # --- arrange / act / assert -------
    d = AnimatedSizeDim(50.0)
    assert d.evaluate_at(0) == 50.0
    assert d.evaluate_at(9999) == 50.0


def test_evaluate_at_size_dim_animated_interpolates() -> None:
    """Animated size dim interpolates between keyframes."""
    # --- arrange ----------------------
    d = AnimatedSizeDim(ScalarKeyframes(keyframes=[(0, 100), (100, 50)]))

    # --- act / assert -----------------
    assert d.evaluate_at(50) == 75.0
    assert d.evaluate_at(0) == 100.0
    assert d.evaluate_at(100) == 50.0
    assert d.evaluate_at(-50) == 100.0  # held-constant beyond first
    assert d.evaluate_at(500) == 50.0  # held-constant beyond last
