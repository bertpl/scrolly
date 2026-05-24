"""Tests for scrollimation IR models — structural validation via pydantic."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from scrolly.slide.ir import (
    AnimatedScalar,
    AnimatedVec2,
    HtmlElement,
    ImageElement,
    MarkdownElement,
    MermaidElement,
    ScalarKeyframes,
    SlideIR,
    Vec2Keyframes,
)
from scrolly.slide.ir.slide import SlideIR

# ── helpers ────────────────────────────────────────────────────────


def _html_element(**overrides) -> dict:
    base = {"name": "L", "html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}
    return {**base, **overrides}


def _image_element(**overrides) -> dict:
    base = {
        "name": "L",
        "image": "img.jpg",
        "position": [0, 0],
        "width": 100,
        "height": 100,
        "object_fit": "cover",
    }
    return {**base, **overrides}


def _md_element(**overrides) -> dict:
    base = {"name": "L", "markdown": "# Hi", "position": [0, 0], "width": 80, "height": "auto"}
    return {**base, **overrides}


def _mermaid_element(**overrides) -> dict:
    base = {"name": "L", "mermaid": "graph LR\n  A --> B", "position": [10, 10], "width": 80, "height": "auto"}
    return {**base, **overrides}


def _slide(**overrides) -> dict:
    base = {
        "title": "T",
        "scroll_range": 1000,
        "elements": [_html_element()],
    }
    return {**base, **overrides}


# ── Element types ────────────────────────────────────────────────


class TestHtmlElement:
    def test_valid_construction(self) -> None:
        element = HtmlElement(**_html_element())
        assert element.name == "L"
        assert element.html == "<p>hi</p>"
        assert element.position.static_value == (0, 0)
        assert element.width.static_value == 100
        assert element.height.static_value == 100

    def test_defaults(self) -> None:
        element = HtmlElement(**_html_element())
        assert element.anchor.static_value == (0.0, 0.0)
        assert element.opacity.static_value == 1.0
        assert element.scale.static_value == 1.0
        assert element.angle.static_value == 0.0

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
        element = ImageElement(**_image_element(width=100, height="auto", object_fit=None))
        assert element.height.is_auto
        assert element.object_fit is None

    def test_object_fit_required_when_both_numeric(self) -> None:
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageElement(**_image_element(object_fit=None))

    def test_object_fit_forbidden_with_auto_dim(self) -> None:
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageElement(**_image_element(width=100, height="auto", object_fit="cover"))

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            ImageElement(**_image_element(html="sneaky"))


class TestMarkdownElement:
    def test_valid_construction(self) -> None:
        element = MarkdownElement(**_md_element())
        assert element.markdown == "# Hi"
        assert element.width.static_value == 80
        assert element.height.is_auto

    def test_missing_markdown_rejected(self) -> None:
        data = _md_element()
        del data["markdown"]
        with pytest.raises(ValidationError):
            MarkdownElement(**data)


class TestMermaidElement:
    def test_valid_construction(self) -> None:
        element = MermaidElement(**_mermaid_element())
        assert element.mermaid == "graph LR\n  A --> B"
        assert element.width.static_value == 80
        assert element.height.is_auto

    def test_missing_mermaid_rejected(self) -> None:
        data = _mermaid_element()
        del data["mermaid"]
        with pytest.raises(ValidationError):
            MermaidElement(**data)

    def test_in_slide(self) -> None:
        slide = SlideIR(**_slide(elements=[_mermaid_element()]))
        assert isinstance(slide.elements[0], MermaidElement)

    def test_mixed_element_types(self) -> None:
        slide = SlideIR(**_slide(elements=[_html_element(name="a"), _mermaid_element(name="b")]))
        assert isinstance(slide.elements[0], HtmlElement)
        assert isinstance(slide.elements[1], MermaidElement)


# ── Size validation ───────────────────────────────────────────────


class TestSizeValidation:
    def test_auto_auto_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one size dimension must be non-auto"):
            HtmlElement(**_html_element(width="auto", height="auto"))

    def test_zero_width_rejected(self) -> None:
        with pytest.raises(ValidationError, match="numeric width must be > 0"):
            HtmlElement(**_html_element(width=0, height=100))

    def test_negative_height_rejected(self) -> None:
        with pytest.raises(ValidationError, match="numeric height must be > 0"):
            HtmlElement(**_html_element(width=100, height=-5))

    def test_auto_width_numeric_height(self) -> None:
        element = HtmlElement(**_html_element(width="auto", height=50))
        assert element.width.is_auto
        assert element.height.static_value == 50

    def test_numeric_width_auto_height(self) -> None:
        element = HtmlElement(**_html_element(width=80, height="auto"))
        assert element.width.static_value == 80
        assert element.height.is_auto

    def test_oversized_values_allowed(self) -> None:
        element = HtmlElement(**_html_element(width=200, height=300))
        assert element.width.static_value == 200
        assert element.height.static_value == 300

    def test_negative_position_allowed(self) -> None:
        element = HtmlElement(**_html_element(position=[-50, -100]))
        assert element.position.static_value == (-50, -100)

    def test_position_beyond_100_allowed(self) -> None:
        element = HtmlElement(**_html_element(position=[150, 200]))
        assert element.position.static_value == (150, 200)


# ── SlideIR ────────────────────────────────────────────


class TestSlideIR:
    def test_is_slide_ir(self) -> None:
        assert issubclass(SlideIR, SlideIR)

    def test_valid_construction(self) -> None:
        slide = SlideIR(**_slide())
        assert slide.title == "T"
        assert slide.scroll_range == 1000
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"
        assert len(slide.elements) == 1

    def test_defaults(self) -> None:
        slide = SlideIR(**_slide())
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"
        assert slide.reverse is False

    def test_reverse_true(self) -> None:
        slide = SlideIR(**_slide(reverse=True))
        assert slide.reverse is True

    def test_reverse_false_explicit(self) -> None:
        slide = SlideIR(**_slide(reverse=False))
        assert slide.reverse is False

    def test_scroll_range_zero_valid(self) -> None:
        slide = SlideIR(**_slide(scroll_range=0))
        assert slide.scroll_range == 0

    def test_negative_scroll_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scroll_range must be >= 0"):
            SlideIR(**_slide(scroll_range=-1))

    def test_empty_elements_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one element"):
            SlideIR(**_slide(elements=[]))

    def test_duplicate_element_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate element name"):
            SlideIR(
                **_slide(
                    elements=[
                        _html_element(name="dup"),
                        _html_element(name="dup", html="<p>other</p>"),
                    ]
                )
            )

    def test_initial_scroll_position_beyond_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="initial_scroll_position"):
            SlideIR(**_slide(scroll_range=100, initial_scroll_position=200))

    def test_multiple_element_types(self) -> None:
        slide = SlideIR(
            **_slide(
                elements=[
                    _image_element(name="bg"),
                    _html_element(name="sep"),
                    _md_element(name="caption"),
                ]
            )
        )
        assert isinstance(slide.elements[0], ImageElement)
        assert isinstance(slide.elements[1], HtmlElement)
        assert isinstance(slide.elements[2], MarkdownElement)

    def test_element_with_animated_opacity(self) -> None:
        el = _html_element(opacity={"keyframes": [(0, 0.0), (1000, 1.0)]})
        slide = SlideIR(**_slide(elements=[el]))
        assert slide.elements[0].opacity.is_animated
        assert slide.elements[0].opacity.keyframes == [(0, 0.0), (1000, 1.0)]

    def test_element_with_animated_position(self) -> None:
        el = _html_element(position={"keyframes": [(0, (0, 0)), (1000, (50, 50))]})
        slide = SlideIR(**_slide(elements=[el]))
        assert slide.elements[0].position.is_animated

    def test_element_with_static_opacity(self) -> None:
        el = _html_element(opacity=0.5)
        slide = SlideIR(**_slide(elements=[el]))
        assert not slide.elements[0].opacity.is_animated
        assert slide.elements[0].opacity.static_value == 0.5

    def test_snap_positions_default_empty(self) -> None:
        slide = SlideIR(**_slide())
        assert slide.snap_positions == ()

    def test_snap_positions_accepted(self) -> None:
        slide = SlideIR(**_slide(scroll_range=1000, snap_positions=[0, 500, 1000]))
        assert slide.snap_positions == (0, 500, 1000)

    def test_snap_positions_exceeds_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="snap_positions"):
            SlideIR(**_slide(scroll_range=100, snap_positions=[0, 200]))

    def test_snap_positions_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="snap_positions"):
            SlideIR(**_slide(snap_positions=[-1]))


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
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
"""


