"""Tests for SlideElement, element types, and shared validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.slide.ir import (
    AnimatedScalar,
    AnimatedVec2,
    HtmlElement,
    ImageElement,
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
