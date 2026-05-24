"""Tests for the per-helper logic in ``scrolly.slide.introspect``.

CLI-level behaviour lives in ``tests/python/_cli/test_introspect_*.py``;
these tests pin the JSON-shaping and visibility-interval math directly,
without going through Click.
"""

from __future__ import annotations

from pathlib import Path

from scrolly.pipeline import load_deck
from scrolly.slide.introspect import _compute_visibility_intervals, snaps_to_json, snapshot_to_json, timeline_to_json
from scrolly.slide.ir._framework.animated_values import AnimatedScalar, ScalarKeyframes
from tests.python.conftest import PROJECT_ROOT

WORKED_EXAMPLE = PROJECT_ROOT / "examples" / "worked-example" / "deck.deck.json"


# --------------------------------------------------------------------------
#  _compute_visibility_intervals
# --------------------------------------------------------------------------
def test_visibility_static_positive_opacity_numeric_range() -> None:
    """Static opacity > 0 → one interval spanning [0, scroll_range]."""
    # --- arrange / act ----------------
    result = _compute_visibility_intervals(AnimatedScalar(1.0), scroll_range=1000)

    # --- assert -----------------------
    assert result == [{"from": 0, "to": 1000}]


def test_visibility_static_positive_opacity_auto_range() -> None:
    """Static opacity > 0 on ``"auto"`` slide → unbounded interval (to: None)."""
    # --- arrange / act ----------------
    result = _compute_visibility_intervals(AnimatedScalar(1.0), scroll_range="auto")

    # --- assert -----------------------
    assert result == [{"from": 0, "to": None}]


def test_visibility_static_zero_opacity() -> None:
    """Static opacity == 0 → element never visible → empty interval list."""
    # --- arrange / act ----------------
    result = _compute_visibility_intervals(AnimatedScalar(0.0), scroll_range=1000)

    # --- assert -----------------------
    assert result == []


def test_visibility_simple_fade_in_then_fade_out() -> None:
    """Fade-in then fade-out: one visible interval bounded by the zero-crossings."""
    # --- arrange ----------------------
    opacity = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 0), (200, 1), (800, 1), (1000, 0)]))

    # --- act --------------------------
    result = _compute_visibility_intervals(opacity, scroll_range=1000)

    # --- assert -----------------------
    # The keyframes themselves are at opacity = 0 at positions 0 and 1000,
    # so the visible interval is exactly (200, 800) — but the half-open
    # convention starts at 0 (the boundary) and ends at 1000 since adjacent
    # segments touch end-to-start at the keyframes and get merged.
    # Actually: segment (0, 200) has v1=0, v2=1 → crossing at scroll 0 → (0, 200).
    # Segment (200, 800) has v1=1, v2=1 → (200, 800).
    # Segment (800, 1000) has v1=1, v2=0 → crossing at scroll 1000 → (800, 1000).
    # All three merge to (0, 1000).
    assert result == [{"from": 0, "to": 1000}]


def test_visibility_mid_segment_zero_crossing() -> None:
    """A linear segment crossing zero produces a partial-visibility interval."""
    # --- arrange ----------------------
    # Opacity goes 1 → -1 over [0, 1000]; crosses zero at scroll 500.
    opacity = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 1), (1000, -1)]))

    # --- act --------------------------
    result = _compute_visibility_intervals(opacity, scroll_range=1000)

    # --- assert -----------------------
    assert result == [{"from": 0, "to": 500.0}]


def test_visibility_auto_range_held_constant_positive_at_end() -> None:
    """Auto slide with positive final keyframe extends visibility past last keyframe to None."""
    # --- arrange ----------------------
    # Opacity ramps 0 → 1 over [0, 200], then held constant at 1 past scroll 200.
    opacity = AnimatedScalar(ScalarKeyframes(keyframes=[(0, 0), (200, 1)]))

    # --- act --------------------------
    result = _compute_visibility_intervals(opacity, scroll_range="auto")

    # --- assert -----------------------
    # Interval (0, 200) from the ramp + (200, None) from the held-constant
    # suffix — merge to (0, None).
    assert result == [{"from": 0, "to": None}]


# --------------------------------------------------------------------------
#  Helpers operating on the worked example
# --------------------------------------------------------------------------
def test_snaps_filmstrip_includes_derived_hold_centres() -> None:
    """``filmstrip`` slide's image_sequence contributes derived snap positions."""
    # --- arrange ----------------------
    deck, slide_irs = load_deck(WORKED_EXAMPLE)

    # --- act --------------------------
    result = snaps_to_json(deck, slide_irs, ("filmstrip",))

    # --- assert -----------------------
    filmstrip = result["slides"]["filmstrip"]
    assert "author_snap_positions" in filmstrip
    assert "derived_snap_positions" in filmstrip
    assert "merged" in filmstrip
    # At least one derived entry from the image_sequence element.
    assert len(filmstrip["derived_snap_positions"]) > 0
    # Each derived entry has a structured source.
    for entry in filmstrip["derived_snap_positions"]:
        assert {"element_index", "element_name", "frame_index"} <= set(entry["source"].keys())


def test_timeline_parallax_has_animated_properties_and_intervals() -> None:
    """``parallax`` slide's bg element is animated → timeline surfaces keyframes + intervals."""
    # --- arrange ----------------------
    deck, slide_irs = load_deck(WORKED_EXAMPLE)

    # --- act --------------------------
    result = timeline_to_json(deck, slide_irs, ("parallax",))

    # --- assert -----------------------
    bg = result["slides"]["parallax"]["elements"][0]
    assert bg["name"] == "bg"
    # Position is animated on bg.
    assert "position" in bg["animated_properties"]
    # Visibility intervals are non-empty (bg is fully opaque throughout).
    assert len(bg["visibility_intervals"]) >= 1


def test_snapshot_resolves_animated_properties_at_scroll() -> None:
    """Snapshot on a slide with animated position returns numeric values per scroll."""
    # --- arrange ----------------------
    deck, slide_irs = load_deck(WORKED_EXAMPLE)

    # --- act --------------------------
    result = snapshot_to_json(deck, slide_irs, "parallax", (0.0, 750.0, 1500.0))

    # --- assert -----------------------
    snapshots = result["slides"]["parallax"]["snapshots"]
    assert len(snapshots) == 3
    assert [s["scroll"] for s in snapshots] == [0.0, 750.0, 1500.0]
    # Every snapshot includes the visible flag derived from opacity > 0.
    for snap in snapshots:
        for el in snap["elements"]:
            assert "visible" in el
            assert el["visible"] == (el["opacity"] > 0)
