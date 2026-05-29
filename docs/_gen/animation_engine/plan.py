"""Pure frame planning — turn a `Recipe` into a deterministic frame plan.

`build_frame_plan` expands the recipe's ``steps`` into a per-step frame
budget (with interpolated scroll fractions) and resolves ``overlays``
into per-frame draw instructions. Everything here is pure arithmetic:
no browser, no image library, no IO. The capture stage consumes
`FramePlan.steps` to drive the deck; the composite stage consumes
`FramePlan.overlay_draws` to paint each frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from .recipe import (
    CaptionOverlay,
    ClickOverlay,
    CursorOverlay,
    HoldStep,
    KeyOverlay,
    Recipe,
    ScrollStep,
    ViewStep,
)

# Pulse / hold durations for the momentary interaction cues, in ms.
_CLICK_PULSE_MS = 300
_KEY_HOLD_MS = 600


# ==================================================================================================
#  Plan data model
# ==================================================================================================
@dataclass(frozen=True)
class StepFrames:
    """The frame budget + capture hints for one recipe step.

    `type` is ``"hold"`` / ``"view"`` / ``"scroll"``. For ``scroll``,
    `scroll_fractions` holds the per-frame normalized position; for the
    others it is empty. `view` is the target zoom (``"deck"`` /
    ``"slide"`` / ``None`` when unchanged) and `slide` the target slide.
    """

    step_index: int
    type: str
    n_frames: int
    global_start: int
    view: str | None
    slide: str | None
    scroll_fractions: tuple[float, ...]


@dataclass(frozen=True)
class CaptionDraw:
    """Draw a caption at `alpha` opacity on a frame."""

    text: str
    anchor: str
    alpha: float


@dataclass(frozen=True)
class CursorDraw:
    """Draw the cursor sprite at `pos` (viewport px) on a frame."""

    pos: tuple[float, float]


@dataclass(frozen=True)
class ClickDraw:
    """Draw a click pulse at `pos`; `progress` 0..1 expands the ring."""

    pos: tuple[float, float]
    progress: float


@dataclass(frozen=True)
class KeyDraw:
    """Draw a key-press chip showing `label` at `alpha` opacity."""

    label: str
    alpha: float


OverlayDraw = CaptionDraw | CursorDraw | ClickDraw | KeyDraw


@dataclass(frozen=True)
class FramePlan:
    """A fully-resolved animation: per-step capture + per-frame overlays."""

    fps: int
    total_frames: int
    steps: tuple[StepFrames, ...]
    overlay_draws: tuple[tuple[OverlayDraw, ...], ...]


def frame_filename(index: int) -> str:
    """Zero-padded raw/composited frame filename for a global index."""
    return f"frame-{index:05d}.png"


# ==================================================================================================
#  Builder
# ==================================================================================================
def build_frame_plan(recipe: Recipe) -> FramePlan:
    """Expand a recipe into a deterministic `FramePlan`.

    Args:
        recipe: The validated recipe.

    Returns:
        A `FramePlan` whose `steps` drive capture and whose
        `overlay_draws` (one tuple per global frame) drive compositing.
    """
    steps = _plan_steps(recipe)
    total = sum(s.n_frames for s in steps)
    draws = _resolve_overlays(recipe, steps, total)
    return FramePlan(fps=recipe.fps, total_frames=total, steps=steps, overlay_draws=draws)


# --- step planning --------------------------------
def _plan_steps(recipe: Recipe) -> tuple[StepFrames, ...]:
    """Assign each step its frame count, start offset, and capture hints."""
    planned: list[StepFrames] = []
    cursor = 0
    held_slide: str | None = None
    for i, step in enumerate(recipe.steps):
        n = _frame_count(step.ms, recipe.fps)
        if isinstance(step, HoldStep):
            held_slide = step.slide or held_slide
            planned.append(_hold_frames(i, n, cursor, step, held_slide))
        elif isinstance(step, ViewStep):
            held_slide = step.slide or held_slide
            planned.append(StepFrames(i, "view", n, cursor, step.to, step.slide, ()))
        elif isinstance(step, ScrollStep):
            held_slide = step.slide
            planned.append(_scroll_frames(i, n, cursor, step))
        cursor += n
    return tuple(planned)


def _hold_frames(index: int, n: int, start: int, step: HoldStep, slide: str | None) -> StepFrames:
    return StepFrames(index, "hold", n, start, step.view, slide, ())


def _scroll_frames(index: int, n: int, start: int, step: ScrollStep) -> StepFrames:
    fractions = tuple(_lerp(step.start, step.end, _ease(_progress(f, n), step.ease)) for f in range(n))
    return StepFrames(index, "scroll", n, start, "slide", step.slide, fractions)


# --- overlay resolution ---------------------------
def _resolve_overlays(recipe: Recipe, steps: tuple[StepFrames, ...], total: int) -> tuple[tuple[OverlayDraw, ...], ...]:
    """Build the per-frame draw lists from the recipe's overlays."""
    buckets: list[list[OverlayDraw]] = [[] for _ in range(total)]
    for overlay in recipe.overlays:
        step = steps[overlay.step]
        for global_index, draw in _overlay_draws(overlay, step, recipe.fps):
            buckets[global_index].append(draw)
    return tuple(tuple(b) for b in buckets)


