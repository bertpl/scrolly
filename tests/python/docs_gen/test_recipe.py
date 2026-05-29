"""Unit tests for the hero-animation recipe schema + loader."""

from pathlib import Path

import pytest
from animation_engine.recipe import (
    CaptionOverlay,
    ClickOverlay,
    CursorOverlay,
    HoldStep,
    KeyOverlay,
    Recipe,
    ScrollHintOverlay,
    ScrollStep,
    ViewStep,
    load_recipe,
    parse_recipe,
)


def _recipe_dict(**overrides) -> dict:
    """A minimal valid recipe dict, with optional top-level overrides."""
    data = {
        "deck": "examples/stacked-diffs",
        "viewport": {"width": 1280, "height": 720, "scale": 2},
        "fps": 15,
        "output": {"path": "out.gif"},
        "steps": [
            {"type": "hold", "view": "deck", "ms": 1000},
            {"type": "view", "to": "slide", "slide": "overview", "ms": 400},
            {"type": "scroll", "slide": "overview", "from": 0.0, "to": 1.0, "ms": 2000},
        ],
        "overlays": [],
    }
    data.update(overrides)
    return data


# ==================================================================================================
#  Parsing
# ==================================================================================================
def test_parse_recipe_step_types() -> None:
    # --- arrange ----------------------
    data = _recipe_dict()

    # --- act --------------------------
    recipe = parse_recipe(data)

    # --- assert -----------------------
    assert isinstance(recipe, Recipe)
    assert [type(s) for s in recipe.steps] == [HoldStep, ViewStep, ScrollStep]
    scroll = recipe.steps[2]
    assert (scroll.start, scroll.end, scroll.ease) == (0.0, 1.0, "linear")


def test_parse_recipe_overlay_types() -> None:
    # --- arrange ----------------------
    data = _recipe_dict(
        overlays=[
            {"type": "caption", "step": 0, "span": [0.1, 0.9], "text": "hi"},
            {"type": "cursor", "step": 1, "span": [0.0, 1.0], "from": [10, 20], "to": [30, 40]},
            {"type": "click", "step": 1, "at": 0.5, "pos": [50, 60]},
            {"type": "key", "step": 2, "at": 0.0, "label": "Z"},
            {"type": "scroll_hint", "step": 2, "span": [0.0, 1.0], "pos": [70, 80]},
        ]
    )

    # --- act --------------------------
    recipe = parse_recipe(data)

    # --- assert -----------------------
    assert [type(o) for o in recipe.overlays] == [
        CaptionOverlay,
        CursorOverlay,
        ClickOverlay,
        KeyOverlay,
        ScrollHintOverlay,
    ]
    assert recipe.overlays[1].start == (10.0, 20.0)
    assert recipe.overlays[1].end == (30.0, 40.0)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop("deck"), id="missing-deck"),
        pytest.param(lambda d: d.update(fps=0), id="fps-zero"),
        pytest.param(lambda d: d.update(steps=[]), id="empty-steps"),
        pytest.param(lambda d: d["steps"][0].update(type="wobble"), id="unknown-step-type"),
        pytest.param(lambda d: d["steps"][0].update(view="sideways"), id="bad-view"),
        pytest.param(lambda d: d["steps"][2].update(**{"from": 1.5}), id="fraction-out-of-range"),
        pytest.param(
            lambda d: d.update(overlays=[{"type": "caption", "step": 9, "span": [0, 1], "text": "x"}]),
            id="overlay-step-out-of-range",
        ),
        pytest.param(
            lambda d: d.update(overlays=[{"type": "caption", "step": 0, "span": [0.9, 0.1], "text": "x"}]),
            id="span-reversed",
        ),
    ],
)
def test_parse_recipe_rejects_invalid(mutate) -> None:
    # --- arrange ----------------------
    data = _recipe_dict()
    mutate(data)

    # --- act / assert -----------------
    with pytest.raises(ValueError):
        parse_recipe(data)


# ==================================================================================================
#  Loading the shipped recipe
# ==================================================================================================
def test_load_shipped_recipe_is_valid(project_root: Path) -> None:
    # --- arrange ----------------------
    recipe_path = project_root / "docs" / "_gen" / "animation_engine" / "hero-animation.recipe.json"

    # --- act --------------------------
    recipe = load_recipe(recipe_path)

    # --- assert -----------------------
    assert recipe.deck == "examples/stacked-diffs/deck.deck.json"
    # The storyboard uses all three step types; the overlay mix evolves as
    # the animation is tuned, so just require a non-empty, valid overlay set.
    step_types = {type(s) for s in recipe.steps}
    assert step_types == {HoldStep, ViewStep, ScrollStep}
    assert len(recipe.overlays) > 0
