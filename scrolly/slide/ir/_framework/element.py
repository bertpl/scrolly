"""Shared slide-element models.

``SlideElement`` is the base for all positioned visual units within a
slide.  Concrete types (``ImageElement``, ``ImageSequenceElement``,
``HtmlElement``, ``MarkdownElement``, ``MermaidElement``) carry
content-specific fields.

Each animatable property accepts either a static value or a keyframe
animation definition (piecewise linear, held constant beyond extremes).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
)

# ==================================================================================================
#  SlideElement base
# ==================================================================================================


class SlideElement(BaseModel, frozen=True):
    """Base for all positioned visual units within a slide."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        description="Optional human-readable label. Used in error messages only, not for rendering.",
    )
    position: AnimatedVec2 = Field(
        description=(
            "Element position as [x%, y%] of the slide viewport, or animated via keyframes. "
            "[0, 0] = top-left corner, [100, 100] = bottom-right corner. "
            "The anchor point of the element is placed at this position."
        ),
    )
    width: AnimatedSizeDim = Field(
        description=(
            'Element width as % of slide viewport, "auto", or animated via keyframes. '
            'Use "auto" to preserve aspect ratio (images) or size to content (text).'
        ),
    )
    height: AnimatedSizeDim = Field(
        description=(
            'Element height as % of slide viewport, "auto", or animated via keyframes. '
            'Use "auto" to preserve aspect ratio (images) or size to content (text).'
        ),
    )
    anchor: AnimatedVec2 = Field(
        default=AnimatedVec2((0.0, 0.0)),
        description=(
            "Reference point within the element as [x%, y%] of the element's own box, "
            "or animated via keyframes. "
            "[0, 0] = top-left corner placed at position (default), "
            "[50, 50] = center placed at position. "
            "Also serves as the pivot for scale and angle transforms."
        ),
    )
    opacity: AnimatedScalar = Field(
        default=AnimatedScalar(1.0),
        description="Element opacity (0.0 = invisible, 1.0 = fully visible), or animated via keyframes.",
    )
    scale: AnimatedScalar = Field(
        default=AnimatedScalar(1.0),
        description="Scale factor (1.0 = original size), or animated via keyframes.",
    )
    angle: AnimatedScalar = Field(
        default=AnimatedScalar(0.0),
        description="Rotation in degrees (positive = clockwise), or animated via keyframes.",
    )

    @model_validator(mode="after")
    def _validate_size(self) -> SlideElement:
        """Validate that at least one size dimension is non-auto."""
        if self.width.is_auto and self.height.is_auto:
            raise ValueError('at least one size dimension must be non-auto; got both as "auto"')
        if self.width.is_static_numeric and self.width.static_value <= 0:
            raise ValueError(f"numeric width must be > 0, got {self.width.static_value}")
        if self.height.is_static_numeric and self.height.static_value <= 0:
            raise ValueError(f"numeric height must be > 0, got {self.height.static_value}")
        return self


# ==================================================================================================
#  Concrete element types
# ==================================================================================================


class ImageElement(SlideElement, frozen=True):
    """An element backed by an external image file (PNG, JPEG, SVG, etc.)."""

    image: Path = Field(
        description="Path to the image file, relative to the slide source file.",
    )
    object_fit: Literal["cover", "contain", "fill"] | None = Field(
        default=None,
        description=(
            "How the image fills its box. Required when both size dimensions are numeric "
            '(or animated), forbidden when one is "auto". '
            '"cover" fills the box (may crop), "contain" fits inside (may letterbox), '
            '"fill" stretches to fill exactly.'
        ),
    )

    @model_validator(mode="after")
    def _validate_object_fit(self) -> ImageElement:
        """Validate object_fit rules based on size dimensions."""
        w_is_auto = self.width.is_auto
        h_is_auto = self.height.is_auto
        both_non_auto = not w_is_auto and not h_is_auto
        if both_non_auto and self.object_fit is None:
            raise ValueError("object_fit is required when both size dimensions are numeric or animated")
        if (w_is_auto or h_is_auto) and self.object_fit is not None:
            raise ValueError('object_fit is forbidden when a size dimension is "auto"')
        return self


