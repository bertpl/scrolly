"""ScrollimationIR model.

The scrollimation IR uses ``ElementAnimation`` wrappers around
``SlideElement`` subtypes.  Each animated element carries its own
``InitialState`` and sparse ``Keyframe`` list.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import model_validator

from scrolly.slide.ir import (
    ElementAnimation,
    SlideIR,
    parse_json5_ir,
    resolve_asset_paths,
)


class ScrollimationIR(SlideIR, frozen=True):
    """Top-level IR for a .scrollimation.json source file."""

    SUFFIX: ClassVar[str] = ".scrollimation.json"
    DESCRIPTION: ClassVar[str] = "Scroll-driven animation"

    title: str
    scroll_range: float
    initial_scroll_position: float = 0
    scroll_speed: float = 1.0
    easing: Literal["linear"] = "linear"
    snap_positions: tuple[int, ...] = ()
    elements: list[ElementAnimation]

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        ir = parse_json5_ir(source_path, cls, "scrollimation")
        resolved = resolve_asset_paths(ir.elements, source_path.parent)
        if resolved != list(ir.elements):
            ir = ir.model_copy(update={"elements": resolved})
        return ir

    @model_validator(mode="after")
    def _validate_slide(self) -> ScrollimationIR:
        if self.scroll_range < 0:
            raise ValueError(f"scroll_range must be >= 0, got {self.scroll_range}")
        if self.initial_scroll_position < 0:
            raise ValueError(f"initial_scroll_position must be >= 0, got {self.initial_scroll_position}")
        if self.initial_scroll_position > self.scroll_range:
            raise ValueError(
                f"initial_scroll_position ({self.initial_scroll_position}) "
                f"must be <= scroll_range ({self.scroll_range})"
            )
        if not self.elements:
            raise ValueError("at least one element is required")

        ids = [anim.element.id for anim in self.elements]
        seen: set[str | None] = set()
        for lid in ids:
            if lid is not None and lid in seen:
                raise ValueError(f"duplicate element id: {lid!r}")
            if lid is not None:
                seen.add(lid)

        for anim in self.elements:
            for kf in anim.keyframes:
                if kf.at < 0 or kf.at > self.scroll_range:
                    raise ValueError(
                        f"element {anim.element.id!r}: keyframe at={kf.at} is outside [0, {self.scroll_range}]"
                    )
            self._check_duplicate_keyframes(anim)

        for pos in self.snap_positions:
            if pos < 0 or pos > self.scroll_range:
                raise ValueError(f"snap_positions value {pos} is outside [0, {self.scroll_range}]")

        return self

    @staticmethod
    def _check_duplicate_keyframes(anim: ElementAnimation) -> None:
        props = ("opacity", "translate", "scale", "rotate")
        for prop in props:
            ats: list[float] = []
            for kf in anim.keyframes:
                if getattr(kf, prop) is not None:
                    ats.append(kf.at)
            seen: set[float] = set()
            for at in ats:
                if at in seen:
                    raise ValueError(f"element {anim.element.id!r}: duplicate keyframe at={at} for property {prop!r}")
                seen.add(at)
