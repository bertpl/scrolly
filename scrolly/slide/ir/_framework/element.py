"""Shared slide-element models.

``SlideElement`` is the base for all positioned visual units within a
slide.  Concrete types (``ImageElement``, ``ImageSequenceElement``,
``HtmlElement``, ``IframeElement``, ``MarkdownElement``,
``MermaidElement``) carry content-specific fields.

Each animatable property accepts either a static value or a keyframe
animation definition (piecewise linear, held constant beyond extremes).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from scrolly.errors import SlideSourceError
from scrolly.slide.element_ir import ElementIR, PrimitiveElement
from scrolly.slide.ir._framework.animated_values import (
    AnimatedScalar,
    AnimatedSizeDim,
    AnimatedVec2,
)


# ==================================================================================================
#  Shared field builders
# ==================================================================================================
def _content_file_field(inline_key: str, example: str) -> Path | None:
    """Build the declaration for a ``*_file`` content field.

    These fields exist on the models for schema truthfulness only: the
    source may author content via ``<inline_key>_file`` instead of
    ``<inline_key>``, but ``_resolve_file_fields`` inlines and pops the
    ``*_file`` key before validation, so validated instances always carry
    the inline field and never a populated ``*_file`` field.
    """
    return Field(
        default=None,
        description=(
            f"Path to a file whose text becomes `{inline_key}`, relative to the slide "
            f'source file (e.g. `"{example}"`). Read and inlined at parse time. '
            f"Author exactly one of `{inline_key}` / `{inline_key}_file`; validated "
            f"slides always carry `{inline_key}`."
        ),
    )


# ==================================================================================================
#  Shared validators
# ==================================================================================================
def _validate_object_fit_rules(
    width: AnimatedSizeDim,
    height: AnimatedSizeDim,
    object_fit: Literal["cover", "contain", "fill"] | None,
) -> None:
    """Enforce the object_fit / size-dimension rules shared by image element types.

    ``object_fit`` is required when both dimensions are numeric (or animated)
    and forbidden when either is ``"auto"``.

    Raises:
        SlideSourceError: ``E303`` if both dimensions are non-auto and
            ``object_fit`` is missing; ``E304`` if a dimension is ``"auto"``
            and ``object_fit`` is set.
    """
    w_is_auto = width.is_auto
    h_is_auto = height.is_auto
    both_non_auto = not w_is_auto and not h_is_auto
    if both_non_auto and object_fit is None:
        raise SlideSourceError(
            code="E303",
            message="object_fit is required when both size dimensions are numeric or animated",
        )
    if (w_is_auto or h_is_auto) and object_fit is not None:
        raise SlideSourceError(
            code="E304",
            message='object_fit is forbidden when a size dimension is "auto"',
        )


# ==================================================================================================
#  SlideElement base
# ==================================================================================================
class SlideElement(ElementIR, frozen=True):
    """Base for all positioned visual units within a slide."""

    SOURCE_KEY: ClassVar[str]
    DESCRIPTION: ClassVar[str]

    name: str | None = Field(
        default=None,
        description="Optional human-readable label. Used in error messages only, not for rendering.",
    )
    position: AnimatedVec2 = Field(
        default=AnimatedVec2((5.0, 5.0)),
        description=(
            "Element position as [x%, y%] of the slide viewport, or animated via keyframes. "
            "Default [5, 5] — a 5%-inset top-left. [0, 0] = exact top-left, "
            "[100, 100] = bottom-right corner. The anchor point of the element is placed "
            "at this position."
        ),
    )
    width: AnimatedSizeDim = Field(
        default=AnimatedSizeDim(90.0),
        description=(
            'Element width as % of slide viewport, "auto", or animated via keyframes. '
            "Default 90, pairing with position [5, 5] for a centered 90%-wide column. "
            'Use "auto" to preserve aspect ratio (images) or size to content (text).'
        ),
    )
    height: AnimatedSizeDim = Field(
        default=AnimatedSizeDim("auto"),
        description=(
            'Element height as % of slide viewport, "auto", or animated via keyframes. '
            'Default "auto" — content-driven height. Set to a number to fix the height, '
            "or animate via keyframes."
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
            raise SlideSourceError(
                code="E301",
                message='at least one size dimension must be non-auto; got both as "auto"',
            )
        if self.width.is_static_numeric and self.width.static_value <= 0:
            raise SlideSourceError(code="E302", message=f"numeric width must be > 0, got {self.width.static_value}")
        if self.height.is_static_numeric and self.height.static_value <= 0:
            raise SlideSourceError(code="E302", message=f"numeric height must be > 0, got {self.height.static_value}")
        return self

    @classmethod
    def source_schema(cls) -> dict:
        """JSON-serializable description of this element type's source schema."""
        return cls.model_json_schema()


