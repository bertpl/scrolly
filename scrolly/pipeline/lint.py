"""Optional lint checks for suspicious-but-valid patterns.

The lint system is an independent post-parse check. Parsers, compilers,
and renderers never see ``--strict`` — the CLI calls lint after
successful validation and reports diagnostics to stderr.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from scrolly.deck.model import Deck
from scrolly.slide.ir._framework.animated_values import AnimatedScalar, AnimatedVec2
from scrolly.slide.ir._framework.element import ImageSequenceElement
from scrolly.slide.ir.slide import SlideIR
from scrolly.slide.registry import get_ir_class_for_path


@dataclass(frozen=True)
class Diagnostic:
    """A single lint finding."""

    level: Literal["warning", "info"]
    message: str
    location: str


def lint_deck(deck: Deck) -> list[Diagnostic]:
    """Run all lint checks over a parsed deck."""
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_out_of_range_keyframes(deck))
    return diagnostics


# --------------------------------------------------------------------------
#  Lint rules
# --------------------------------------------------------------------------
def _check_out_of_range_keyframes(deck: Deck) -> list[Diagnostic]:
    """Warn on keyframe positions outside [0, scroll_range].

    Slides with ``scroll_range="auto"`` (content-driven height) are
    skipped: the upper bound is not statically known until the slide is
    rendered, so out-of-range checks against it can't be evaluated at
    lint time.
    """
    diagnostics: list[Diagnostic] = []

    for slide in deck.slides:
        ir = _parse_slide_ir(slide.source)
        if not isinstance(ir, SlideIR):
            continue

        if not isinstance(ir.scroll_range, (int, float)):
            continue

        scroll_range = ir.scroll_range
        for i, el in enumerate(ir.elements):
            label = f"'{el.name}'" if el.name else f"element [{i}]"
            location = f"slide '{ir.title}', {label}"
            _check_scalar_field(el.opacity, "opacity", location, scroll_range, diagnostics)
            _check_scalar_field(el.scale, "scale", location, scroll_range, diagnostics)
            _check_scalar_field(el.angle, "angle", location, scroll_range, diagnostics)
            _check_vec2_field(el.position, "position", location, scroll_range, diagnostics)
            _check_vec2_field(el.anchor, "anchor", location, scroll_range, diagnostics)
            _check_size_field(el.width, "width", location, scroll_range, diagnostics)
            _check_size_field(el.height, "height", location, scroll_range, diagnostics)
            if isinstance(el, ImageSequenceElement):
                _check_image_sequence(el, location, scroll_range, diagnostics)

    return diagnostics


def _check_scalar_field(
    field: AnimatedScalar,
    field_name: str,
    location: str,
    scroll_range: float,
    diagnostics: list[Diagnostic],
) -> None:
    """Check an AnimatedScalar field for out-of-range keyframes."""
    if not field.is_animated:
        return
    for at, _ in field.keyframes:
        if at < 0 or at > scroll_range:
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    message=f"keyframe at={at} is outside [0, {scroll_range}]",
                    location=f"{location}, field '{field_name}'",
                )
            )
            break


def _check_vec2_field(
    field: AnimatedVec2,
    field_name: str,
    location: str,
    scroll_range: float,
    diagnostics: list[Diagnostic],
) -> None:
    """Check an AnimatedVec2 field for out-of-range keyframes."""
    if not field.is_animated:
        return
    for at, _ in field.keyframes:
        if at < 0 or at > scroll_range:
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    message=f"keyframe at={at} is outside [0, {scroll_range}]",
                    location=f"{location}, field '{field_name}'",
                )
            )
            break


def _check_size_field(
    field,
    field_name: str,
    location: str,
    scroll_range: float,
    diagnostics: list[Diagnostic],
) -> None:
    """Check an AnimatedSizeDim field for out-of-range keyframes."""
    if not field.is_animated:
        return
    for at, _ in field.keyframes:
        if at < 0 or at > scroll_range:
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    message=f"keyframe at={at} is outside [0, {scroll_range}]",
                    location=f"{location}, field '{field_name}'",
                )
            )
            break


def _check_image_sequence(
    el: ImageSequenceElement,
    location: str,
    scroll_range: float,
    diagnostics: list[Diagnostic],
) -> None:
    """Check the auto-generated opacity keyframes for an image sequence element."""
    n = len(el.image_sequence)
    timeline_start = el.scroll_offset - el.fade_in
    timeline_end = el.scroll_offset + (n - 1) * el.frame_distance + el.hold + el.fade_out
    if timeline_start < 0:
        diagnostics.append(
            Diagnostic(
                level="warning",
                message=f"image_sequence timeline starts at {timeline_start}, before 0",
                location=f"{location}, field 'image_sequence'",
            )
        )
    if timeline_end > scroll_range:
        diagnostics.append(
            Diagnostic(
                level="warning",
                message=f"image_sequence timeline ends at {timeline_end}, past scroll_range ({scroll_range})",
                location=f"{location}, field 'image_sequence'",
            )
        )


def _parse_slide_ir(source: Path):
    """Parse a slide source file into its IR."""
    ir_cls = get_ir_class_for_path(source)
    return ir_cls.from_file(source)
