"""ScrollimationIR model.

The scrollimation IR contains a list of positioned elements, each with
animatable properties.  Properties can be either static values or
keyframe-based animations (piecewise linear, held constant beyond extremes).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from scrolly.slide.ir import (
    HtmlElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
    parse_json5_ir,
    resolve_asset_paths,
)

AnyElement = ImageElement | ImageSequenceElement | HtmlElement | MarkdownElement | MermaidElement


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
    reverse: bool = Field(
        default=False,
        description=(
            "When true, the scrollbar thumb starts at the bottom of the track and "
            "rises as the scroll value increases. Authoring values (keyframe `at`, "
            "`snap_positions`, `initial_scroll_position`) keep their normal "
            "meaning; only the scrollbar's thumb-position mapping and the sign of "
            "user-input deltas are flipped. Intended for naturally bottom-up "
            "content (e.g. git-tree visualisations) so authors can keep keyframes "
            "and image lists in their natural ascending order."
        ),
    )
    elements: list[AnyElement] = Field(
        description="The elements in this slide, rendered in array order (first = bottom, last = top).",
    )

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        """Parse a .scrollimation.json source file."""
        ir = parse_json5_ir(source_path, cls, "scrollimation")
        resolved = resolve_asset_paths(ir.elements, source_path.parent)
        if resolved != list(ir.elements):
            ir = ir.model_copy(update={"elements": resolved})
        return ir

    @model_validator(mode="after")
    def _validate_slide(self) -> ScrollimationIR:
        """Validate slide-level constraints."""
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
        for el in self.elements:
            if el.name is not None:
                if el.name in seen_names:
                    raise ValueError(f"duplicate element name: {el.name!r}")
                seen_names.add(el.name)

        for pos in self.snap_positions:
            if pos < 0 or pos > self.scroll_range:
                raise ValueError(f"snap_positions value {pos} is outside [0, {self.scroll_range}]")

        return self
