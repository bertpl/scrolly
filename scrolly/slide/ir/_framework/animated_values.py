"""Animated value types for the unified animation model.

Each animatable property on a slide element accepts either a static value
or a keyframe-based animation (piecewise linear, held constant beyond the
extremal keyframe points).  Three ``RootModel`` wrapper types handle the
serialization/deserialization for each value shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel, model_validator


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
        if len(self.keyframes) < 2:
            raise ValueError("keyframes must contain at least 2 entries")
        positions = [kf[0] for kf in self.keyframes]
        for i in range(1, len(positions)):
            if positions[i] <= positions[i - 1]:
                raise ValueError(
                    f"keyframes must be sorted by scroll position with no duplicates; "
                    f"got {positions[i - 1]} followed by {positions[i]}"
                )
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
        if len(self.keyframes) < 2:
            raise ValueError("keyframes must contain at least 2 entries")
        positions = [kf[0] for kf in self.keyframes]
        for i in range(1, len(positions)):
            if positions[i] <= positions[i - 1]:
                raise ValueError(
                    f"keyframes must be sorted by scroll position with no duplicates; "
                    f"got {positions[i - 1]} followed by {positions[i]}"
                )
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
