"""Tests for slide JSON5 parsing — file -> pydantic IR."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import HtmlElement, IframeElement, ImageElement, MarkdownElement, parse_json5_ir
from scrolly.slide.ir.slide import SlideIR


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
"""


# ── Happy path ────────────────────────────────────────────────────


class TestParsing:
    def test_minimal(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.slide.json", MINIMAL)
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert slide.title == "T"
        assert slide.scroll_range == 1000
        assert len(slide.elements) == 1
        assert isinstance(slide.elements[0], HtmlElement)

    def test_defaults_applied(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.slide.json", MINIMAL)
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"

    def test_all_three_element_types(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "Multi",
  scroll_range: 500,
  elements: [
    { name: "bg", image: "hero.jpg", position: [0, 0], width: 100, height: 120, object_fit: "cover" },
    { name: "sep", html: "<div></div>", position: [0, 0], width: 100, height: 100 },
    { name: "txt", markdown: "# Hi", position: [10, 40], width: 80, height: "auto" },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert isinstance(slide.elements[0], ImageElement)
        assert isinstance(slide.elements[1], HtmlElement)
        assert isinstance(slide.elements[2], MarkdownElement)

    def test_iframe_element_parsed(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      name: "frame",
      iframe_html: "<!doctype html><p>hi</p>",
      position: [10, 10],
      width: 80,
      height: 80,
      border_width: 2,
      border_color: "#333",
      shadow_size: 12,
      shadow_color: "rgba(0,0,0,0.3)",
    },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert isinstance(slide.elements[0], IframeElement)
        el = slide.elements[0]
        assert el.iframe_html == "<!doctype html><p>hi</p>"
        assert el.border_width == 2
        assert el.border_color == "#333"
        assert el.shadow_size == 12
        assert el.shadow_color == "rgba(0,0,0,0.3)"

    def test_animated_opacity_parsed(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    {
      name: "L",
      html: "<p>hi</p>",
      position: [0, 0],
      width: 100,
      height: 100,
      opacity: { keyframes: [[0, 0], [500, 1], [1000, 0]] },
    },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        el = slide.elements[0]
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(0, 0), (500, 1), (1000, 0)]

    def test_animated_position_parsed(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    {
      name: "L",
      html: "<p>hi</p>",
      position: { keyframes: [[0, [0, 0]], [1000, [50, 50]]] },
      width: 100,
      height: 100,
    },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        el = slide.elements[0]
        assert el.position.is_animated
        assert el.position.keyframes == [(0, (0, 0)), (1000, (50, 50))]

    def test_json5_features_work(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  // JSON5 comment
  title: "T",
  scroll_range: 1000,
  elements: [
    {
      name: "L",
      html: "<p>hi</p>",
      position: [0, 0],
      width: 100,
      height: 100,  // trailing comma
    },
  ],  // trailing comma
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert slide.title == "T"

    def test_scroll_range_zero(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "Static composition",
  scroll_range: 0,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert slide.scroll_range == 0

    def test_scroll_speed_custom(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 1000,
  scroll_speed: 0.5,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert slide.scroll_speed == 0.5

    def test_image_element_with_auto_dim(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", image: "img.png", position: [0, 0], width: 100, height: "auto" },
  ],
}
""",
        )
        slide = parse_json5_ir(src, SlideIR, "slide")
        assert isinstance(slide.elements[0], ImageElement)
        assert slide.elements[0].object_fit is None


# ── Error handling ────────────────────────────────────────────────


class TestParseErrors:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(SlideSourceError, match="not found"):
            parse_json5_ir(tmp_path / "no_such.slide.json", SlideIR, "slide")

    def test_invalid_json5(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "bad.slide.json", "not json at all {{{")
        with pytest.raises(SlideSourceError, match="not valid JSON5"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_top_level_not_object(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "bad.slide.json", "[1, 2, 3]")
        with pytest.raises(SlideSourceError, match="must be a JSON object"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_missing_title(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_missing_elements(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.slide.json", '{ title: "T", scroll_range: 100 }')
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")


# ── Validation through JSON5 path ─────────────────────────────────


class TestValidationViaJson5:
    def test_auto_auto_rejected(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: "auto", height: "auto" },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_object_fit_required(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", image: "img.jpg", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_object_fit_forbidden_with_auto(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", image: "img.jpg", position: [0, 0], width: 100, height: "auto", object_fit: "cover" },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_duplicate_element_names(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "dup", html: "<p>a</p>", position: [0, 0], width: 100, height: 100 },
    { name: "dup", html: "<p>b</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")

    def test_negative_scroll_range(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.slide.json",
            """\
{
  title: "T",
  scroll_range: -5,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, SlideIR, "slide")
