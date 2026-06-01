"""Unit tests for the hero-animation recipe schema + loader."""

from pathlib import Path

import pytest
from animation_engine.recipe import (
    Border,
    CaptionOverlay,
    ClickOverlay,
    CursorOverlay,
    Gif,
    HoldStep,
    KeyOverlay,
    Output,
    PressStep,
    ProgressBar,
    Recipe,
    ScrollElStep,
    ScrollHintOverlay,
    ScrollStep,
    ViewStep,
    Webp,
    load_recipe,
    parse_recipe,
)


def _recipe_dict(**overrides) -> dict:
    """A minimal valid recipe dict, with optional top-level overrides."""
    data = {
        "deck": "examples/stacked-diffs",
        "viewport": {"width": 1280, "height": 720, "scale": 2},
        "fps": 15,
        "output": {"gif": {"path": "out.gif"}},
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


def test_parse_press_and_scroll_el_steps() -> None:
    # --- arrange ----------------------
    data = _recipe_dict(
        steps=[
            {"type": "press", "key": "d", "ms": 800},
            {
                "type": "scroll_el",
                "selector": ".help-modal-body",
                "from": 0.0,
                "to": 1.0,
                "ms": 1500,
                "ease": "ease-in-out",
            },
        ]
    )

    # --- act --------------------------
    recipe = parse_recipe(data)

    # --- assert -----------------------
    assert recipe.steps[0] == PressStep(key="d", ms=800)
    assert recipe.steps[1] == ScrollElStep(selector=".help-modal-body", start=0.0, end=1.0, ms=1500, ease="ease-in-out")


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


def test_parse_caption_step_forms() -> None:
    # --- arrange ----------------------
    data = _recipe_dict(
        overlays=[
            {"type": "caption", "step": 0, "span": [0.0, 1.0], "text": "single"},
            {"type": "caption", "step": [0, 2], "span": [0.0, 1.0], "text": "range"},
        ]
    )

    # --- act --------------------------
    single, ranged = parse_recipe(data).overlays

    # --- assert -----------------------
    assert (single.step_start, single.step_end) == (0, 0)  # int -> degenerate range
    assert (ranged.step_start, ranged.step_end) == (0, 2)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop("deck"), id="missing-deck"),
        pytest.param(lambda d: d.update(fps=0), id="fps-zero"),
        pytest.param(lambda d: d.update(steps=[]), id="empty-steps"),
        pytest.param(lambda d: d["steps"][0].update(type="wobble"), id="unknown-step-type"),
        pytest.param(lambda d: d["steps"][0].update(view="sideways"), id="bad-view"),
        pytest.param(lambda d: d.update(steps=[{"type": "press", "ms": 500}]), id="press-missing-key"),
        pytest.param(
            lambda d: d.update(steps=[{"type": "scroll_el", "from": 0.0, "to": 1.0, "ms": 500}]),
            id="scroll-el-missing-selector",
        ),
        pytest.param(lambda d: d["steps"][2].update(**{"from": 1.5}), id="fraction-out-of-range"),
        pytest.param(
            lambda d: d.update(overlays=[{"type": "caption", "step": 9, "span": [0, 1], "text": "x"}]),
            id="overlay-step-out-of-range",
        ),
        pytest.param(
            lambda d: d.update(overlays=[{"type": "caption", "step": [2, 0], "span": [0, 1], "text": "x"}]),
            id="caption-range-reversed",
        ),
        pytest.param(
            lambda d: d.update(overlays=[{"type": "caption", "step": [0, 9], "span": [0, 1], "text": "x"}]),
            id="caption-range-out-of-range",
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
    # The storyboard's exact step/overlay mix evolves as the animation is
    # tuned, so just require valid types from the known set and the core
    # hold/view/scroll trio always being present.
    step_types = {type(s) for s in recipe.steps}
    assert step_types <= {HoldStep, ViewStep, ScrollStep, PressStep, ScrollElStep}
    assert {HoldStep, ViewStep, ScrollStep} <= step_types
    assert len(recipe.overlays) > 0


# ==================================================================================================
#  Border + progress bar (whole-run chrome)
# ==================================================================================================
def test_chrome_defaults_off_when_absent() -> None:
    # --- act --------------------------
    recipe = parse_recipe(_recipe_dict())

    # --- assert -----------------------
    assert recipe.border == Border(width=0, color="#000000")
    assert recipe.progress_bar == ProgressBar(height=0, color="#000000", track_color="#000000")


def test_border_parsed() -> None:
    # --- act --------------------------
    recipe = parse_recipe(_recipe_dict(border={"width": 4, "color": "#1A1A1A"}))

    # --- assert -----------------------
    assert recipe.border == Border(width=4, color="#1A1A1A")


def test_progress_bar_parsed() -> None:
    # --- act --------------------------
    recipe = parse_recipe(_recipe_dict(progress_bar={"height": 2, "color": "#4A6FA5", "track_color": "#3A3A3A"}))

    # --- assert -----------------------
    assert recipe.progress_bar == ProgressBar(height=2, color="#4A6FA5", track_color="#3A3A3A")


@pytest.mark.parametrize(
    "block,field",
    [("border", "color"), ("progress_bar", "color"), ("progress_bar", "track_color")],
)
def test_invalid_chrome_color_rejected(block, field) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="opaque hex color"):
        parse_recipe(_recipe_dict(**{block: {field: "red"}}))