# ==================================================================================================
#  Concrete element types
# ==================================================================================================
class ImageElement(SlideElement, PrimitiveElement, frozen=True):
    """An element backed by an external image file (PNG, JPEG, SVG, etc.)."""

    SOURCE_KEY: ClassVar[str] = "image"
    DESCRIPTION: ClassVar[str] = "Image from an external file (PNG, JPEG, SVG, …)."

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
        _validate_object_fit_rules(self.width, self.height, self.object_fit)
        return self


class ImageSequenceElement(SlideElement, PrimitiveElement, frozen=True):
    """A scroll-driven filmstrip: an ordered sequence of images that crossfade as the user scrolls.

    Each image is shown in turn on an equidistant scroll grid. Repeating the same
    path consecutively in ``image_sequence`` extends its visible duration by one
    slot per repeat. An empty string (``""``) in any slot reserves that slot in
    the timeline but renders nothing — neighboring frames fade out before and
    in after the blank, so the slot is a clean "no image visible" period.
    Optional ``fade_in`` / ``fade_out`` add leading / trailing opacity ramps
    independent of the inter-frame crossfade timing.
    """

    SOURCE_KEY: ClassVar[str] = "image_sequence"
    DESCRIPTION: ClassVar[str] = "Scroll-driven filmstrip of crossfading images."

    image_sequence: list[Path | None] = Field(
        description=(
            "Ordered image paths, relative to the slide source file. Min 2 entries. "
            'An empty string ("") reserves a blank slot in the timeline — neighboring frames '
            "crossfade out before and in after it. "
            "Repeating the same path consecutively extends its visible duration by one slot per repeat."
        ),
    )

    @field_validator("image_sequence", mode="before")
    @classmethod
    def _empty_string_means_blank(cls, value: object) -> object:
        """Normalize ``""`` entries to ``None`` so blank slots are represented uniformly."""
        if isinstance(value, list):
            return [None if item == "" else item for item in value]
        return value

    frame_distance: float = Field(
        description=(
            "Scroll distance between consecutive frames' snap positions "
            "(P_i = scroll_offset + i * frame_distance). Must be > 0."
        ),
    )
    hold_fraction: float = Field(
        default=0.2,
        description=(
            "Fraction of frame_distance each frame stays at full opacity, centered "
            "on its snap position. Must be in [0, 1) so the crossfade "
            "(frame_distance * (1 - hold_fraction)) stays positive. Default 0.2."
        ),
    )
    scroll_offset: float = Field(
        default=0,
        description="Scroll position of frame 0's snap (P_0); frame i snaps at scroll_offset + i * frame_distance.",
    )
    fade_in: float = Field(
        default=0,
        description=(
            "Scroll distance of the leading fade-in ramp before frame 0's snap. "
            "0 (default) = frame 0 starts at full opacity (hard cut). "
            "> 0 = the timeline begins (opacity 0) at scroll_offset - fade_in."
        ),
    )
    fade_out: float = Field(
        default=0,
        description=(
            "Scroll distance of the trailing fade-out ramp after the last frame's snap. "
            "0 (default) = the last frame stays at full opacity past its snap (hard cut). "
            "> 0 = the timeline ends (opacity 0) at last_snap + fade_out."
        ),
    )
    object_fit: Literal["cover", "contain", "fill"] | None = Field(
        default=None,
        description=(
            "How each image fills its box. Required when both size dimensions are numeric "
            '(or animated), forbidden when one is "auto". Same semantics as ImageElement.object_fit.'
        ),
    )
    compositing: Literal["blend", "overlay", "incremental"] = Field(
        default="blend",
        description=(
            "How successive frames composite on top of one another as the sequence advances. "
            '"blend" (default): symmetric crossfade — each frame ramps 0→1 in and 1→0 out, '
            "leaving a brief mid-transition window where both frames are partially transparent and the "
            "slide background may show through. Use for frames that have their own per-pixel "
            "transparency and should fully replace each other. "
            '"overlay": each frame ramps 0→1 in, then holds at 1 until the next frame has fully faded in, '
            "then instantly drops to 0. The next frame fully covers it before it disappears, so the "
            "slide background never shows through. Use for opaque image sequences (photos, screenshots). "
            '"incremental": each frame ramps 0→1 in, then holds at 1 until the sequence ends — all '
            "revealed frames stay layered and the rendered image is the alpha-composite of every "
            "frame to date. Use for build-up sequences where each frame adds a new element on a "
            "transparent background (a flowchart growing, an equation revealed line by line, a map "
            "gaining markers)."
        ),
    )

    @model_validator(mode="after")
    def _validate_image_sequence(self) -> ImageSequenceElement:
        """Validate image-sequence-specific timing and asset fields."""
        if len(self.image_sequence) < 2:
            raise SlideSourceError(
                code="E305",
                message=f"image_sequence must contain at least 2 entries, got {len(self.image_sequence)}",
            )
        if self.frame_distance <= 0:
            raise SlideSourceError(code="E306", message=f"frame_distance must be > 0, got {self.frame_distance}")
        if not 0 <= self.hold_fraction < 1:
            raise SlideSourceError(
                code="E306",
                message=f"hold_fraction must be in [0, 1), got {self.hold_fraction}",
            )
        if self.fade_in < 0:
            raise SlideSourceError(code="E306", message=f"fade_in must be >= 0, got {self.fade_in}")
        if self.fade_out < 0:
            raise SlideSourceError(code="E306", message=f"fade_out must be >= 0, got {self.fade_out}")
        return self

    @model_validator(mode="after")
    def _validate_object_fit(self) -> ImageSequenceElement:
        """Validate object_fit rules based on size dimensions (mirrors ImageElement)."""
        _validate_object_fit_rules(self.width, self.height, self.object_fit)
        return self

    def snap_positions(self) -> list[float]:
        """Return the per-slot snap positions on the frame grid.

        Each slot ``i`` in ``image_sequence`` snaps at
        ``scroll_offset + i * frame_distance`` — the center of that frame's
        symmetric hold and the natural settle point where the frame is most
        clearly on display. Repeated frames and blank slots (``None`` entries)
        each contribute one snap per slot.

        Returns:
            One float per slot in ``image_sequence``, in order.
        """
        return [self.scroll_offset + i * self.frame_distance for i in range(len(self.image_sequence))]

    def timeline_start(self) -> float:
        """Return the scroll position where the sequence begins (frame 0 at opacity 0)."""
        return self.scroll_offset - self.fade_in

    def timeline_end(self) -> float:
        """Return the scroll position where the sequence ends (last frame fully faded out).

        Equals ``last_snap + fade_out``. Size the slide's ``scroll_range`` to at
        least this so the trailing fade completes within range.
        """
        n = len(self.image_sequence)
        return self.scroll_offset + (n - 1) * self.frame_distance + self.fade_out


