"""Stage 1 — Playwright capture of raw frames.

Drives the built deck's automation hook (``?scrolly-automation=1``)
according to a `FramePlan` and screenshots raw (overlay-free) frames to
a cache directory. Frames are named ``frame-NNNNN.png`` by global index
so stage 2 can pair them with `FramePlan.overlay_draws`.

Determinism notes:

- ``setScroll`` is synchronous (it sets the ``--scroll-position`` CSS
  var and syncs the scrollbar), so scroll frames are captured with no
  settling wait — each ``setScroll`` then screenshot is exact.
- Pan / zoom are CSS transitions; ``isAnimating()`` (the
  ``view-transitioning`` body class) is the settle signal. View steps
  are sampled in real time across the transition to capture motion.
- Scripted hook calls don't reset the idle-fade timers, so the
  scrollbar / snap / zoom controls are pinned visible via injected CSS
  (otherwise the scroll affordance would fade out mid-capture).

Requires the optional ``capture`` dependency group (Playwright + a
browser from ``make capture-setup``); ``playwright`` is imported lazily
so the rest of the engine loads without it.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from .plan import FramePlan, StepFrames, frame_filename
from .recipe import Recipe

# Injected before capture. Two jobs:
#  1. Pin the idle-faded controls visible (scripted hook calls don't reset
#     the idle timer the way real input does).
#  2. Zero native scrollbars. canvas.js centers the slide cluster from
#     window.innerWidth/innerHeight, which include space-taking scrollbars.
#     Headless Chromium renders classic (space-taking) root scrollbars where
#     macOS Chrome uses zero-width overlay scrollbars, so that extra gutter
#     shifts the captured slide toward the scrollbars. Zeroing them makes the
#     headless geometry match what a real browser sees. (Only affects the top
#     document; iframe-internal scrollbars are behind the iframe boundary.)
_CAPTURE_CSS = """
.scroll-ui.scroll-ui-idle { opacity: 1 !important; transition: none !important; }
.navigation.hover-ui-idle .zoom-out-control,
.navigation.hover-ui-idle .edge-arrow { opacity: 1 !important; transition: none !important; }
::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
"""

# JS that drives setScroll to its clamp ceiling and reads back the
# resulting (clamped) scroll position — i.e. the slide's scroll range.
_PROBE_RANGE_JS = """(id) => {
  window.__scrolly.setScroll(1e9);
  const el = document.querySelector('.slide-container[data-id="' + id + '"]');
  const v = el ? getComputedStyle(el).getPropertyValue('--scroll-position') : '0';
  return parseFloat(v) || 0;
}"""


# ==================================================================================================
#  Entry point
# ==================================================================================================
def run_capture(recipe: Recipe, plan: FramePlan, deck_html: Path, frames_dir: Path) -> int:
    """Capture every frame of the plan to ``frames_dir``.

    Args:
        recipe: The validated recipe (viewport / fps).
        plan: The frame plan whose `steps` drive the deck.
        deck_html: Path to the built deck's ``index.html``.
        frames_dir: Output directory for ``frame-NNNNN.png`` files
            (created and cleared of stale frames).

    Returns:
        The number of frames written.
    """
    from playwright.sync_api import sync_playwright

    _prepare_frames_dir(frames_dir)
    url = f"{deck_html.resolve().as_uri()}?scrolly-automation=1"

    # Default headless; SCROLLY_CAPTURE_HEADED=1 runs a real (headed) window
    # for pixel-exact parity with a desktop browser if the CSS fix ever isn't
    # enough on a given platform.
    headless = os.environ.get("SCROLLY_CAPTURE_HEADED") != "1"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page(
            viewport={"width": recipe.viewport.width, "height": recipe.viewport.height},
            device_scale_factor=recipe.viewport.scale,
        )
        page.goto(url)
        page.wait_for_function("() => !!(window.__scrolly && window.__scrolly.isAnimating)")
        page.add_style_tag(content=_CAPTURE_CSS)

        ranges: dict[str, float] = {}
        for step in plan.steps:
            _capture_step(page, recipe, step, frames_dir, ranges)

        browser.close()

    return plan.total_frames


# --- per-step capture -----------------------------
def _capture_step(page, recipe: Recipe, step: StepFrames, frames_dir: Path, ranges: dict[str, float]) -> None:
    """Capture one step's frames according to its type."""
    if step.type == "hold":
        _set_state(page, step.view, step.slide)
        _shoot_static_run(page, frames_dir, step.global_start, step.n_frames)
    elif step.type == "view":
        _shoot_transition(page, recipe, step, frames_dir)
    elif step.type == "scroll":
        _set_state(page, "slide", step.slide)
        range_units = ranges.setdefault(step.slide, _probe_range(page, step.slide))
        _shoot_scroll(page, frames_dir, step, range_units)


def _shoot_static_run(page, frames_dir: Path, start: int, n: int) -> None:
    """Screenshot once and duplicate for an unchanging (held) view."""
    first = _frame_path(frames_dir, start)
    page.screenshot(path=str(first))
    data = first.read_bytes()
    for k in range(1, n):
        _frame_path(frames_dir, start + k).write_bytes(data)


def _shoot_transition(page, recipe: Recipe, step: StepFrames, frames_dir: Path) -> None:
    """Trigger a pan / zoom and sample frames in real time across it."""
    if step.slide:
        page.evaluate("(id) => window.__scrolly.selectSlide(id)", step.slide)
    if step.view:
        page.evaluate("(v) => window.__scrolly.setView(v)", step.view)
    interval = 1.0 / recipe.fps
    for k in range(step.n_frames):
        page.screenshot(path=str(_frame_path(frames_dir, step.global_start + k)))
        time.sleep(interval)


def _shoot_scroll(page, frames_dir: Path, step: StepFrames, range_units: float) -> None:
    """Set each frame's scroll position and screenshot (synchronous)."""
    for k, fraction in enumerate(step.scroll_fractions):
        page.evaluate("(p) => window.__scrolly.setScroll(p)", fraction * range_units)
        page.screenshot(path=str(_frame_path(frames_dir, step.global_start + k)))


# --- browser helpers ------------------------------
def _set_state(page, view: str | None, slide: str | None) -> None:
    """Select a slide and/or set the zoom level, then wait for settle."""
    if slide:
        page.evaluate("(id) => window.__scrolly.selectSlide(id)", slide)
    if view:
        page.evaluate("(v) => window.__scrolly.setView(v)", view)
    page.wait_for_function("() => !window.__scrolly.isAnimating()", timeout=3000)


def _probe_range(page, slide: str) -> float:
    """Discover a slide's scroll range, then reset its scroll to 0."""
    range_units = page.evaluate(_PROBE_RANGE_JS, slide)
    page.evaluate("() => window.__scrolly.setScroll(0)")
    return float(range_units)


def _prepare_frames_dir(frames_dir: Path) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()


def _frame_path(frames_dir: Path, index: int) -> Path:
    return frames_dir / frame_filename(index)