def _overlay_draws(overlay: object, step: StepFrames, fps: int):
    """Yield ``(global_frame_index, OverlayDraw)`` for one overlay."""
    if isinstance(overlay, CaptionOverlay):
        yield from _caption_draws(overlay, step, fps)
    elif isinstance(overlay, CursorOverlay):
        yield from _cursor_draws(overlay, step)
    elif isinstance(overlay, ClickOverlay):
        yield from _click_draws(overlay, step, fps)
    elif isinstance(overlay, KeyOverlay):
        yield from _key_draws(overlay, step, fps)


def _caption_draws(overlay: CaptionOverlay, step: StepFrames, fps: int):
    start, end = overlay.span
    # Fade duration in progress units (0..1 over the step). No min-1
    # floor here: fade_ms == 0 must mean a hard cut, not a 1-frame ramp.
    fade_frames = round(overlay.fade_ms / 1000.0 * fps)
    fade_frac = fade_frames / max(step.n_frames - 1, 1)
    for f in range(step.n_frames):
        p = _progress(f, step.n_frames)
        if not start <= p <= end:
            continue
        alpha = _trapezoid_alpha(p, start, end, fade_frac)
        if alpha > 0:
            yield step.global_start + f, CaptionDraw(text=overlay.text, anchor=overlay.anchor, alpha=alpha)


def _cursor_draws(overlay: CursorOverlay, step: StepFrames):
    start, end = overlay.span
    for f in range(step.n_frames):
        p = _progress(f, step.n_frames)
        if not start <= p <= end:
            continue
        local = 0.0 if end == start else (p - start) / (end - start)
        pos = (_lerp(overlay.start[0], overlay.end[0], local), _lerp(overlay.start[1], overlay.end[1], local))
        yield step.global_start + f, CursorDraw(pos=pos)


def _click_draws(overlay: ClickOverlay, step: StepFrames, fps: int):
    target = round(overlay.at * max(step.n_frames - 1, 0))
    pulse = _frame_count(_CLICK_PULSE_MS, fps)
    for k in range(pulse):
        f = target + k
        if f >= step.n_frames:
            break
        yield step.global_start + f, ClickDraw(pos=overlay.pos, progress=_progress(k, pulse))


def _key_draws(overlay: KeyOverlay, step: StepFrames, fps: int):
    target = round(overlay.at * max(step.n_frames - 1, 0))
    hold = _frame_count(_KEY_HOLD_MS, fps)
    for k in range(hold):
        f = target + k
        if f >= step.n_frames:
            break
        # Solid for most of the hold, fading out over the final third.
        tail = max(hold // 3, 1)
        alpha = 1.0 if k < hold - tail else max(0.0, (hold - k) / tail)
        yield step.global_start + f, KeyDraw(label=overlay.label, alpha=alpha)


# --- math helpers ---------------------------------
def _frame_count(ms: int, fps: int) -> int:
    """Frames covering ``ms`` at ``fps`` (at least one)."""
    return max(1, round(ms / 1000.0 * fps))


def _progress(f: int, n: int) -> float:
    """Local progress 0..1 of frame ``f`` within ``n`` frames."""
    return 0.0 if n <= 1 else f / (n - 1)


def _trapezoid_alpha(p: float, start: float, end: float, fade_frac: float) -> float:
    """Opacity ramp: 0 at the span edges rising to 1 after ``fade_frac``."""
    if fade_frac <= 0:
        return 1.0
    rise = (p - start) / fade_frac
    fall = (end - p) / fade_frac
    return max(0.0, min(1.0, rise, fall))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease(t: float, kind: str) -> float:
    """Apply an easing curve to a 0..1 parameter."""
    if kind == "ease-in-out":
        return t * t * (3.0 - 2.0 * t)
    return t  # linear (default / unknown)
