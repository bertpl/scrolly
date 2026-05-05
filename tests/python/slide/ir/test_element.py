"""Tests for SlideElement, element types, ElementAnimation, and shared validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    ImageElement,
    InitialState,
    Keyframe,
    MarkdownElement,
    MermaidElement,
    SlideElement,
)

# ── helpers ───────────────────────────────────────────────────────


def _html(**overrides) -> dict:
    base = {"html": "<p>hi</p>", "position": [0, 0], "size": [100, 100]}
    return {**base, **overrides}


def _asset(**overrides) -> dict:
    base = {"image": "img.jpg", "position": [0, 0], "size": [100, 100], "object_fit": "cover"}
    return {**base, **overrides}


def _md(**overrides) -> dict:
    base = {"markdown": "# Hi", "position": [10, 30], "size": [80, "auto"]}
    return {**base, **overrides}


def _mermaid(**overrides) -> dict:
    base = {"mermaid": "graph LR\n  A --> B", "position": [10, 10], "size": [80, "auto"]}
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

    def test_default_transform_origin(self):
        el = HtmlElement(**_html())
        assert el.transform_origin == (50.0, 50.0)

    def test_custom_transform_origin(self):
        el = HtmlElement(**_html(transform_origin=[0, 100]))
        assert el.transform_origin == (0, 100)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            HtmlElement(**_html(bogus="x"))


# ── Size validation ───────────────────────────────────────────────


class TestSizeValidation:
    def test_auto_auto_rejected(self):
        with pytest.raises(ValidationError, match="at least one size dimension must be numeric"):
            HtmlElement(**_html(size=["auto", "auto"]))

    def test_zero_width_rejected(self):
        with pytest.raises(ValidationError, match="width must be > 0"):
            HtmlElement(**_html(size=[0, 100]))

    def test_negative_height_rejected(self):
        with pytest.raises(ValidationError, match="height must be > 0"):
            HtmlElement(**_html(size=[100, -5]))

    def test_auto_width_numeric_height(self):
        el = HtmlElement(**_html(size=["auto", 50]))
        assert el.size == ("auto", 50)

    def test_numeric_width_auto_height(self):
        el = HtmlElement(**_html(size=[80, "auto"]))
        assert el.size == (80, "auto")

    def test_oversized_values_allowed(self):
        el = HtmlElement(**_html(size=[200, 300]))
        assert el.size == (200, 300)

    def test_negative_position_allowed(self):
        el = HtmlElement(**_html(position=[-50, -100]))
        assert el.position == (-50, -100)


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
        el = ImageElement(**_asset(size=[100, "auto"], object_fit=None))
        assert el.object_fit is None

    def test_object_fit_required_when_both_numeric(self):
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageElement(**_asset(object_fit=None))

    def test_object_fit_forbidden_with_auto(self):
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageElement(**_asset(size=[100, "auto"], object_fit="cover"))

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
        el = MermaidElement(**_mermaid(size=[80, "auto"]))
        assert el.size == (80, "auto")

    def test_both_numeric_size(self):
        el = MermaidElement(**_mermaid(size=[40, 50]))
        assert el.size == (40, 50)

    def test_size_validation_applies(self):
        with pytest.raises(ValidationError, match="at least one size dimension must be numeric"):
            MermaidElement(**_mermaid(size=["auto", "auto"]))


# ── InitialState ──────────────────────────────────────────────────


class TestInitialState:
    def test_defaults(self):
        s = InitialState()
        assert s.opacity == 1.0
        assert s.translate == (0.0, 0.0)
        assert s.scale == 1.0
        assert s.rotate == 0.0

    def test_custom_values(self):
        s = InitialState(opacity=0.5, translate=(10, -20), scale=2.0, rotate=45)
        assert s.opacity == 0.5
        assert s.translate == (10, -20)


# ── Keyframe ──────────────────────────────────────────────────────


class TestKeyframe:
    def test_sparse(self):
        kf = Keyframe(at=100, opacity=0.5)
        assert kf.at == 100
        assert kf.opacity == 0.5
        assert kf.translate is None
        assert kf.scale is None
        assert kf.rotate is None

    def test_all_properties(self):
        kf = Keyframe(at=0, opacity=1, translate=(50, 50), scale=2, rotate=90)
        assert kf.translate == (50, 50)


# ── ElementAnimation ─────────────────────────────────────────────


class TestElementAnimation:
    def test_wraps_element(self):
        el = HtmlElement(**_html(name="L"))
        anim = ElementAnimation(element=el)
        assert anim.element is el
        assert anim.initial == InitialState()
        assert anim.keyframes == []

    def test_with_animation(self):
        el = ImageElement(**_asset(name="bg"))
        anim = ElementAnimation(
            element=el,
            initial=InitialState(opacity=0),
            keyframes=[Keyframe(at=0, opacity=0), Keyframe(at=500, opacity=1)],
        )
        assert anim.initial.opacity == 0
        assert len(anim.keyframes) == 2

    def test_frozen(self):
        el = HtmlElement(**_html())
        anim = ElementAnimation(element=el)
        with pytest.raises(ValidationError):
            anim.keyframes = []

    def test_element_types_discriminated(self):
        for el, cls in [
            (HtmlElement(**_html()), HtmlElement),
            (ImageElement(**_asset()), ImageElement),
            (MarkdownElement(**_md()), MarkdownElement),
            (MermaidElement(**_mermaid()), MermaidElement),
        ]:
            anim = ElementAnimation(element=el)
            assert isinstance(anim.element, cls)
