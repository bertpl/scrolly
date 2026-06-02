"""Unit tests for the demo-clip timing checker.

Covers the two guidelines it enforces — caption dwell (absolute + per
word) and the transition buffer (including the three ways a caption can
clear a transition, and the `allow_transition_overlap` opt-out).
"""

from __future__ import annotations

import pytest
from animation_engine.recipe import (
    Border,
    CaptionOverlay,
    Gif,
    HoldStep,
    Output,
    ProgressBar,
    Recipe,
    Viewport,
    ViewStep,
)
from animation_engine.verify_clip_timings import _clears_transition, _step_starts, check_recipe


def _recipe(steps: tuple, overlays: tuple) -> Recipe:
    """A Recipe carrying just the steps + overlays the checker reads."""
    return Recipe(
        deck="d",
        viewport=Viewport(width=10, height=10, scale=1, output_scale=1),
        fps=30,
        output=Output(gif=Gif(path="o.gif")),
        steps=steps,
        overlays=overlays,
        border=Border(),
        progress_bar=ProgressBar(),
    )


# ==================================================================================================
#  Timeline helpers
# ==================================================================================================
def test_step_starts_are_cumulative() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=1000, view="slide"), HoldStep(ms=500, view="slide"), HoldStep(ms=200, view="slide"))

    # --- act --------------------------
    starts = _step_starts(steps)

    # --- assert -----------------------
    assert starts == [0, 1000, 1500]


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (0, 1200, True),  # ends before the transition with margin
        (0, 1400, False),  # fades out too close before it
        (3100, 5000, True),  # starts after the transition with margin
        (2900, 5000, False),  # fades in too close after it
        (1000, 3100, True),  # spans fully across with margin both sides
        (1300, 3100, False),  # overlaps the window without clearing it
    ],
)
def test_clears_transition(start: float, end: float, expected: bool) -> None:
    # --- act / assert -----------------
    # transition window [2000, 2300]; buffer is 750ms.
    assert _clears_transition(start, end, t0=2000, t1=2300) is expected


# ==================================================================================================
#  check_recipe
# ==================================================================================================
def test_clean_caption_has_no_problems() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=3500, view="slide"),)
    cap = CaptionOverlay(step_start=0, step_end=0, span=(0.0, 1.0), text="alpha beta gamma delta")

    # --- act --------------------------
    problems = check_recipe(_recipe(steps, (cap,)))

    # --- assert -----------------------
    assert problems == []


def test_flags_caption_below_absolute_minimum() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=2000, view="slide"),)  # 2000ms < 3000ms floor
    cap = CaptionOverlay(step_start=0, step_end=0, span=(0.0, 1.0), text="alpha beta gamma")

    # --- act --------------------------
    problems = check_recipe(_recipe(steps, (cap,)))

    # --- assert -----------------------
    assert any("on screen" in p for p in problems)


def test_flags_caption_below_per_word_minimum() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=3200, view="slide"),)  # 8 words / 3200ms = 400ms/word < 500
    cap = CaptionOverlay(step_start=0, step_end=0, span=(0.0, 1.0), text="one two three four five six seven eight")

    # --- act --------------------------
    problems = check_recipe(_recipe(steps, (cap,)))

    # --- assert -----------------------
    assert any("ms/word" in p for p in problems)


def test_flags_caption_too_close_to_transition() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=4000, view="slide"), ViewStep(ms=1100, to="deck"), HoldStep(ms=4000, view="deck"))
    cap = CaptionOverlay(step_start=0, step_end=0, span=(0.0, 0.96), text="alpha beta gamma delta")

    # --- act --------------------------
    problems = check_recipe(_recipe(steps, (cap,)))

    # --- assert -----------------------
    assert any("transition" in p for p in problems)


def test_allow_transition_overlap_exempts_buffer() -> None:
    # --- arrange ----------------------
    steps = (HoldStep(ms=4000, view="slide"), ViewStep(ms=1100, to="deck"), HoldStep(ms=4000, view="deck"))
    cap = CaptionOverlay(
        step_start=0, step_end=0, span=(0.0, 0.96), text="alpha beta gamma delta", allow_transition_overlap=True
    )

    # --- act --------------------------
    problems = check_recipe(_recipe(steps, (cap,)))

    # --- assert -----------------------
    assert problems == []
