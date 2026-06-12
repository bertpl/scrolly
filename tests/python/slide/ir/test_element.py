"""Tests for SlideElement, element types, and shared validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import (
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideElement,
)

# ── helpers ───────────────────────────────────────────────────────


def _html(**overrides) -> dict:
    base = {"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}
    return {**base, **overrides}


def _asset(**overrides) -> dict:
    base = {"image": "img.jpg", "position": [0, 0], "width": 100, "height": 100, "object_fit": "cover"}
    return {**base, **overrides}


def _md(**overrides) -> dict:
    base = {"markdown": "# Hi", "position": [10, 30], "width": 80, "height": "auto"}
    return {**base, **overrides}


def _mermaid(**overrides) -> dict:
    base = {"mermaid": "graph LR\n  A --> B", "position": [10, 10], "width": 80, "height": "auto"}
    return {**base, **overrides}


def _iframe(**overrides) -> dict:
    base = {
        "iframe_html": "<!doctype html><p>hi</p>",
        "position": [10, 10],
        "width": 80,
        "height": 80,
    }
    return {**base, **overrides}


def _image_sequence(**overrides) -> dict:
    base = {
        "image_sequence": ["a.svg", "b.svg", "c.svg"],
        "frame_distance": 400,
        "hold_fraction": 0.5,
        "position": [0, 0],
        "width": 80,
        "height": "auto",
    }
    return {**base, **overrides}


# ── SlideElement base ─────────────────────────────────────────────


def test_is_pydantic_model():
    assert issubclass(SlideElement, BaseModel)


def test_frozen():
    el = HtmlElement(**_html())
    with pytest.raises(ValidationError):
        el.html = "changed"


def test_name_defaults_to_none():
    el = HtmlElement(**_html())
    assert el.name is None


def test_name_can_be_set():
    el = HtmlElement(**_html(name="myname"))
    assert el.name == "myname"


def test_default_anchor():
    el = HtmlElement(**_html())
    assert el.anchor.static_value == (0.0, 0.0)


def test_custom_anchor():
    el = HtmlElement(**_html(anchor=[50, 50]))
    assert el.anchor.static_value == (50, 50)


def test_extra_field_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        HtmlElement(**_html(bogus="x"))


def test_default_opacity():
    el = HtmlElement(**_html())
    assert el.opacity.static_value == 1.0


def test_default_scale():
    el = HtmlElement(**_html())
    assert el.scale.static_value == 1.0


def test_default_angle():
    el = HtmlElement(**_html())
    assert el.angle.static_value == 0.0


def test_animated_opacity():
    kfs = {"keyframes": [(0, 0.0), (1000, 1.0)]}
    el = HtmlElement(**_html(opacity=kfs))
    assert el.opacity.is_animated
    assert el.opacity.keyframes == [(0, 0.0), (1000, 1.0)]


def test_animated_position():
    kfs = {"keyframes": [(0, (0, 0)), (1000, (50, 50))]}
    el = HtmlElement(**_html(position=kfs))
    assert el.position.is_animated
    assert el.position.keyframes == [(0, (0, 0)), (1000, (50, 50))]


# ── Size validation ───────────────────────────────────────────────


def test_auto_auto_rejected():
    with pytest.raises(SlideSourceError, match="at least one size dimension must be non-auto"):
        HtmlElement(**_html(width="auto", height="auto"))


def test_zero_width_rejected():
    with pytest.raises(SlideSourceError, match="numeric width must be > 0"):
        HtmlElement(**_html(width=0, height=100))


def test_negative_height_rejected():
    with pytest.raises(SlideSourceError, match="numeric height must be > 0"):
        HtmlElement(**_html(width=100, height=-5))


def test_auto_width_numeric_height():
    el = HtmlElement(**_html(width="auto", height=50))
    assert el.width.is_auto
    assert el.height.static_value == 50


def test_numeric_width_auto_height():
    el = HtmlElement(**_html(width=80, height="auto"))
    assert el.width.static_value == 80
    assert el.height.is_auto


def test_oversized_values_allowed():
    el = HtmlElement(**_html(width=200, height=300))
    assert el.width.static_value == 200
    assert el.height.static_value == 300


def test_negative_position_allowed():
    el = HtmlElement(**_html(position=[-50, -100]))
    assert el.position.static_value == (-50, -100)


# ── ImageElement ──────────────────────────────────────────────────


def test_image_valid():
    el = ImageElement(**_asset())
    assert el.image == Path("img.jpg")
    assert el.object_fit == "cover"


def test_object_fit_contain():
    el = ImageElement(**_asset(object_fit="contain"))
    assert el.object_fit == "contain"


def test_object_fit_fill():
    el = ImageElement(**_asset(object_fit="fill"))
    assert el.object_fit == "fill"


def test_image_auto_size_without_object_fit():
    el = ImageElement(**_asset(width=100, height="auto", object_fit=None))
    assert el.object_fit is None


def test_image_object_fit_required_when_both_numeric():
    with pytest.raises(SlideSourceError, match="object_fit is required"):
        ImageElement(**_asset(object_fit=None))


def test_image_object_fit_forbidden_with_auto():
    with pytest.raises(SlideSourceError, match="object_fit is forbidden"):
        ImageElement(**_asset(width=100, height="auto", object_fit="cover"))


def test_image_extra_field_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        ImageElement(**_asset(html="sneaky"))


# ── ImageSequenceElement ──────────────────────────────────────────


def test_image_sequence_valid():
    el = ImageSequenceElement(**_image_sequence())
    assert [p.name for p in el.image_sequence] == ["a.svg", "b.svg", "c.svg"]
    assert el.frame_distance == 400
    assert el.hold_fraction == 0.5


def test_defaults():
    el = ImageSequenceElement(**_image_sequence())
    assert el.scroll_offset == 0
    assert el.fade_in == 0
    assert el.fade_out == 0
    assert el.object_fit is None


def test_repeats_allowed():
    el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "b.svg", "b.svg", "c.svg"]))
    assert len(el.image_sequence) == 4
    assert el.image_sequence[1] == el.image_sequence[2]


def test_empty_string_becomes_none():
    el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "", "b.svg"]))
    assert len(el.image_sequence) == 3
    assert el.image_sequence[0] is not None
    assert el.image_sequence[1] is None
    assert el.image_sequence[2] is not None


def test_consecutive_empty_strings_allowed():
    el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "", "", "b.svg"]))
    assert el.image_sequence[1] is None
    assert el.image_sequence[2] is None


def test_empty_string_counts_toward_min_two():
    el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", ""]))
    assert len(el.image_sequence) == 2


def test_too_few_frames_rejected():
    with pytest.raises(SlideSourceError, match="image_sequence must contain at least 2 entries"):
        ImageSequenceElement(**_image_sequence(image_sequence=["a.svg"]))


def test_hold_fraction_one_rejected():
    with pytest.raises(SlideSourceError, match=r"hold_fraction must be in \[0, 1\)"):
        ImageSequenceElement(**_image_sequence(hold_fraction=1))


def test_hold_fraction_above_one_rejected():
    with pytest.raises(SlideSourceError, match=r"hold_fraction must be in \[0, 1\)"):
        ImageSequenceElement(**_image_sequence(hold_fraction=1.5))


def test_negative_hold_fraction_rejected():
    with pytest.raises(SlideSourceError, match=r"hold_fraction must be in \[0, 1\)"):
        ImageSequenceElement(**_image_sequence(hold_fraction=-0.1))


def test_zero_hold_fraction_allowed():
    el = ImageSequenceElement(**_image_sequence(hold_fraction=0))
    assert el.hold_fraction == 0


def test_hold_fraction_defaults_to_0_2():
    kwargs = _image_sequence()
    del kwargs["hold_fraction"]
    assert ImageSequenceElement(**kwargs).hold_fraction == 0.2


def test_zero_frame_distance_rejected():
    with pytest.raises(SlideSourceError, match="frame_distance must be > 0"):
        ImageSequenceElement(**_image_sequence(frame_distance=0))


def test_negative_fade_in_rejected():
    with pytest.raises(SlideSourceError, match="fade_in must be >= 0"):
        ImageSequenceElement(**_image_sequence(fade_in=-1))


def test_negative_fade_out_rejected():
    with pytest.raises(SlideSourceError, match="fade_out must be >= 0"):
        ImageSequenceElement(**_image_sequence(fade_out=-1))


def test_zero_fade_in_allowed():
    el = ImageSequenceElement(**_image_sequence(fade_in=0))
    assert el.fade_in == 0


def test_positive_fade_in_allowed():
    el = ImageSequenceElement(**_image_sequence(fade_in=150))
    assert el.fade_in == 150


def test_image_sequence_object_fit_required_when_both_numeric():
    with pytest.raises(SlideSourceError, match="object_fit is required"):
        ImageSequenceElement(**_image_sequence(width=80, height=60))


def test_object_fit_with_both_numeric():
    el = ImageSequenceElement(**_image_sequence(width=80, height=60, object_fit="cover"))
    assert el.object_fit == "cover"


def test_image_sequence_object_fit_forbidden_with_auto():
    with pytest.raises(SlideSourceError, match="object_fit is forbidden"):
        ImageSequenceElement(**_image_sequence(object_fit="cover"))


def test_image_sequence_extra_field_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        ImageSequenceElement(**_image_sequence(image="sneaky.png"))


def test_inherits_animated_position():
    el = ImageSequenceElement(**_image_sequence(position={"keyframes": [(0, (0, 0)), (1000, (50, 50))]}))
    assert el.position.is_animated


# ── HtmlElement ───────────────────────────────────────────────────


def test_html_valid():
    el = HtmlElement(**_html())
    assert el.html == "<p>hi</p>"


def test_missing_html_rejected():
    data = _html()
    del data["html"]
    with pytest.raises(ValidationError):
        HtmlElement(**data)


# ── IframeElement ─────────────────────────────────────────────────


def test_iframe_valid():
    el = IframeElement(**_iframe())
    assert el.iframe_html == "<!doctype html><p>hi</p>"


def test_default_decorations():
    el = IframeElement(**_iframe())
    assert el.border_width == 0
    assert el.border_color == "#000000"
    assert el.shadow_size == 0
    assert el.shadow_color == "#000000"


def test_custom_border():
    el = IframeElement(**_iframe(border_width=4, border_color="#333"))
    assert el.border_width == 4
    assert el.border_color == "#333"


def test_custom_shadow():
    el = IframeElement(**_iframe(shadow_size=12, shadow_color="rgba(0,0,0,0.3)"))
    assert el.shadow_size == 12
    assert el.shadow_color == "rgba(0,0,0,0.3)"


def test_negative_border_width_rejected():
    with pytest.raises(SlideSourceError, match="border_width must be >= 0"):
        IframeElement(**_iframe(border_width=-1))


def test_negative_shadow_size_rejected():
    with pytest.raises(SlideSourceError, match="shadow_size must be >= 0"):
        IframeElement(**_iframe(shadow_size=-5))


def test_missing_iframe_html_rejected():
    data = _iframe()
    del data["iframe_html"]
    with pytest.raises(ValidationError):
        IframeElement(**data)


def test_iframe_extra_field_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        IframeElement(**_iframe(bogus="x"))


def test_iframe_frozen():
    el = IframeElement(**_iframe())
    with pytest.raises(ValidationError):
        el.iframe_html = "changed"


def test_inherits_size_validation():
    with pytest.raises(SlideSourceError, match="at least one size dimension must be non-auto"):
        IframeElement(**_iframe(width="auto", height="auto"))


def test_inherits_animated_opacity():
    kfs = {"keyframes": [(0, 0.0), (1000, 1.0)]}
    el = IframeElement(**_iframe(opacity=kfs))
    assert el.opacity.is_animated


# ── MarkdownElement ───────────────────────────────────────────────


def test_markdown_valid():
    el = MarkdownElement(**_md())
    assert el.markdown == "# Hi"


def test_default_color():
    el = MarkdownElement(**_md())
    assert el.color == "inherit"


def test_custom_color():
    el = MarkdownElement(**_md(color="#fff"))
    assert el.color == "#fff"


# ── MermaidElement ───────────────────────────────────────────────


def test_mermaid_valid():
    el = MermaidElement(**_mermaid())
    assert el.mermaid == "graph LR\n  A --> B"


def test_mermaid_frozen():
    el = MermaidElement(**_mermaid())
    with pytest.raises(ValidationError):
        el.mermaid = "changed"


def test_mermaid_extra_field_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        MermaidElement(**_mermaid(html="sneaky"))


def test_auto_height():
    el = MermaidElement(**_mermaid(width=80, height="auto"))
    assert el.width.static_value == 80
    assert el.height.is_auto


def test_both_numeric_size():
    el = MermaidElement(**_mermaid(width=40, height=50))
    assert el.width.static_value == 40
    assert el.height.static_value == 50


def test_size_validation_applies():
    with pytest.raises(SlideSourceError, match="at least one size dimension must be non-auto"):
        MermaidElement(**_mermaid(width="auto", height="auto"))


# ==================================================================================================
#  ImageSequenceElement.snap_positions / timeline — frame-grid derivation
# ==================================================================================================
def _seq(**overrides) -> dict:
    """Minimal valid ImageSequenceElement kwargs."""
    base = {
        "image_sequence": [Path("a.png"), Path("b.png"), Path("c.png")],
        "frame_distance": 400,
        "hold_fraction": 0.5,
        "position": [0, 0],
        "width": 100,
        "height": 50,
        "object_fit": "cover",
    }
    return {**base, **overrides}


def test_snap_positions_basic() -> None:
    """Snaps land on the frame grid: ``scroll_offset + i * frame_distance``."""
    # --- arrange ----------------------
    el = ImageSequenceElement(**_seq(scroll_offset=0, frame_distance=400))

    # --- act --------------------------
    snaps = el.snap_positions()

    # --- assert -----------------------
    assert snaps == [0.0, 400.0, 800.0]


def test_snap_positions_with_offset() -> None:
    """``scroll_offset`` shifts every snap."""
    # --- arrange / act ----------------
    el = ImageSequenceElement(**_seq(scroll_offset=50, frame_distance=400))

    # --- assert -----------------------
    assert el.snap_positions() == [50.0, 450.0, 850.0]


def test_snap_positions_one_per_slot() -> None:
    """One snap per slot — including repeated frames and blank slots."""
    # --- arrange / act / assert -------
    el = ImageSequenceElement(**_seq(image_sequence=[Path("a.png"), Path("a.png"), None, Path("b.png")]))
    assert el.snap_positions() == [0.0, 400.0, 800.0, 1200.0]


def test_timeline_start_and_end() -> None:
    """Timeline spans ``[scroll_offset - fade_in, last_snap + fade_out]``."""
    # --- arrange ----------------------
    el = ImageSequenceElement(**_seq(scroll_offset=100, frame_distance=400, fade_in=80, fade_out=150))

    # --- act / assert -----------------
    # last snap = 100 + 2*400 = 900
    assert el.timeline_start() == 100 - 80
    assert el.timeline_end() == 900 + 150


# ── element source registry ───────────────────────────────────────


def test_element_source_types_keys() -> None:
    """Registry is keyed by each element's author-facing source key."""
    # --- arrange / act ----------------
    from scrolly.slide.ir import element_source_types

    registry = element_source_types()

    # --- assert -----------------------
    assert set(registry) == {"container", "html", "iframe", "image", "image_sequence", "markdown", "mermaid"}
    assert registry["image_sequence"] is ImageSequenceElement


def test_element_source_types_matches_slide_union() -> None:
    """Registry stays in lockstep with the ``AnyElement`` union the slide parses."""
    # --- arrange ----------------------
    from typing import get_args

    from scrolly.slide.ir import element_source_types
    from scrolly.slide.ir.slide import AnyElement

    # --- act / assert -----------------
    assert set(element_source_types().values()) == set(get_args(AnyElement))


def test_element_source_schema_is_json_serializable() -> None:
    """Each element exposes a JSON-schema dict via ``source_schema``."""
    # --- arrange / act ----------------
    from scrolly.slide.ir import element_source_types

    # --- assert -----------------------
    for key, cls in element_source_types().items():
        schema = cls.source_schema()
        assert schema["title"] == cls.__name__, key