@pytest.mark.parametrize("block,field", [("border", "width"), ("progress_bar", "height")])
def test_negative_chrome_size_rejected(block, field) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match=">= 0"):
        parse_recipe(_recipe_dict(**{block: {field: -1}}))


def test_chrome_block_must_be_object() -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="must be an object"):
        parse_recipe(_recipe_dict(border="thick"))


# ==================================================================================================
#  Output blocks (gif / webp) + WebP options
# ==================================================================================================
def test_output_defaults_to_gif_only() -> None:
    # --- act --------------------------
    output = parse_recipe(_recipe_dict()).output

    # --- assert -----------------------
    assert isinstance(output, Output)
    assert output.gif == Gif(path="out.gif", quality=80)
    assert output.webp is None


def test_both_blocks_enable_both_formats() -> None:
    # --- arrange ----------------------
    data = _recipe_dict(output={"loop": False, "gif": {"path": "h.gif"}, "webp": {"path": "h.webp"}})

    # --- act --------------------------
    output = parse_recipe(data).output

    # --- assert -----------------------
    assert output.loop is False
    assert output.gif == Gif(path="h.gif", quality=80)
    assert output.webp == Webp(path="h.webp", quality=80.0, method=4, mode="lossy", near_lossless=60)


def test_webp_only_leaves_gif_none() -> None:
    # --- act --------------------------
    output = parse_recipe(_recipe_dict(output={"webp": {"path": "h.webp"}})).output

    # --- assert -----------------------
    assert output.gif is None
    assert output.webp.path == "h.webp"


def test_output_requires_at_least_one_block() -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="must declare 'gif' and/or 'webp'"):
        parse_recipe(_recipe_dict(output={"loop": True}))


@pytest.mark.parametrize("block", ["gif", "webp"])
def test_output_block_requires_path(block) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="'path'"):
        parse_recipe(_recipe_dict(output={block: {}}))


def test_webp_options_parsed() -> None:
    # --- arrange ----------------------
    output = {"webp": {"path": "h.webp", "quality": 90, "method": 4, "mode": "near_lossless", "near_lossless": 40}}

    # --- act --------------------------
    webp = parse_recipe(_recipe_dict(output=output)).output.webp

    # --- assert -----------------------
    assert webp == Webp(path="h.webp", quality=90.0, method=4, mode="near_lossless", near_lossless=40)


def test_invalid_webp_mode_rejected() -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="must be one of"):
        parse_recipe(_recipe_dict(output={"webp": {"path": "h.webp", "mode": "magic"}}))


@pytest.mark.parametrize(
    "field,value",
    [("method", 7), ("method", -1), ("quality", 101), ("near_lossless", 200)],
)
def test_webp_out_of_range_rejected(field, value) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="must be in"):
        parse_recipe(_recipe_dict(output={"webp": {"path": "h.webp", field: value}}))


@pytest.mark.parametrize("block", ["gif", "webp"])
def test_output_block_must_be_object(block) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="must be an object"):
        parse_recipe(_recipe_dict(output={block: "nope"}))


# ==================================================================================================
#  Viewport capture / delivery scale
# ==================================================================================================
def test_output_scale_defaults_to_scale() -> None:
    # --- act --------------------------
    vp = parse_recipe(_recipe_dict()).viewport

    # --- assert -----------------------
    assert (vp.scale, vp.output_scale) == (2, 2.0)  # absent -> no downscale


def test_output_scale_parsed() -> None:
    # --- arrange ----------------------
    data = _recipe_dict(viewport={"width": 1280, "height": 720, "scale": 2, "output_scale": 1})

    # --- act --------------------------
    vp = parse_recipe(data).viewport

    # --- assert -----------------------
    assert vp.output_scale == 1.0


@pytest.mark.parametrize("bad", [0, -1, 3])  # 0, negative, and above scale (2)
def test_output_scale_out_of_range_rejected(bad) -> None:
    # --- arrange ----------------------
    data = _recipe_dict(viewport={"width": 1280, "height": 720, "scale": 2, "output_scale": bad})

    # --- act / assert -----------------
    with pytest.raises(ValueError, match="output_scale"):
        parse_recipe(data)
