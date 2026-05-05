"""Tests for scrollimation IR models — structural validation via pydantic."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    ImageElement,
    InitialState,
    Keyframe,
    MarkdownElement,
    MermaidElement,
    SlideIR,
)
from scrolly.slide.ir.scrollimation import ScrollimationIR

# ── helpers ────────────────────────────────────────────────────────


def _html_element(**overrides) -> dict:
    base = {"name": "L", "html": "<p>hi</p>", "position": [0, 0], "size": [100, 100]}
    return {**base, **overrides}


def _image_element(**overrides) -> dict:
    base = {
        "name": "L",
        "image": "img.jpg",
        "position": [0, 0],
        "size": [100, 100],
        "object_fit": "cover",
    }
    return {**base, **overrides}


def _md_element(**overrides) -> dict:
    base = {"name": "L", "markdown": "# Hi", "position": [0, 0], "size": [80, "auto"]}
    return {**base, **overrides}


def _anim(element: dict, **overrides) -> dict:
    """Build an ElementAnimation dict wrapping an element dict."""
    base = {"element": element}
    return {**base, **overrides}


def _html_anim(**overrides) -> dict:
    """Shortcut: ElementAnimation wrapping a default HtmlElement."""
    el_overrides = {}
    anim_overrides = {}
    element_fields = {"name", "html", "position", "size", "anchor"}
    for k, v in overrides.items():
        if k in element_fields:
            el_overrides[k] = v
        else:
            anim_overrides[k] = v
    return _anim(_html_element(**el_overrides), **anim_overrides)


def _image_anim(**overrides) -> dict:
    """Shortcut: ElementAnimation wrapping a default ImageElement."""
    el_overrides = {}
    anim_overrides = {}
    element_fields = {"name", "image", "position", "size", "object_fit", "anchor"}
    for k, v in overrides.items():
        if k in element_fields:
            el_overrides[k] = v
        else:
            anim_overrides[k] = v
    return _anim(_image_element(**el_overrides), **anim_overrides)


def _md_anim(**overrides) -> dict:
    """Shortcut: ElementAnimation wrapping a default MarkdownElement."""
    el_overrides = {}
    anim_overrides = {}
    element_fields = {"name", "markdown", "position", "size", "anchor", "color"}
    for k, v in overrides.items():
        if k in element_fields:
            el_overrides[k] = v
        else:
            anim_overrides[k] = v
    return _anim(_md_element(**el_overrides), **anim_overrides)


def _mermaid_element(**overrides) -> dict:
    base = {"name": "L", "mermaid": "graph LR\n  A --> B", "position": [10, 10], "size": [80, "auto"]}
    return {**base, **overrides}


def _mermaid_anim(**overrides) -> dict:
    """Shortcut: ElementAnimation wrapping a default MermaidElement."""
    el_overrides = {}
    anim_overrides = {}
    element_fields = {"name", "mermaid", "position", "size", "anchor"}
    for k, v in overrides.items():
        if k in element_fields:
            el_overrides[k] = v
        else:
            anim_overrides[k] = v
    return _anim(_mermaid_element(**el_overrides), **anim_overrides)


def _slide(**overrides) -> dict:
    base = {
        "title": "T",
        "scroll_range": 1000,
        "elements": [_html_anim()],
    }
    return {**base, **overrides}


# ── InitialState ──────────────────────────────────────────────────


class TestInitialState:
    def test_defaults(self) -> None:
        s = InitialState()
        assert s.opacity == 1.0
        assert s.translate == (0.0, 0.0)
        assert s.scale == 1.0
        assert s.rotate == 0.0

    def test_custom_values(self) -> None:
        s = InitialState(opacity=0.5, translate=(10, -20), scale=2.0, rotate=45)
        assert s.opacity == 0.5
        assert s.translate == (10, -20)
        assert s.scale == 2.0
        assert s.rotate == 45


# ── Keyframe ──────────────────────────────────────────────────────


class TestKeyframe:
    def test_sparse_keyframe(self) -> None:
        kf = Keyframe(at=100, opacity=0.5)
        assert kf.at == 100
        assert kf.opacity == 0.5
        assert kf.translate is None
        assert kf.scale is None
        assert kf.rotate is None

    def test_all_properties(self) -> None:
        kf = Keyframe(at=0, opacity=1, translate=(50, 50), scale=2, rotate=90)
        assert kf.translate == (50, 50)


# ── Element types ────────────────────────────────────────────────


class TestHtmlElement:
    def test_valid_construction(self) -> None:
        element = HtmlElement(**_html_element())
        assert element.name == "L"
        assert element.html == "<p>hi</p>"
        assert element.position == (0, 0)
        assert element.size == (100, 100)

    def test_defaults(self) -> None:
        element = HtmlElement(**_html_element())
        assert element.anchor == (0.0, 0.0)

    def test_missing_html_rejected(self) -> None:
        data = _html_element()
        del data["html"]
        with pytest.raises(ValidationError):
            HtmlElement(**data)

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            HtmlElement(**_html_element(asset="sneaky.jpg"))


class TestImageElement:
    def test_valid_construction(self) -> None:
        element = ImageElement(**_image_element())
        assert element.image == Path("img.jpg")
        assert element.object_fit == "cover"

    def test_object_fit_contain(self) -> None:
        element = ImageElement(**_image_element(object_fit="contain"))
        assert element.object_fit == "contain"

    def test_object_fit_fill(self) -> None:
        element = ImageElement(**_image_element(object_fit="fill"))
        assert element.object_fit == "fill"

    def test_auto_size_without_object_fit(self) -> None:
        element = ImageElement(**_image_element(size=[100, "auto"], object_fit=None))
        assert element.size == (100, "auto")
        assert element.object_fit is None

    def test_object_fit_required_when_both_numeric(self) -> None:
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageElement(**_image_element(object_fit=None))

    def test_object_fit_forbidden_with_auto_dim(self) -> None:
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageElement(**_image_element(size=[100, "auto"], object_fit="cover"))

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            ImageElement(**_image_element(html="sneaky"))


class TestMarkdownElement:
    def test_valid_construction(self) -> None:
        element = MarkdownElement(**_md_element())
        assert element.markdown == "# Hi"
        assert element.size == (80, "auto")

    def test_missing_markdown_rejected(self) -> None:
        data = _md_element()
        del data["markdown"]
        with pytest.raises(ValidationError):
            MarkdownElement(**data)


class TestMermaidElement:
    def test_valid_construction(self) -> None:
        element = MermaidElement(**_mermaid_element())
        assert element.mermaid == "graph LR\n  A --> B"
        assert element.size == (80, "auto")

    def test_missing_mermaid_rejected(self) -> None:
        data = _mermaid_element()
        del data["mermaid"]
        with pytest.raises(ValidationError):
            MermaidElement(**data)

    def test_in_slide(self) -> None:
        slide = ScrollimationIR(**_slide(elements=[_mermaid_anim()]))
        assert isinstance(slide.elements[0].element, MermaidElement)

    def test_mixed_element_types(self) -> None:
        slide = ScrollimationIR(**_slide(elements=[_html_anim(name="a"), _mermaid_anim(name="b")]))
        assert isinstance(slide.elements[0].element, HtmlElement)
        assert isinstance(slide.elements[1].element, MermaidElement)


# ── Size validation ───────────────────────────────────────────────


class TestSizeValidation:
    def test_auto_auto_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one size dimension must be numeric"):
            HtmlElement(**_html_element(size=["auto", "auto"]))

    def test_zero_width_rejected(self) -> None:
        with pytest.raises(ValidationError, match="width must be > 0"):
            HtmlElement(**_html_element(size=[0, 100]))

    def test_negative_height_rejected(self) -> None:
        with pytest.raises(ValidationError, match="height must be > 0"):
            HtmlElement(**_html_element(size=[100, -5]))

    def test_auto_width_numeric_height(self) -> None:
        element = HtmlElement(**_html_element(size=["auto", 50]))
        assert element.size == ("auto", 50)

    def test_numeric_width_auto_height(self) -> None:
        element = HtmlElement(**_html_element(size=[80, "auto"]))
        assert element.size == (80, "auto")

    def test_oversized_values_allowed(self) -> None:
        element = HtmlElement(**_html_element(size=[200, 300]))
        assert element.size == (200, 300)

    def test_negative_position_allowed(self) -> None:
        element = HtmlElement(**_html_element(position=[-50, -100]))
        assert element.position == (-50, -100)

    def test_position_beyond_100_allowed(self) -> None:
        element = HtmlElement(**_html_element(position=[150, 200]))
        assert element.position == (150, 200)


# ── ScrollimationIR ────────────────────────────────────────────


class TestScrollimationIR:
    def test_is_slide_ir(self) -> None:
        assert issubclass(ScrollimationIR, SlideIR)

    def test_valid_construction(self) -> None:
        slide = ScrollimationIR(**_slide())
        assert slide.title == "T"
        assert slide.scroll_range == 1000
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"
        assert len(slide.elements) == 1

    def test_defaults(self) -> None:
        slide = ScrollimationIR(**_slide())
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"

    def test_scroll_range_zero_valid(self) -> None:
        slide = ScrollimationIR(**_slide(scroll_range=0))
        assert slide.scroll_range == 0

    def test_negative_scroll_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scroll_range must be >= 0"):
            ScrollimationIR(**_slide(scroll_range=-1))

    def test_empty_elements_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one element"):
            ScrollimationIR(**_slide(elements=[]))

    def test_duplicate_element_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate element name"):
            ScrollimationIR(
                **_slide(
                    elements=[
                        _html_anim(name="dup"),
                        _html_anim(name="dup", html="<p>other</p>"),
                    ]
                )
            )

    def test_keyframe_outside_scroll_range_rejected(self) -> None:
        anim = _html_anim(keyframes=[{"at": 1500, "opacity": 1}])
        with pytest.raises(ValidationError, match="outside"):
            ScrollimationIR(**_slide(scroll_range=1000, elements=[anim]))

    def test_negative_keyframe_rejected(self) -> None:
        anim = _html_anim(keyframes=[{"at": -1, "opacity": 1}])
        with pytest.raises(ValidationError, match="outside"):
            ScrollimationIR(**_slide(elements=[anim]))

    def test_duplicate_keyframe_at_for_same_property_rejected(self) -> None:
        anim = _html_anim(
            keyframes=[
                {"at": 100, "opacity": 0},
                {"at": 100, "opacity": 1},
            ]
        )
        with pytest.raises(ValidationError, match="duplicate keyframe"):
            ScrollimationIR(**_slide(elements=[anim]))

    def test_same_at_different_properties_allowed(self) -> None:
        anim = _html_anim(
            keyframes=[
                {"at": 100, "opacity": 0},
                {"at": 100, "scale": 2},
            ]
        )
        slide = ScrollimationIR(**_slide(elements=[anim]))
        assert len(slide.elements[0].keyframes) == 2

    def test_empty_keyframes_valid(self) -> None:
        anim = _html_anim(keyframes=[])
        slide = ScrollimationIR(**_slide(elements=[anim]))
        assert slide.elements[0].keyframes == []

    def test_initial_scroll_position_beyond_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="initial_scroll_position"):
            ScrollimationIR(**_slide(scroll_range=100, initial_scroll_position=200))

    def test_multiple_element_types(self) -> None:
        slide = ScrollimationIR(
            **_slide(
                elements=[
                    _image_anim(name="bg"),
                    _html_anim(name="sep"),
                    _md_anim(name="caption"),
                ]
            )
        )
        assert isinstance(slide.elements[0].element, ImageElement)
        assert isinstance(slide.elements[1].element, HtmlElement)
        assert isinstance(slide.elements[2].element, MarkdownElement)

    def test_initial_omitted_uses_defaults(self) -> None:
        anim = _html_anim()
        slide = ScrollimationIR(**_slide(elements=[anim]))
        assert slide.elements[0].initial.opacity == 1.0
        assert slide.elements[0].initial.translate == (0.0, 0.0)

    def test_keyframe_at_zero_present_alongside_initial(self) -> None:
        anim = _html_anim(
            initial={"opacity": 0.5},
            keyframes=[{"at": 0, "opacity": 1.0}],
        )
        slide = ScrollimationIR(**_slide(elements=[anim]))
        assert slide.elements[0].initial.opacity == 0.5
        assert slide.elements[0].keyframes[0].opacity == 1.0

    def test_snap_positions_default_empty(self) -> None:
        slide = ScrollimationIR(**_slide())
        assert slide.snap_positions == ()

    def test_snap_positions_accepted(self) -> None:
        slide = ScrollimationIR(**_slide(scroll_range=1000, snap_positions=[0, 500, 1000]))
        assert slide.snap_positions == (0, 500, 1000)

    def test_snap_positions_exceeds_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="snap_positions"):
            ScrollimationIR(**_slide(scroll_range=100, snap_positions=[0, 200]))

    def test_snap_positions_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="snap_positions"):
            ScrollimationIR(**_slide(snap_positions=[-1]))


# ── from_file ─────────────────────────────────────────────────────


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


MINIMAL_JSON5 = """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
"""


class TestFromFile:
    def test_returns_scrollimation_ir(self, tmp_path: Path) -> None:
        src = _write(tmp_path, "s.scrollimation.json", MINIMAL_JSON5)
        ir = ScrollimationIR.from_file(src)
        assert isinstance(ir, ScrollimationIR)
        assert ir.title == "T"
        assert ir.scroll_range == 100

    def test_asset_paths_resolved_to_absolute(self, tmp_path: Path) -> None:
        _write(tmp_path, "hero.jpg", "fake")
        src = _write(
            tmp_path,
            "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { name: "bg", image: "hero.jpg", position: [0, 0], size: [100, 100], object_fit: "cover" } },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert ir.elements[0].element.image.is_absolute()

    def test_slide_type_property(self, tmp_path: Path) -> None:
        src = _write(tmp_path, "s.scrollimation.json", MINIMAL_JSON5)
        ir = ScrollimationIR.from_file(src)
        assert ir.slide_type == "scrollimation-json"

    def test_missing_file_raises(self) -> None:
        from scrolly.errors import SlideSourceError

        with pytest.raises(SlideSourceError, match="not found"):
            ScrollimationIR.from_file(Path("/no/such/file.scrollimation.json"))