class TestFromFile:
    def test_returns_scrollimation_ir(self, tmp_path: Path) -> None:
        src = _write(tmp_path, "s.slide.json", MINIMAL_JSON5)
        ir = SlideIR.from_file(src)
        assert isinstance(ir, SlideIR)
        assert ir.title == "T"
        assert ir.scroll_range == 100

    def test_asset_paths_resolved_to_absolute(self, tmp_path: Path) -> None:
        _write(tmp_path, "hero.jpg", "fake")
        src = _write(
            tmp_path,
            "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "bg", image: "hero.jpg", position: [0, 0], width: 100, height: 100, object_fit: "cover" },
  ],
}
""",
        )
        ir = SlideIR.from_file(src)
        assert ir.elements[0].image.is_absolute()

    def test_slide_type_property(self, tmp_path: Path) -> None:
        src = _write(tmp_path, "s.slide.json", MINIMAL_JSON5)
        ir = SlideIR.from_file(src)
        assert ir.slide_type == "slide-json"

    def test_missing_file_raises(self) -> None:
        from scrolly.errors import SlideSourceError

        with pytest.raises(SlideSourceError, match="not found"):
            SlideIR.from_file(Path("/no/such/file.slide.json"))


class TestSubstrateDefaults:
    """Substrate-level defaults landed in v0.2.0 (item C / D)."""

    def test_scroll_range_defaults_to_auto(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(title="T", elements=[_html_element()])

        # --- assert -----------------------------
        assert ir.scroll_range == "auto"

    def test_scroll_range_accepts_explicit_auto(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(title="T", scroll_range="auto", elements=[_html_element()])

        # --- assert -----------------------------
        assert ir.scroll_range == "auto"

    def test_scroll_range_accepts_numeric(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(title="T", scroll_range=500, elements=[_html_element()])

        # --- assert -----------------------------
        assert ir.scroll_range == 500.0

    def test_scroll_range_rejects_negative_number(self) -> None:
        # --- arrange / act / assert -------------
        with pytest.raises(ValidationError, match=r"scroll_range must be >= 0 or 'auto'"):
            SlideIR(title="T", scroll_range=-1, elements=[_html_element()])

    def test_scroll_range_rejects_unknown_string(self) -> None:
        # --- arrange / act / assert -------------
        with pytest.raises(ValidationError):
            SlideIR(title="T", scroll_range="huge", elements=[_html_element()])

    def test_auto_skips_initial_scroll_position_upper_bound(self) -> None:
        # --- arrange / act ----------------------
        # With scroll_range="auto" the upper bound isn't statically known,
        # so an initial_scroll_position that would exceed any reasonable
        # numeric range is still accepted.
        ir = SlideIR(
            title="T",
            scroll_range="auto",
            initial_scroll_position=99999,
            elements=[_html_element()],
        )

        # --- assert -----------------------------
        assert ir.initial_scroll_position == 99999

    def test_auto_skips_snap_position_upper_bound(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(
            title="T",
            scroll_range="auto",
            snap_positions=(0, 5000, 99999),
            elements=[_html_element()],
        )

        # --- assert -----------------------------
        assert ir.snap_positions == (0, 5000, 99999)

    def test_auto_still_rejects_negative_snap_positions(self) -> None:
        # --- arrange / act / assert -------------
        with pytest.raises(ValidationError, match=r"snap_positions value -1 must be >= 0"):
            SlideIR(
                title="T",
                scroll_range="auto",
                snap_positions=(-1,),
                elements=[_html_element()],
            )

    def test_font_scale_defaults_to_one(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(title="T", scroll_range=100, elements=[_html_element()])

        # --- assert -----------------------------
        assert ir.font_scale == 1.0

    def test_font_scale_accepts_positive_values(self) -> None:
        # --- arrange / act ----------------------
        ir = SlideIR(title="T", scroll_range=100, font_scale=1.5, elements=[_html_element()])

        # --- assert -----------------------------
        assert ir.font_scale == 1.5

    def test_font_scale_rejects_zero_and_negative(self) -> None:
        # --- arrange / act / assert -------------
        with pytest.raises(ValidationError, match=r"font_scale must be > 0"):
            SlideIR(title="T", scroll_range=100, font_scale=0, elements=[_html_element()])
        with pytest.raises(ValidationError, match=r"font_scale must be > 0"):
            SlideIR(title="T", scroll_range=100, font_scale=-1, elements=[_html_element()])
