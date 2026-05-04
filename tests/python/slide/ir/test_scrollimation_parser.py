"""Tests for scrollimation JSON5 parsing — file → pydantic IR."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import ElementAnimation, HtmlElement, ImageElement, MarkdownElement, parse_json5_ir
from scrolly.slide.ir.scrollimation import ScrollimationIR


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
"""


# ── Happy path ────────────────────────────────────────────────────


class TestParsing:
    def test_minimal(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.title == "T"
        assert slide.scroll_range == 1000
        assert len(slide.elements) == 1
        assert isinstance(slide.elements[0].element, HtmlElement)

    def test_defaults_applied(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.initial_scroll_position == 0
        assert slide.scroll_speed == 1.0
        assert slide.easing == "linear"

    def test_all_three_element_types(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "Multi",
  scroll_range: 500,
  elements: [
    { element: { id: "bg", image: "hero.jpg", position: [0, 0], size: [100, 120], object_fit: "cover" } },
    { element: { id: "sep", html: "<div></div>", position: [0, 0], size: [100, 100] } },
    { element: { id: "txt", markdown: "# Hi", position: [10, 40], size: [80, "auto"] } },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert isinstance(slide.elements[0].element, ImageElement)
        assert isinstance(slide.elements[1].element, HtmlElement)
        assert isinstance(slide.elements[2].element, MarkdownElement)

    def test_keyframes_parsed(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    {
      element: {
        id: "L",
        html: "<p>hi</p>",
        position: [0, 0],
        size: [100, 100],
      },
      initial: { opacity: 0 },
      keyframes: [
        { at: 0, opacity: 0 },
        { at: 500, opacity: 1, translate: [50, 0] },
        { at: 1000, opacity: 0 },
      ],
    },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert len(slide.elements[0].keyframes) == 3
        assert slide.elements[0].keyframes[1].translate == (50, 0)

    def test_json5_features_work(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  // JSON5 comment
  title: "T",
  scroll_range: 1000,
  elements: [
    {
      element: {
        id: "L",
        html: "<p>hi</p>",
        position: [0, 0],
        size: [100, 100],  // trailing comma
      },
    },
  ],  // trailing comma
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.title == "T"

    def test_scroll_range_zero(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "Static composition",
  scroll_range: 0,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.scroll_range == 0

    def test_empty_keyframes(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      element: { id: "L", html: "<p>static</p>", position: [0, 0], size: [100, 100] },
      keyframes: [],
    },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.elements[0].keyframes == []

    def test_initial_omitted(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.elements[0].initial.opacity == 1.0
        assert slide.elements[0].initial.translate == (0.0, 0.0)

    def test_scroll_speed_custom(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 1000,
  scroll_speed: 0.5,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert slide.scroll_speed == 0.5

    def test_image_element_with_auto_dim(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "L", image: "img.png", position: [0, 0], size: [100, "auto"] } },
  ],
}
""",
        )
        slide = parse_json5_ir(src, ScrollimationIR, "scrollimation")
        assert isinstance(slide.elements[0].element, ImageElement)
        assert slide.elements[0].element.object_fit is None


# ── Error handling ────────────────────────────────────────────────


class TestParseErrors:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(SlideSourceError, match="not found"):
            parse_json5_ir(tmp_path / "no_such.scrollimation.json", ScrollimationIR, "scrollimation")

    def test_invalid_json5(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "bad.scrollimation.json", "not json at all {{{")
        with pytest.raises(SlideSourceError, match="not valid JSON5"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_top_level_not_object(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "bad.scrollimation.json", "[1, 2, 3]")
        with pytest.raises(SlideSourceError, match="must be a JSON object"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_missing_title(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  scroll_range: 100,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_missing_elements(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", '{ title: "T", scroll_range: 100 }')
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")


# ── Validation through JSON5 path ─────────────────────────────────


class TestValidationViaJson5:
    def test_auto_auto_rejected(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: ["auto", "auto"] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_object_fit_required(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "L", image: "img.jpg", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_object_fit_forbidden_with_auto(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "L", image: "img.jpg", position: [0, 0], size: [100, "auto"], object_fit: "cover" } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_duplicate_element_ids(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "dup", html: "<p>a</p>", position: [0, 0], size: [100, 100] } },
    { element: { id: "dup", html: "<p>b</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_keyframe_outside_range(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      element: {
        id: "L",
        html: "<p>hi</p>",
        position: [0, 0],
        size: [100, 100],
      },
      keyframes: [ { at: 200, opacity: 1 } ],
    },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_duplicate_keyframe_at_same_property(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      element: {
        id: "L",
        html: "<p>hi</p>",
        position: [0, 0],
        size: [100, 100],
      },
      keyframes: [
        { at: 50, opacity: 0 },
        { at: 50, opacity: 1 },
      ],
    },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_negative_scroll_range(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: -5,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")

    def test_element_with_both_html_and_asset_rejected(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { element: { id: "L", html: "<p>hi</p>", image: "img.jpg", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, ScrollimationIR, "scrollimation")
