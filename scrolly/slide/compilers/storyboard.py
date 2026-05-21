"""Compile StoryboardIR -> ScrollimationIR.

Each scene becomes a group of elements with auto-generated opacity
keyframes implementing a crossfade.  Outgoing scenes fade out while
incoming scenes fade in over the same transition zone; the background
(always at 100% opacity) fills any midpoint transparency.
"""

from __future__ import annotations

from scrolly.slide.ir import (
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
)
from scrolly.slide.ir._framework.animated_values import AnimatedScalar, ScalarKeyframes
from scrolly.slide.ir.scrollimation import AnyElement, ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR
from scrolly.slide.processor import Compiler as CompilerBase


class StoryboardCompiler(CompilerBase):
    """Compiler: StoryboardIR -> ScrollimationIR."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        """Return True if this compiler handles the given IR type."""
        return isinstance(ir, StoryboardIR)

    def compile(self, ir: SlideIR) -> ScrollimationIR:
        """Compile a StoryboardIR into a ScrollimationIR."""
        assert isinstance(ir, StoryboardIR)
        return compile_storyboard(ir)


def compile_storyboard(ir: StoryboardIR) -> ScrollimationIR:
    """Convert a storyboard IR into a scrollimation IR."""
    D = ir.scene_distance
    H = ir.hold
    n = len(ir.scenes)
    scroll_range = D * (n - 1)
    snap_positions = tuple(i * D for i in range(n))

    elements: list[AnyElement] = []

    for el in ir.background:
        elements.append(el)

    for i, scene in enumerate(ir.scenes):
        opacity_kfs = _scene_opacity_keyframes(i, n, D, H)
        init_opacity = 1.0 if i == 0 else 0.0

        for el in scene.elements:
            elements.append(_set_opacity(el, init_opacity, opacity_kfs))

    return ScrollimationIR(
        title=ir.title,
        scroll_range=scroll_range,
        snap_positions=snap_positions,
        elements=elements,
    )


def _scene_opacity_keyframes(scene_idx: int, num_scenes: int, D: int, H: int) -> list[tuple[float, float]]:
    """Build opacity keyframes for a scene's fade-in and fade-out."""
    kfs: list[tuple[float, float]] = []
    is_first = scene_idx == 0
    is_last = scene_idx == num_scenes - 1

    if not is_first:
        fade_in_start = (scene_idx - 1) * D + H
        fade_in_end = scene_idx * D - H
        kfs.append((fade_in_start, 0.0))
        kfs.append((fade_in_end, 1.0))

    if not is_last:
        fade_out_start = scene_idx * D + H
        fade_out_end = (scene_idx + 1) * D - H
        if kfs and kfs[-1][0] == fade_out_start and kfs[-1][1] == 1.0:
            pass
        else:
            kfs.append((fade_out_start, 1.0))
        kfs.append((fade_out_end, 0.0))

    return kfs


def _set_opacity(
    el: ImageElement | ImageSequenceElement | HtmlElement | IframeElement | MarkdownElement | MermaidElement,
    init_opacity: float,
    opacity_kfs: list[tuple[float, float]],
) -> AnyElement:
    """Return a copy of the element with opacity set from the crossfade schedule."""
    if not opacity_kfs:
        opacity = AnimatedScalar(init_opacity)
    else:
        opacity = AnimatedScalar(ScalarKeyframes(keyframes=opacity_kfs))
    return el.model_copy(update={"opacity": opacity})
