"""ScrollimationIR model.

The scrollimation IR uses ``ElementAnimation`` wrappers around
``SlideElement`` subtypes.  Each animated element carries its own
``InitialState`` and sparse ``Keyframe`` list.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

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

    title: str = Field(description="Human-readable slide title, shown in navigation UI.")
    scroll_range: float = Field(
        description=(
            "Total scrollable distance in abstract scroll units. "
            "Keyframe 'at' values and snap positions reference this range. "
            "A slide with scroll_range=0 has no scroll behavior."
        ),
    )
    initial_scroll_position: float = Field(
        default=0,
        description="Scroll position the slide starts at on first visit. Must be within [0, scroll_range].",
    )
    scroll_speed: float = Field(
        default=1.0,
        description="Scroll speed multiplier. Values > 1 scroll faster, < 1 scroll slower.",
    )
    easing: Literal["linear"] = Field(
        default="linear",
        description="Easing function for scroll-driven animation. Currently only 'linear' is supported.",
    )
    snap_positions: tuple[int, ...] = Field(
        default=(),
        description=(
            "Scroll positions where the view settles after scrolling stops. Values must be within [0, scroll_range]."
        ),
    )
    elements: list[ElementAnimation] = Field(
        description="The animated elements in this slide, rendered in array order (first = bottom, last = top).",
    )

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

        seen_names: set[str] = set()
        for anim in self.elements:
            name = anim.element.name
            if name is not None:
                if name in seen_names:
                    raise ValueError(f"duplicate element name: {name!r}")
                seen_names.add(name)

        for i, anim in enumerate(self.elements):
            label = f"'{anim.element.name}'" if anim.element.name else f"[{i}]"
            for kf in anim.keyframes:
                if kf.at < 0 or kf.at > self.scroll_range:
                    raise ValueError(f"element {label}: keyframe at={kf.at} is outside [0, {self.scroll_range}]")
            self._check_duplicate_keyframes(anim, label)
            self._check_anchor_exclusivity(anim, label)

        for pos in self.snap_positions:
            if pos < 0 or pos > self.scroll_range:
                raise ValueError(f"snap_positions value {pos} is outside [0, {self.scroll_range}]")

        return self

    @staticmethod
    def _check_anchor_exclusivity(anim: ElementAnimation, label: str) -> None:
        has_animated = anim.initial.anchor is not None or any(kf.anchor is not None for kf in anim.keyframes)
        has_element_level = anim.element.anchor != (0.0, 0.0)
        if has_animated and has_element_level:
            raise ValueError(f"element {label}: anchor must be set on the element OR in initial/keyframes, not both")

    @staticmethod
    def _check_duplicate_keyframes(anim: ElementAnimation, label: str) -> None:
        props = ("opacity", "translate", "scale", "rotate", "anchor")
        for prop in props:
            ats: list[float] = []
            for kf in anim.keyframes:
                if getattr(kf, prop) is not None:
                    ats.append(kf.at)
            seen: set[float] = set()
            for at in ats:
                if at in seen:
                    raise ValueError(f"element {label}: duplicate keyframe at={at} for property {prop!r}")
                seen.add(at)
