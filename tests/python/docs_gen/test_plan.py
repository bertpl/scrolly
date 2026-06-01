"""Unit tests for hero-animation frame planning (pure logic)."""

from pathlib import Path

from animation_engine.plan import (
    CaptionDraw,
    ClickDraw,
    CursorDraw,
    KeyDraw,
    ScrollHintDraw,
    build_frame_plan,
    frame_filename,
)
from animation_engine.recipe import load_recipe, parse_recipe


def _recipe(steps, overlays=None, fps=15):
    """Build a Recipe from step / overlay dicts at a fixed fps."""
    return parse_recipe(
        {
            "deck": "d",
            "viewport": {"width": 1280, "height": 720, "scale": 2},
            "fps": fps,
            "output": {"gif": {"path": "out.gif"}},
            "steps": steps,
            "overlays": overlays or [],
        }
    )


# ==================================================================================================
#  Step / frame budgeting
# ==================================================================================================
def test_frame_counts_and_offsets() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [
            {"type": "hold", "view": "deck", "ms": 1000},  # 15 frames @ 15fps
            {"type": "view", "to": "slide", "slide": "s", "ms": 400},  # 6 frames
            {"type": "scroll", "slide": "s", "from": 0.0, "to": 1.0, "ms": 2000},  # 30 frames
        ]
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)

    # --- assert -----------------------
    assert [s.n_frames for s in plan.steps] == [15, 6, 30]
    assert [s.global_start for s in plan.steps] == [0, 15, 21]
    assert plan.total_frames == 51
    assert len(plan.overlay_draws) == 51


def test_scroll_fractions_linear() -> None:
    # --- arrange ----------------------
    recipe = _recipe([{"type": "scroll", "slide": "s", "from": 0.0, "to": 1.0, "ms": 1000, "ease": "linear"}])

    # --- act --------------------------
    fractions = build_frame_plan(recipe).steps[0].scroll_fractions

    # --- assert -----------------------
    assert fractions[0] == 0.0
    assert fractions[-1] == 1.0
    assert all(b >= a for a, b in zip(fractions, fractions[1:]))