class HtmlElement(SlideElement, PrimitiveElement, frozen=True):
    """An element with inline HTML content."""

    SOURCE_KEY: ClassVar[str] = "html"
    DESCRIPTION: ClassVar[str] = "Inline raw HTML content."

    html: str = Field(
        description=(
            "Raw HTML content, inserted verbatim into the slide. "
            'Authored inline or via `html_file: "path/to/snippet.html"` '
            "(the file form reads the file at parse time)."
        ),
    )
    html_file: Path | None = _content_file_field("html", "card.html")


class IframeElement(SlideElement, PrimitiveElement, frozen=True):
    """An element backed by a sandboxed iframe rendering a self-contained HTML document.

    The embedded HTML is inlined as the iframe's ``srcdoc`` attribute, giving
    the content its own browsing context — independent scrollbar, isolated
    CSS scope, and isolated JavaScript scope. ``sandbox="allow-scripts"`` is
    set by default, so embedded scripts run in a unique origin and cannot
    reach the parent slide.

    Because ``srcdoc`` documents have base URL ``about:srcdoc``, relative
    references inside the embedded HTML do not resolve; authors inline
    images as ``data:`` URIs and place CSS / JS inline.

    Optional ``border_*`` and ``shadow_*`` fields frame the iframe wrapper.
    When either decoration is active, the wrapper switches to
    ``box-sizing: border-box`` so the declared ``width`` / ``height`` remain
    the outer footprint including the border.
    """

    SOURCE_KEY: ClassVar[str] = "iframe"
    DESCRIPTION: ClassVar[str] = "Sandboxed iframe embedding a self-contained HTML document."

    iframe_html: str = Field(
        description=(
            "Full HTML document inlined as the iframe's `srcdoc` attribute. "
            'Authored inline or via `iframe_html_file: "path/to/page.html"` '
            "(the file form reads the file at parse time). Must be self-"
            "contained — relative references inside the document do not "
            "resolve under `about:srcdoc`."
        ),
    )
    iframe_html_file: Path | None = _content_file_field("iframe_html", "page.html")
    border_width: int = Field(
        default=0,
        description=(
            "Border width in CSS pixels around the iframe wrapper. "
            "0 (default) = no border. When non-zero, the wrapper uses "
            "`box-sizing: border-box` so the declared `width` / `height` "
            "are the outer footprint including the border."
        ),
    )
    border_color: str = Field(
        default="#000000",
        description="CSS color of the border. Only rendered when `border_width > 0`.",
    )
    shadow_size: int = Field(
        default=0,
        description=(
            "Soft-glow shadow size in CSS pixels — interpreted as the "
            "`box-shadow` blur radius with zero offset and zero spread. "
            "0 (default) = no shadow."
        ),
    )
    shadow_color: str = Field(
        default="#000000",
        description="CSS color of the shadow. Only rendered when `shadow_size > 0`.",
    )

    @model_validator(mode="after")
    def _validate_decorations(self) -> IframeElement:
        """Validate non-negative border and shadow sizes."""
        if self.border_width < 0:
            raise SlideSourceError(code="E307", message=f"border_width must be >= 0, got {self.border_width}")
        if self.shadow_size < 0:
            raise SlideSourceError(code="E307", message=f"shadow_size must be >= 0, got {self.shadow_size}")
        return self


