"""``SlideIR`` — the single slide IR model.

A slide is a list of positioned elements, each with animatable
properties (static values or piecewise-linear keyframes). The renderer
runs each element through the element-IR registry to produce the
contributed HTML, CSS, assets, and snap positions; the assembled
output goes into the deck-level page.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, Field, model_validator

from scrolly.errors import SlideSourceError
from scrolly.slide.ir._framework.element import AnyElement, ContainerElement
from scrolly.slide.ir._framework.utils import parse_json5_ir, resolve_asset_paths


def _effective_element_names(elements: list, prefix: str) -> list[str]:
    """Collect every named element's effective (dot-prefixed) name, recursively.

    A named container prefixes its children's names (``header.title``);
    an unnamed container passes the enclosing prefix through, so its
    children compete in the surrounding name scope.
    """
    names: list[str] = []
    for el in elements:
        effective = f"{prefix}{el.name}" if el.name is not None else None
        if effective is not None:
            names.append(effective)
        if isinstance(el, ContainerElement):
            child_prefix = f"{effective}." if effective is not None else prefix
            names.extend(_effective_element_names(el.container, child_prefix))
    return names


class SlideIR(BaseModel, frozen=True):
    """The single slide IR. Loaded from ``.slide.json`` source files.

    Substrate fields:

    - ``title`` (required) — navigation label.
    - ``scroll_range`` — total scrollable distance in abstract scroll
      units, or ``"auto"`` (default) for content-driven height.
    - ``font_scale`` (default ``1.0``) — per-slide font multiplier.
    - ``initial_scroll_position`` (default ``0``).
    - ``scroll_speed`` (default ``1.0``), ``easing`` (default
      ``"linear"``), ``snap_positions`` (default empty),
      ``reverse`` (default ``False``).
    - ``elements`` (required, non-empty) — the positioned content.

    The ``SUFFIX`` and ``DESCRIPTION`` class attributes plus the
    registry-driven ``from_file`` factory mean ``SlideIR`` participates
    in the same one-entry dispatch mechanism the multi-type design used,
    so registering a second slide type later (if ever needed) is a
    registration rather than a re-architecture.
    """

    SUFFIX: ClassVar[str] = ".slide.json"
    DESCRIPTION: ClassVar[str] = "Slide"

    title: str = Field(description="Human-readable slide title, shown in navigation UI.")
    scroll_range: float | Literal["auto"] = Field(
        default="auto",
        description=(
            "Total scrollable distance in abstract scroll units, or 'auto' (default) "
            "for content-driven height where the slide grows to fit its rendered "
            "content. Keyframe 'at' values and snap positions reference this range "
            "(when numeric). A slide with scroll_range=0 has no scroll behavior."
        ),
    )
    initial_scroll_position: float = Field(
        default=0,
        description="Scroll position the slide starts at on first visit. Must be within [0, scroll_range].",
    )
    font_scale: float = Field(
        default=1.0,
        description="Font size multiplier for the slide. 1.0 = inherit. Must be > 0.",
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
            "Reverses the scrollbar direction so the slide reads bottom-up. "
            "When false (default), scroll value 0 places the scrollbar thumb "
            "at the TOP of the track and the user scrolls DOWN to advance "
            "through the slide — the conventional direction. When true, "
            "scroll value 0 places the thumb at the BOTTOM of the track, the "
            "thumb rises as the scroll value increases, and the user scrolls "
            "UP to advance. "
            "Authoring values are UNCHANGED in either mode: keyframe `at` "
            "values, `snap_positions`, and `initial_scroll_position` are "
            "still interpreted in the usual [0, scroll_range] range, with "
            "`at=0` rendering the slide's initial state regardless of "
            "`reverse`. Only the scrollbar's value-to-thumb-position mapping "
            "and the sign of user-input deltas (wheel, shift+arrows, "
            "chevrons, drag) are flipped at render time. "
            "Intended for naturally bottom-up content (e.g. git-tree "
            "visualizations) so authors can keep keyframes and image lists "
            "in their natural ascending order rather than writing them "
            "in reverse."
        ),
    )
    elements: list[AnyElement] = Field(
        description="The elements in this slide, rendered in array order (first = bottom, last = top).",
    )

    @property
    def slide_type(self) -> str:
        """CSS-safe type name derived from ``SUFFIX``."""
        return self.SUFFIX.lstrip(".").replace(".", "-")

    @classmethod
    def source_schema(cls) -> dict:
        """JSON-serializable description of the source file format."""
        return cls.model_json_schema()

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        """Parse a ``.slide.json`` source file."""
        ir = parse_json5_ir(source_path, cls, "slide")
        resolved = resolve_asset_paths(ir.elements, source_path.parent)
        if resolved != list(ir.elements):
            ir = ir.model_copy(update={"elements": resolved})
        return ir

    @model_validator(mode="after")
    def _validate_slide(self) -> SlideIR:
        """Validate slide-level constraints.

        Raises ``SlideSourceError`` rather than ``ValueError`` so the
        catalog code propagates through Pydantic intact — Pydantic only
        wraps ``ValueError`` / ``AssertionError`` / ``PydanticCustomError``.
        """
        if self.font_scale <= 0:
            raise SlideSourceError(code="E202", message=f"font_scale must be > 0, got {self.font_scale}")
        if self.initial_scroll_position < 0:
            raise SlideSourceError(
                code="E203",
                message=f"initial_scroll_position must be >= 0, got {self.initial_scroll_position}",
            )
        if not self.elements:
            raise SlideSourceError(code="E201", message="at least one element is required")

        if isinstance(self.scroll_range, (int, float)):
            if self.scroll_range < 0:
                raise SlideSourceError(
                    code="E204",
                    message=f"scroll_range must be >= 0 or 'auto', got {self.scroll_range}",
                )
            if self.initial_scroll_position > self.scroll_range:
                raise SlideSourceError(
                    code="E205",
                    message=(
                        f"initial_scroll_position ({self.initial_scroll_position}) "
                        f"must be <= scroll_range ({self.scroll_range})"
                    ),
                )
            for pos in self.snap_positions:
                if pos < 0 or pos > self.scroll_range:
                    raise SlideSourceError(
                        code="E206",
                        message=f"snap_positions value {pos} is outside [0, {self.scroll_range}]",
                    )
        else:
            for pos in self.snap_positions:
                if pos < 0:
                    raise SlideSourceError(code="E206", message=f"snap_positions value {pos} must be >= 0")

        seen_names: set[str] = set()
        for name in _effective_element_names(self.elements, prefix=""):
            if name in seen_names:
                raise SlideSourceError(
                    code="E207",
                    message=(
                        f"duplicate element name: {name!r}. Names are checked after container "
                        f"expansion — give instantiating elements distinct `name`s to prefix "
                        f"their children (e.g. `header.title`)."
                    ),
                )
            seen_names.add(name)

        return self