class ImageSequenceElement(SlideElement, frozen=True):
    """A scroll-driven filmstrip: an ordered sequence of images that crossfade as the user scrolls.

    Each image is shown in turn on an equidistant scroll grid. Repeating the same
    path consecutively in ``image_sequence`` extends its visible duration by one
    slot per repeat. An empty string (``""``) in any slot reserves that slot in
    the timeline but renders nothing — neighbouring frames fade out before and
    in after the blank, so the slot is a clean "no image visible" period.
    Optional ``fade_in`` / ``fade_out`` add leading / trailing opacity ramps
    independent of the inter-frame crossfade timing.
    """

    image_sequence: list[Path | None] = Field(
        description=(
            "Ordered image paths, relative to the slide source file. Min 2 entries. "
            "An empty string (\"\") reserves a blank slot in the timeline — neighbouring frames "
            "crossfade out before and in after it. "
            "Repeating the same path consecutively extends its visible duration by one slot per repeat."
        ),
    )

    @field_validator("image_sequence", mode="before")
    @classmethod
    def _empty_string_means_blank(cls, value: object) -> object:
        """Normalise ``""`` entries to ``None`` so blank slots are represented uniformly."""
        if isinstance(value, list):
            return [None if item == "" else item for item in value]
        return value
    frame_distance: float = Field(
        description=(
            "Scroll distance between the start of consecutive frames' hold periods. "
            "Must be > hold (so the crossfade duration frame_distance - hold is > 0)."
        ),
    )
    hold: float = Field(
        description="Scroll distance each frame stays at full opacity. Must be > 0.",
    )
    scroll_offset: float = Field(
        default=0,
        description="Scroll position where frame 0's hold period begins.",
    )
    fade_in: float = Field(
        default=0,
        description=(
            "Scroll distance of the leading fade-in ramp. "
            "0 (default) = frame 0 starts at full opacity (hard cut). "
            "> 0 = frame 0 ramps from opacity 0 to 1 over [scroll_offset - fade_in, scroll_offset]."
        ),
    )
    fade_out: float = Field(
        default=0,
        description=(
            "Scroll distance of the trailing fade-out ramp. "
            "0 (default) = last frame stays at full opacity past the end of its hold (hard cut). "
            "> 0 = last frame ramps from opacity 1 to 0 over fade_out scroll units after its hold ends."
        ),
    )
    object_fit: Literal["cover", "contain", "fill"] | None = Field(
        default=None,
        description=(
            "How each image fills its box. Required when both size dimensions are numeric "
            '(or animated), forbidden when one is "auto". Same semantics as ImageElement.object_fit.'
        ),
    )

    @model_validator(mode="after")
    def _validate_image_sequence(self) -> ImageSequenceElement:
        """Validate image-sequence-specific timing and asset fields."""
        if len(self.image_sequence) < 2:
            raise ValueError(f"image_sequence must contain at least 2 entries, got {len(self.image_sequence)}")
        if self.hold <= 0:
            raise ValueError(f"hold must be > 0, got {self.hold}")
        if self.frame_distance <= self.hold:
            raise ValueError(
                f"frame_distance ({self.frame_distance}) must be > hold ({self.hold}) to allow a non-zero crossfade"
            )
        if self.fade_in < 0:
            raise ValueError(f"fade_in must be >= 0, got {self.fade_in}")
        if self.fade_out < 0:
            raise ValueError(f"fade_out must be >= 0, got {self.fade_out}")
        return self

    @model_validator(mode="after")
    def _validate_object_fit(self) -> ImageSequenceElement:
        """Validate object_fit rules based on size dimensions (mirrors ImageElement)."""
        w_is_auto = self.width.is_auto
        h_is_auto = self.height.is_auto
        both_non_auto = not w_is_auto and not h_is_auto
        if both_non_auto and self.object_fit is None:
            raise ValueError("object_fit is required when both size dimensions are numeric or animated")
        if (w_is_auto or h_is_auto) and self.object_fit is not None:
            raise ValueError('object_fit is forbidden when a size dimension is "auto"')
        return self


class HtmlElement(SlideElement, frozen=True):
    """An element with inline HTML content."""

    html: str = Field(description="Raw HTML content, inserted verbatim into the slide.")


class MarkdownElement(SlideElement, frozen=True):
    """An element with markdown content, rendered to HTML at build time."""

    markdown: str = Field(description="Markdown content, rendered to HTML at build time.")
    color: str = Field(
        default="#808080",
        description="CSS color value for the rendered text.",
    )
    text_align: Literal["left", "center", "right"] = Field(
        default="left",
        description="Horizontal text alignment within the element box.",
    )


class MermaidElement(SlideElement, frozen=True):
    """An element with mermaid diagram source, rendered client-side."""

    mermaid: str = Field(description="Mermaid diagram source code, rendered client-side by mermaid.js.")