class MarkdownElement(SlideElement, PrimitiveElement, frozen=True):
    """An element with markdown content, rendered to HTML at build time."""

    SOURCE_KEY: ClassVar[str] = "markdown"
    DESCRIPTION: ClassVar[str] = "Markdown content, rendered to HTML at build time."

    markdown: str = Field(
        description=(
            "Markdown content, rendered to HTML at build time. "
            'Authored inline or via `markdown_file: "path/to/content.md"` '
            "(the file form reads the file at parse time)."
        ),
    )
    markdown_file: Path | None = _content_file_field("markdown", "content.md")
    color: str = Field(
        default="inherit",
        description="CSS color value for the rendered text. Default 'inherit' picks up the slide-level body color.",
    )
    text_align: Literal["left", "center", "right"] = Field(
        default="left",
        description="Horizontal text alignment within the element box.",
    )


class MermaidElement(SlideElement, PrimitiveElement, frozen=True):
    """An element with mermaid diagram source, rendered client-side."""

    SOURCE_KEY: ClassVar[str] = "mermaid"
    DESCRIPTION: ClassVar[str] = "Mermaid diagram, rendered client-side."

    mermaid: str = Field(
        description=(
            "Mermaid diagram source code, rendered client-side by mermaid.js. "
            'Authored inline or via `mermaid_file: "path/to/diagram.mmd"` '
            "(the file form reads the file at parse time)."
        ),
    )
    mermaid_file: Path | None = _content_file_field("mermaid", "diagram.mmd")


# ==================================================================================================
#  Element source registry
# ==================================================================================================
_ELEMENT_TYPES: tuple[type[SlideElement], ...] = (
    ImageElement,
    ImageSequenceElement,
    HtmlElement,
    IframeElement,
    MarkdownElement,
    MermaidElement,
)


def element_source_types() -> dict[str, type[SlideElement]]:
    """Return a mapping of source key to element source model, for every element type.

    Keyed by each element's author-facing ``SOURCE_KEY`` (e.g. ``"image_sequence"``)
    and ordered by key for stable output.
    """
    return {cls.SOURCE_KEY: cls for cls in sorted(_ELEMENT_TYPES, key=lambda c: c.SOURCE_KEY)}
