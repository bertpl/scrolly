"""Static timing checker for the viewing-decks demo clips.

Validates every ``clips/*.recipe.json`` against the legibility
guidelines the clips are authored to, without rendering them:

- **Caption dwell** — each caption stays on screen at least
  ``MIN_CAPTION_MS`` *and* at least ``MIN_MS_PER_WORD`` per word, so it
  is readable while the viewer also watches the animation.
- **Transition buffer** — a caption's fade-in / fade-out keeps at least
  ``TRANSITION_BUFFER_MS`` clear of every full-screen transition (a
  ``view`` zoom, a ``z`` view-toggle, or an ``h`` help-modal pop),
  unless the caption sets ``allow_transition_overlap`` because it
  deliberately narrates the transition it rides over.

A ``view`` zoom animates for its whole step, so its window is the full
step; a ``z`` / ``h`` press only pops briefly and then holds, so its
window is capped at ``POP_MS``.

Run directly (``uv run python docs/_gen/animation_engine/verify_clip_timings.py``);
exits non-zero if any clip violates a guideline.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from animation_engine.recipe import (  # noqa: E402
    CaptionOverlay,
    PressStep,
    Recipe,
    Step,
    ViewStep,
    load_recipe,
)

# ==================================================================================================
#  Guidelines
# ==================================================================================================
MIN_CAPTION_MS = 3000
MIN_MS_PER_WORD = 500
TRANSITION_BUFFER_MS = 750
POP_MS = 350
POP_KEYS = ("z", "h")

CLIPS_DIR = Path(__file__).resolve().parent / "clips"


# ==================================================================================================
#  Timeline helpers
# ==================================================================================================
def _step_starts(steps: tuple[Step, ...]) -> list[int]:
    """Return each step's start time in ms (cumulative sum of prior durations)."""
    starts: list[int] = []
    t = 0
    for s in steps:
        starts.append(t)
        t += s.ms
    return starts


def _transition_windows(steps: tuple[Step, ...], starts: list[int]) -> list[tuple[int, int, int]]:
    """Find the animated window of every full-screen transition.

    Args:
        steps: The recipe's steps.
        starts: Each step's start time in ms (from `_step_starts`).

    Returns:
        A list of `(step_index, start_ms, end_ms)` windows: full-step for
        `view` zooms, capped at `POP_MS` for `z` / `h` presses.
    """
    windows: list[tuple[int, int, int]] = []
    for i, s in enumerate(steps):
        if isinstance(s, ViewStep):
            windows.append((i, starts[i], starts[i] + s.ms))
        elif isinstance(s, PressStep) and s.key in POP_KEYS:
            windows.append((i, starts[i], starts[i] + min(s.ms, POP_MS)))
    return windows


def _caption_window(steps: tuple[Step, ...], starts: list[int], cap: CaptionOverlay) -> tuple[float, float]:
    """Resolve a caption's on-screen `(start_ms, end_ms)` from its step range and span."""
    span_ms = sum(steps[k].ms for k in range(cap.step_start, cap.step_end + 1))
    base = starts[cap.step_start]
    return base + cap.span[0] * span_ms, base + cap.span[1] * span_ms


def _clears_transition(start: float, end: float, t0: int, t1: int) -> bool:
    """Whether a caption `[start, end]` keeps the buffer clear of a transition `[t0, t1]`.

    Args:
        start: Caption fade-in time in ms.
        end: Caption fade-out time in ms.
        t0: Transition window start in ms.
        t1: Transition window end in ms.

    Returns:
        True if the caption ends before, starts after, or fully spans the
        transition with at least `TRANSITION_BUFFER_MS` of margin.
    """
    ends_before = end <= t0 - TRANSITION_BUFFER_MS
    starts_after = start >= t1 + TRANSITION_BUFFER_MS
    spans_across = start <= t0 - TRANSITION_BUFFER_MS and end >= t1 + TRANSITION_BUFFER_MS
    return ends_before or starts_after or spans_across


# ==================================================================================================
#  Checking
# ==================================================================================================
def check_recipe(recipe: Recipe) -> list[str]:
    """Return one message per guideline a recipe's captions violate (empty if clean).

    Args:
        recipe: A parsed clip recipe.

    Returns:
        Human-readable failure messages, one per dwell- or buffer-rule breach.
    """
    steps = recipe.steps
    starts = _step_starts(steps)
    windows = _transition_windows(steps, starts)

    problems: list[str] = []
    for cap in (o for o in recipe.overlays if isinstance(o, CaptionOverlay)):
        start, end = _caption_window(steps, starts, cap)
        dur = end - start
        words = len(cap.text.split())
        ms_per_word = dur / words

        if dur < MIN_CAPTION_MS:
            problems.append(f'"{cap.text}": on screen {dur:.0f}ms < {MIN_CAPTION_MS}ms')
        if ms_per_word < MIN_MS_PER_WORD:
            problems.append(f'"{cap.text}": {ms_per_word:.0f}ms/word < {MIN_MS_PER_WORD}ms/word')
        if not cap.allow_transition_overlap:
            for ti, t0, t1 in windows:
                if not _clears_transition(start, end, t0, t1):
                    problems.append(
                        f'"{cap.text}": within {TRANSITION_BUFFER_MS}ms of the transition at step {ti} [{t0}-{t1}ms]'
                    )
    return problems


def main() -> int:
    """Check every clip recipe and print a per-clip verdict.

    Returns:
        0 if all clips pass, 1 if any clip violates a guideline.
    """
    failed = False
    for path in sorted(CLIPS_DIR.glob("*.recipe.json")):
        problems = check_recipe(load_recipe(path))
        if problems:
            failed = True
            print(f"FAIL  {path.name}")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"ok    {path.name}")
    print()
    print("FAILED — fix the captions above." if failed else "All clips pass the timing guidelines.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
