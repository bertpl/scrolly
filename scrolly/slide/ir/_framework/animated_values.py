"""Animated value types for the unified animation model.

Each animatable property on a slide element accepts either a static value
or a keyframe-based animation (piecewise linear, held constant beyond the
extremal keyframe points).  Three ``RootModel`` wrapper types handle the
serialization/deserialization for each value schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel, model_validator

from scrolly.errors import SlideSourceError


# ==================================================================================================
#  Internal helpers
# ==================================================================================================
def _validate_keyframe_positions(keyframes: list[tuple]) -> None:
    """Validate a keyframe list has ≥2 entries with strictly increasing positions.

    Shared by the scalar and vec2 keyframe containers: both store the
    scroll position as the first tuple element regardless of value schema.

    Raises:
        SlideSourceError: ``E308`` if the list has fewer than 2 entries or
            is not strictly sorted by scroll position.
    """
    if len(keyframes) < 2:
        raise SlideSourceError(code="E308", message="keyframes must contain at least 2 entries")
    positions = [kf[0] for kf in keyframes]
    for i in range(1, len(positions)):
        if positions[i] <= positions[i - 1]:
            raise SlideSourceError(
                code="E308",
                message=(
                    f"keyframes must be sorted by scroll position with no duplicates; "
                    f"got {positions[i - 1]} followed by {positions[i]}"
                ),
            )


def _interpolate_scalar(keyframes: list[tuple[float, float]], scroll: float) -> float:
    """Interpolate a scalar keyframe sequence at ``scroll``.

    Linear between bracketing keyframes; held constant beyond the first
    and last keyframe (the canonical scrolly convention for keyframe
    extrapolation, matching what the browser sees via the renderer's
    CSS ``calc()`` expressions).

    Args:
        keyframes: Sorted list of ``(scroll_position, value)`` tuples
            with at least two entries (validated upstream).
        scroll: Scroll position to evaluate at.

    Returns:
        Interpolated scalar value at ``scroll``.
    """
    if scroll <= keyframes[0][0]:
        return keyframes[0][1]
    if scroll >= keyframes[-1][0]:
        return keyframes[-1][1]
    for i in range(1, len(keyframes)):
        p2, v2 = keyframes[i]
        if p2 >= scroll:
            p1, v1 = keyframes[i - 1]
            t = (scroll - p1) / (p2 - p1)
            return v1 + (v2 - v1) * t
    # Unreachable: the held-constant cases above cover scroll outside the
    # extremes, and the loop finds a bracketing pair for any scroll strictly
    # between them.
    raise RuntimeError("keyframe interpolation gap")


# ==================================================================================================
#  Keyframe container models
# ==================================================================================================
class ScalarKeyframes(BaseModel, frozen=True):
    """Piecewise linear animation curve for a scalar property."""

    keyframes: list[tuple[float, float]] = Field(
        description=(
            "Keyframe list as [[scroll_position, value], ...]. "
            "Interpolated linearly between points; held constant beyond the first and last keyframe."
        ),
    )

    @model_validator(mode="after")
    def _validate(self) -> ScalarKeyframes:
        """Validate keyframe list is non-empty and sorted by scroll position."""
        _validate_keyframe_positions(self.keyframes)
        return self


class Vec2Keyframes(BaseModel, frozen=True):
    """Piecewise linear animation curve for a 2D vector property."""

    keyframes: list[tuple[float, tuple[float, float]]] = Field(
        description=(
            "Keyframe list as [[scroll_position, [x, y]], ...]. "
            "Interpolated linearly between points; held constant beyond the first and last keyframe."
        ),
    )

    @model_validator(mode="after")
    def _validate(self) -> Vec2Keyframes:
        """Validate keyframe list is non-empty and sorted by scroll position."""
        _validate_keyframe_positions(self.keyframes)
        return self


# ==================================================================================================
#  RootModel wrappers — the "potentially animated" types
# ==================================================================================================
class AnimatedScalar(RootModel[float | ScalarKeyframes], frozen=True):
    """A scalar property: either a static float or a keyframe animation."""

    @property
    def is_animated(self) -> bool:
        """True if this value has keyframes rather than being static."""
        return isinstance(self.root, ScalarKeyframes)

    @property
    def static_value(self) -> float:
        """Return the static float value.

        Raises:
            ValueError: If this is an animated value.
        """
        if self.is_animated:
            raise ValueError("Cannot access static_value on an animated property")
        return self.root

    @property
    def keyframes(self) -> list[tuple[float, float]]:
        """Return the keyframe list.

        Raises:
            ValueError: If this is a static value.
        """
        if not self.is_animated:
            raise ValueError("Cannot access keyframes on a static property")
        return self.root.keyframes

    def evaluate_at(self, scroll: float) -> float:
        """Resolve to a numeric value at the given scroll position.

        Static values return themselves regardless of ``scroll``; animated
        values linearly interpolate between bracketing keyframes, held
        constant beyond the first and last keyframe.
        """
        if not self.is_animated:
            return self.root
        return _interpolate_scalar(self.root.keyframes, scroll)


class AnimatedVec2(RootModel[tuple[float, float] | Vec2Keyframes], frozen=True):
    """A 2D vector property: either a static [x, y] or a keyframe animation."""

    @property
    def is_animated(self) -> bool:
        """True if this value has keyframes rather than being static."""
        return isinstance(self.root, Vec2Keyframes)

    @property
    def static_value(self) -> tuple[float, float]:
        """Return the static [x, y] value.

        Raises:
            ValueError: If this is an animated value.
        """
        if self.is_animated:
            raise ValueError("Cannot access static_value on an animated property")
        return self.root

    @property
    def keyframes(self) -> list[tuple[float, tuple[float, float]]]:
        """Return the keyframe list.

        Raises:
            ValueError: If this is a static value.
        """
        if not self.is_animated:
            raise ValueError("Cannot access keyframes on a static property")
        return self.root.keyframes

    def evaluate_at(self, scroll: float) -> tuple[float, float]:
        """Resolve to an ``(x, y)`` value at the given scroll position.

        Static values return themselves regardless of ``scroll``; animated
        values interpolate each component independently using the same
        linear / held-beyond-extremes rule as :class:`AnimatedScalar`.
        """
        if not self.is_animated:
            return self.root
        kf = self.root.keyframes
        x_kf = [(pos, xy[0]) for pos, xy in kf]
        y_kf = [(pos, xy[1]) for pos, xy in kf]
        return (_interpolate_scalar(x_kf, scroll), _interpolate_scalar(y_kf, scroll))


class AnimatedSizeDim(RootModel[Literal["auto"] | float | ScalarKeyframes], frozen=True):
    """A size dimension: ``"auto"``, a static number, or a keyframe animation."""

    @property
    def is_auto(self) -> bool:
        """True if this dimension is set to ``"auto"``."""
        return self.root == "auto"

    @property
    def is_animated(self) -> bool:
        """True if this value has keyframes rather than being static."""
        return isinstance(self.root, ScalarKeyframes)

    @property
    def is_static_numeric(self) -> bool:
        """True if this is a static numeric value (not "auto", not animated)."""
        return isinstance(self.root, (int, float))

    @property
    def static_value(self) -> float:
        """Return the static numeric value.

        Raises:
            ValueError: If this is "auto" or animated.
        """
        if not self.is_static_numeric:
            raise ValueError("Cannot access static_value: value is 'auto' or animated")
        return self.root

    @property
    def keyframes(self) -> list[tuple[float, float]]:
        """Return the keyframe list.

        Raises:
            ValueError: If this is not animated.
        """
        if not self.is_animated:
            raise ValueError("Cannot access keyframes on a non-animated property")
        return self.root.keyframes

    def evaluate_at(self, scroll: float) -> float | Literal["auto"]:
        """Resolve to a numeric value or ``"auto"`` at the given scroll position.

        Static ``"auto"`` stays ``"auto"`` regardless of ``scroll``; static
        numeric values return themselves; animated values interpolate via
        the shared scalar rule (keyframes here are always numeric — the
        schema forbids ``"auto"`` inside a keyframe list, so the held-
        constant extrapolation always produces a number).
        """
        if self.is_auto:
            return "auto"
        if self.is_animated:
            return _interpolate_scalar(self.root.keyframes, scroll)
        return self.root
