"""Compile StoryboardIR → ScrollimationIR.

Each scene becomes a group of animated elements with auto-generated
opacity keyframes implementing a crossfade.  Outgoing scenes fade out
while incoming scenes fade in over the same transition zone; the
background (always at 100% opacity) fills any midpoint transparency.
"""

from __future__ import annotations

from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    ImageElement,
    InitialState,
    Keyframe,
    MarkdownElement,
    SlideIR,
)
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR
from scrolly.slide.processor import Compiler as CompilerBase


class StoryboardCompiler(CompilerBase):
    """Compiler: StoryboardIR → ScrollimationIR."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, StoryboardIR)

    def compile(self, ir: SlideIR) -> ScrollimationIR:
        assert isinstance(ir, StoryboardIR)
        return compile_storyboard(ir)


def compile_storyboard(ir: StoryboardIR) -> ScrollimationIR:
    """Convert a storyboard IR into a scrollimation IR."""
    D = ir.scene_distance
    H = ir.hold
    n = len(ir.scenes)
    scroll_range = D * (n - 1)
    snap_positions = tuple(i * D for i in range(n))

    anims: list[ElementAnimation] = []

    for el in ir.background:
        anims.append(_wrap_element(el, initial_opacity=1.0, keyframes=[]))

    for i, scene in enumerate(ir.scenes):
        kfs = _scene_keyframes(i, n, D, H)
        init_opacity = 1.0 if i == 0 else 0.0

        for el in scene.elements:
            anims.append(_wrap_element(el, initial_opacity=init_opacity, keyframes=kfs))

    return ScrollimationIR(
        title=ir.title,
        scroll_range=scroll_range,
        snap_positions=snap_positions,
        elements=anims,
    )


def _scene_keyframes(scene_idx: int, num_scenes: int, D: int, H: int) -> list[Keyframe]:
    """Build opacity keyframes for a scene's fade-in and fade-out."""
    kfs: list[Keyframe] = []
    is_first = scene_idx == 0
    is_last = scene_idx == num_scenes - 1

    if not is_first:
        fade_in_start = (scene_idx - 1) * D + H
        fade_in_end = scene_idx * D - H
        kfs.append(Keyframe(at=fade_in_start, opacity=0.0))
        kfs.append(Keyframe(at=fade_in_end, opacity=1.0))

    if not is_last:
        fade_out_start = scene_idx * D + H
        fade_out_end = (scene_idx + 1) * D - H
        if kfs and kfs[-1].at == fade_out_start and kfs[-1].opacity == 1.0:
            pass
        else:
            kfs.append(Keyframe(at=fade_out_start, opacity=1.0))
        kfs.append(Keyframe(at=fade_out_end, opacity=0.0))

    return kfs


def _wrap_element(
    el: ImageElement | HtmlElement | MarkdownElement,
    *,
    initial_opacity: float,
    keyframes: list[Keyframe],
) -> ElementAnimation:
    """Wrap a slide element with animation state for the scrollimation IR."""
    return ElementAnimation(
        element=el,
        initial=InitialState(opacity=initial_opacity),
        keyframes=keyframes,
    )