def test_scroll_ease_in_out_is_symmetric() -> None:
    # --- arrange ----------------------
    recipe = _recipe([{"type": "scroll", "slide": "s", "from": 0.0, "to": 1.0, "ms": 1000, "ease": "ease-in-out"}])

    # --- act --------------------------
    fractions = build_frame_plan(recipe).steps[0].scroll_fractions
    mid = fractions[len(fractions) // 2]

    # --- assert -----------------------
    assert fractions[0] == 0.0
    assert fractions[-1] == 1.0
    assert abs(mid - 0.5) < 0.05  # smoothstep passes through 0.5 at the midpoint


def test_press_step_plans_static_with_key() -> None:
    # --- arrange ----------------------
    recipe = _recipe([{"type": "press", "key": "d", "ms": 1000}])

    # --- act --------------------------
    step = build_frame_plan(recipe).steps[0]

    # --- assert -----------------------
    assert step.type == "press"
    assert step.key == "d"
    assert step.view is None  # a press does not change the zoom level
    assert step.scroll_fractions == ()
    assert step.n_frames == 15


def test_scroll_el_step_plans_fractions_with_selector() -> None:
    # --- arrange ----------------------
    recipe = _recipe([{"type": "scroll_el", "selector": ".help-modal-body", "from": 0.0, "to": 1.0, "ms": 1000}])

    # --- act --------------------------
    step = build_frame_plan(recipe).steps[0]

    # --- assert -----------------------
    assert step.type == "scroll_el"
    assert step.selector == ".help-modal-body"
    assert step.view is None
    assert step.scroll_fractions[0] == 0.0
    assert step.scroll_fractions[-1] == 1.0


# ==================================================================================================
#  Overlay resolution
# ==================================================================================================
def test_caption_resolves_within_span_only() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [
            {"type": "hold", "view": "deck", "ms": 1000},
            {"type": "hold", "view": "deck", "ms": 1000},
        ],
        overlays=[{"type": "caption", "step": 0, "span": [0.0, 1.0], "text": "hi", "fade_ms": 0}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    step0 = plan.steps[0]
    in_span = [d for f in range(step0.n_frames) for d in plan.overlay_draws[f]]
    after_span = [d for f in range(step0.n_frames, plan.total_frames) for d in plan.overlay_draws[f]]

    # --- assert -----------------------
    assert in_span and all(isinstance(d, CaptionDraw) and d.alpha == 1.0 for d in in_span)
    assert after_span == []


def test_caption_spans_step_range_and_stops_at_range_end() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [
            {"type": "hold", "view": "deck", "ms": 1000},  # step 0: 15 frames
            {"type": "hold", "view": "deck", "ms": 1000},  # step 1: 15 frames
            {"type": "hold", "view": "deck", "ms": 1000},  # step 2: 15 frames
        ],
        overlays=[{"type": "caption", "step": [0, 1], "span": [0.0, 1.0], "text": "hi", "fade_ms": 0}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    in_range = [d for f in range(30) for d in plan.overlay_draws[f]]  # steps 0+1
    after_range = [d for f in range(30, plan.total_frames) for d in plan.overlay_draws[f]]  # step 2

    # --- assert -----------------------
    # The caption covers the full combined window of steps 0+1, then stops.
    assert len(in_range) == 30 and all(isinstance(d, CaptionDraw) for d in in_range)
    assert after_range == []


def test_cursor_interpolates_start_to_end() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [{"type": "hold", "view": "deck", "ms": 1000}],
        overlays=[{"type": "cursor", "step": 0, "span": [0.0, 1.0], "from": [0, 0], "to": [100, 0]}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    cursors = [d for frame in plan.overlay_draws for d in frame if isinstance(d, CursorDraw)]

    # --- assert -----------------------
    assert cursors[0].pos == (0.0, 0.0)
    assert cursors[-1].pos == (100.0, 0.0)


def test_click_pulse_appears_at_moment() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [{"type": "hold", "view": "deck", "ms": 1000}],
        overlays=[{"type": "click", "step": 0, "at": 1.0, "pos": [5, 6]}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    clicks = [d for frame in plan.overlay_draws for d in frame if isinstance(d, ClickDraw)]

    # --- assert -----------------------
    assert clicks  # a pulse was emitted
    assert clicks[0].progress == 0.0  # ring starts collapsed
    assert all(c.pos == (5.0, 6.0) for c in clicks)


def test_key_chip_appears() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [{"type": "hold", "view": "deck", "ms": 1000}],
        overlays=[{"type": "key", "step": 0, "at": 0.0, "label": "Z"}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    keys = [d for frame in plan.overlay_draws for d in frame if isinstance(d, KeyDraw)]

    # --- assert -----------------------
    assert keys and all(k.label == "Z" for k in keys)


def test_scroll_hint_emits_cycling_phase() -> None:
    # --- arrange ----------------------
    recipe = _recipe(
        [{"type": "hold", "view": "deck", "ms": 1000}],
        overlays=[{"type": "scroll_hint", "step": 0, "span": [0.0, 1.0], "pos": [100, 200]}],
    )

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    hints = [d for frame in plan.overlay_draws for d in frame if isinstance(d, ScrollHintDraw)]

    # --- assert -----------------------
    assert hints
    assert all(0.0 <= h.phase < 1.0 and h.pos == (100.0, 200.0) for h in hints)


# ==================================================================================================
#  Helpers + shipped recipe
# ==================================================================================================
def test_frame_filename_is_zero_padded() -> None:
    # --- arrange / act / assert -------
    assert frame_filename(7) == "frame-00007.png"


def test_shipped_recipe_plans_cleanly(project_root: Path) -> None:
    # --- arrange ----------------------
    recipe = load_recipe(project_root / "docs" / "_gen" / "animation_engine" / "hero-animation.recipe.json")

    # --- act --------------------------
    plan = build_frame_plan(recipe)
    drawn = [d for frame in plan.overlay_draws for d in frame]

    # --- assert -----------------------
    assert plan.total_frames > 0
    assert len(plan.overlay_draws) == plan.total_frames
    assert drawn  # overlays resolve to per-frame draws
