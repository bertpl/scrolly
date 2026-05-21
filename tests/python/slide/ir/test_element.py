"""Tests for SlideElement, element types, and shared validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.slide.ir import (
    AnimatedScalar,
    AnimatedVec2,
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    ScalarKeyframes,
    SlideElement,
    Vec2Keyframes,
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
        "hold": 200,
        "position": [0, 0],
        "width": 80,
        "height": "auto",
    }
    return {**base, **overrides}


# ── SlideElement base ─────────────────────────────────────────────


class TestSlideElement:
    def test_is_pydantic_model(self):
        assert issubclass(SlideElement, BaseModel)

    def test_frozen(self):
        el = HtmlElement(**_html())
        with pytest.raises(ValidationError):
            el.html = "changed"

    def test_name_defaults_to_none(self):
        el = HtmlElement(**_html())
        assert el.name is None

    def test_name_can_be_set(self):
        el = HtmlElement(**_html(name="myname"))
        assert el.name == "myname"

    def test_default_anchor(self):
        el = HtmlElement(**_html())
        assert el.anchor.static_value == (0.0, 0.0)

    def test_custom_anchor(self):
        el = HtmlElement(**_html(anchor=[50, 50]))
        assert el.anchor.static_value == (50, 50)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            HtmlElement(**_html(bogus="x"))

    def test_default_opacity(self):
        el = HtmlElement(**_html())
        assert el.opacity.static_value == 1.0

    def test_default_scale(self):
        el = HtmlElement(**_html())
        assert el.scale.static_value == 1.0

    def test_default_angle(self):
        el = HtmlElement(**_html())
        assert el.angle.static_value == 0.0

    def test_animated_opacity(self):
        kfs = {"keyframes": [(0, 0.0), (1000, 1.0)]}
        el = HtmlElement(**_html(opacity=kfs))
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(0, 0.0), (1000, 1.0)]

    def test_animated_position(self):
        kfs = {"keyframes": [(0, (0, 0)), (1000, (50, 50))]}
        el = HtmlElement(**_html(position=kfs))
        assert el.position.is_animated
        assert el.position.keyframes == [(0, (0, 0)), (1000, (50, 50))]


# ── Size validation ───────────────────────────────────────────────


class TestSizeValidation:
    def test_auto_auto_rejected(self):
        with pytest.raises(ValidationError, match="at least one size dimension must be non-auto"):
            HtmlElement(**_html(width="auto", height="auto"))

    def test_zero_width_rejected(self):
        with pytest.raises(ValidationError, match="numeric width must be > 0"):
            HtmlElement(**_html(width=0, height=100))

    def test_negative_height_rejected(self):
        with pytest.raises(ValidationError, match="numeric height must be > 0"):
            HtmlElement(**_html(width=100, height=-5))

    def test_auto_width_numeric_height(self):
        el = HtmlElement(**_html(width="auto", height=50))
        assert el.width.is_auto
        assert el.height.static_value == 50

    def test_numeric_width_auto_height(self):
        el = HtmlElement(**_html(width=80, height="auto"))
        assert el.width.static_value == 80
        assert el.height.is_auto

    def test_oversized_values_allowed(self):
        el = HtmlElement(**_html(width=200, height=300))
        assert el.width.static_value == 200
        assert el.height.static_value == 300

    def test_negative_position_allowed(self):
        el = HtmlElement(**_html(position=[-50, -100]))
        assert el.position.static_value == (-50, -100)


# ── ImageElement ──────────────────────────────────────────────────


class TestImageElement:
    def test_valid(self):
        el = ImageElement(**_asset())
        assert el.image == Path("img.jpg")
        assert el.object_fit == "cover"

    def test_object_fit_contain(self):
        el = ImageElement(**_asset(object_fit="contain"))
        assert el.object_fit == "contain"

    def test_object_fit_fill(self):
        el = ImageElement(**_asset(object_fit="fill"))
        assert el.object_fit == "fill"

    def test_auto_size_without_object_fit(self):
        el = ImageElement(**_asset(width=100, height="auto", object_fit=None))
        assert el.object_fit is None

    def test_object_fit_required_when_both_numeric(self):
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageElement(**_asset(object_fit=None))

    def test_object_fit_forbidden_with_auto(self):
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageElement(**_asset(width=100, height="auto", object_fit="cover"))

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            ImageElement(**_asset(html="sneaky"))


# ── ImageSequenceElement ──────────────────────────────────────────


class TestImageSequenceElement:
    def test_valid(self):
        el = ImageSequenceElement(**_image_sequence())
        assert [p.name for p in el.image_sequence] == ["a.svg", "b.svg", "c.svg"]
        assert el.frame_distance == 400
        assert el.hold == 200

    def test_defaults(self):
        el = ImageSequenceElement(**_image_sequence())
        assert el.scroll_offset == 0
        assert el.fade_in == 0
        assert el.fade_out == 0
        assert el.object_fit is None

    def test_repeats_allowed(self):
        el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "b.svg", "b.svg", "c.svg"]))
        assert len(el.image_sequence) == 4
        assert el.image_sequence[1] == el.image_sequence[2]

    def test_empty_string_becomes_none(self):
        el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "", "b.svg"]))
        assert len(el.image_sequence) == 3
        assert el.image_sequence[0] is not None
        assert el.image_sequence[1] is None
        assert el.image_sequence[2] is not None

    def test_consecutive_empty_strings_allowed(self):
        el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", "", "", "b.svg"]))
        assert el.image_sequence[1] is None
        assert el.image_sequence[2] is None

    def test_empty_string_counts_toward_min_two(self):
        el = ImageSequenceElement(**_image_sequence(image_sequence=["a.svg", ""]))
        assert len(el.image_sequence) == 2

    def test_too_few_frames_rejected(self):
        with pytest.raises(ValidationError, match="image_sequence must contain at least 2 entries"):
            ImageSequenceElement(**_image_sequence(image_sequence=["a.svg"]))

    def test_zero_hold_rejected(self):
        with pytest.raises(ValidationError, match="hold must be > 0"):
            ImageSequenceElement(**_image_sequence(hold=0))

    def test_negative_hold_rejected(self):
        with pytest.raises(ValidationError, match="hold must be > 0"):
            ImageSequenceElement(**_image_sequence(hold=-50))

    def test_frame_distance_equal_to_hold_rejected(self):
        with pytest.raises(ValidationError, match=r"frame_distance .* must be > hold"):
            ImageSequenceElement(**_image_sequence(frame_distance=200, hold=200))

    def test_frame_distance_less_than_hold_rejected(self):
        with pytest.raises(ValidationError, match=r"frame_distance .* must be > hold"):
            ImageSequenceElement(**_image_sequence(frame_distance=100, hold=200))

    def test_negative_fade_in_rejected(self):
        with pytest.raises(ValidationError, match="fade_in must be >= 0"):
            ImageSequenceElement(**_image_sequence(fade_in=-1))

    def test_negative_fade_out_rejected(self):
        with pytest.raises(ValidationError, match="fade_out must be >= 0"):
            ImageSequenceElement(**_image_sequence(fade_out=-1))

    def test_zero_fade_in_allowed(self):
        el = ImageSequenceElement(**_image_sequence(fade_in=0))
        assert el.fade_in == 0

    def test_positive_fade_in_allowed(self):
        el = ImageSequenceElement(**_image_sequence(fade_in=150))
        assert el.fade_in == 150

    def test_object_fit_required_when_both_numeric(self):
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageSequenceElement(**_image_sequence(width=80, height=60))

    def test_object_fit_with_both_numeric(self):
        el = ImageSequenceElement(**_image_sequence(width=80, height=60, object_fit="cover"))
        assert el.object_fit == "cover"

    def test_object_fit_forbidden_with_auto(self):
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageSequenceElement(**_image_sequence(object_fit="cover"))

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            ImageSequenceElement(**_image_sequence(image="sneaky.png"))

    def test_inherits_animated_position(self):
        el = ImageSequenceElement(**_image_sequence(position={"keyframes": [(0, (0, 0)), (1000, (50, 50))]}))
        assert el.position.is_animated


# ── HtmlElement ───────────────────────────────────────────────────


class TestHtmlElement:
    def test_valid(self):
        el = HtmlElement(**_html())
        assert el.html == "<p>hi</p>"

    def test_missing_html_rejected(self):
        data = _html()
        del data["html"]
        with pytest.raises(ValidationError):
            HtmlElement(**data)


# ── IframeElement ─────────────────────────────────────────────────


class TestIframeElement:
    def test_valid(self):
        el = IframeElement(**_iframe())
        assert el.iframe_html == "<!doctype html><p>hi</p>"

    def test_default_decorations(self):
        el = IframeElement(**_iframe())
        assert el.border_width == 0
        assert el.border_color == "#000000"
        assert el.shadow_size == 0
        assert el.shadow_color == "#000000"

    def test_custom_border(self):
        el = IframeElement(**_iframe(border_width=4, border_color="#333"))
        assert el.border_width == 4
        assert el.border_color == "#333"

    def test_custom_shadow(self):
        el = IframeElement(**_iframe(shadow_size=12, shadow_color="rgba(0,0,0,0.3)"))
        assert el.shadow_size == 12
        assert el.shadow_color == "rgba(0,0,0,0.3)"

    def test_negative_border_width_rejected(self):
        with pytest.raises(ValidationError, match="border_width must be >= 0"):
            IframeElement(**_iframe(border_width=-1))

    def test_negative_shadow_size_rejected(self):
        with pytest.raises(ValidationError, match="shadow_size must be >= 0"):
            IframeElement(**_iframe(shadow_size=-5))

    def test_missing_iframe_html_rejected(self):
        data = _iframe()
        del data["iframe_html"]
        with pytest.raises(ValidationError):
            IframeElement(**data)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            IframeElement(**_iframe(bogus="x"))

    def test_frozen(self):
        el = IframeElement(**_iframe())
        with pytest.raises(ValidationError):
            el.iframe_html = "changed"

    def test_inherits_size_validation(self):
        with pytest.raises(ValidationError, match="at least one size dimension must be non-auto"):
            IframeElement(**_iframe(width="auto", height="auto"))

    def test_inherits_animated_opacity(self):
        kfs = {"keyframes": [(0, 0.0), (1000, 1.0)]}
        el = IframeElement(**_iframe(opacity=kfs))
        assert el.opacity.is_animated


# ── MarkdownElement ───────────────────────────────────────────────


class TestMarkdownElement:
    def test_valid(self):
        el = MarkdownElement(**_md())
        assert el.markdown == "# Hi"

    def test_default_color(self):
        el = MarkdownElement(**_md())
        assert el.color == "#808080"

    def test_custom_color(self):
        el = MarkdownElement(**_md(color="#fff"))
        assert el.color == "#fff"


# ── MermaidElement ───────────────────────────────────────────────


class TestMermaidElement:
    def test_valid(self):
        el = MermaidElement(**_mermaid())
        assert el.mermaid == "graph LR\n  A --> B"

    def test_frozen(self):
        el = MermaidElement(**_mermaid())
        with pytest.raises(ValidationError):
            el.mermaid = "changed"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            MermaidElement(**_mermaid(html="sneaky"))

    def test_auto_height(self):
        el = MermaidElement(**_mermaid(width=80, height="auto"))
        assert el.width.static_value == 80
        assert el.height.is_auto

    def test_both_numeric_size(self):
        el = MermaidElement(**_mermaid(width=40, height=50))
        assert el.width.static_value == 40
        assert el.height.static_value == 50

    def test_size_validation_applies(self):
        with pytest.raises(ValidationError, match="at least one size dimension must be non-auto"):
            MermaidElement(**_mermaid(width="auto", height="auto"))
