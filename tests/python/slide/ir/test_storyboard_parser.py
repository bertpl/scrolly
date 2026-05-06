"""Tests for storyboard JSON5 parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import HtmlElement, ImageElement, MarkdownElement, parse_json5_ir
from scrolly.slide.ir.storyboard import StoryboardIR


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """\
{
  title: "Test",
  scene_distance: 100,
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [10, 30], width: 80, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [10, 30], width: 80, height: "auto" }] },
  ],
}
"""


class TestParsing:
    def test_minimal(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL)
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert isinstance(ir, StoryboardIR)
        assert ir.title == "Test"
        assert ir.scene_distance == 100
        assert ir.hold == 0
        assert ir.background == []
        assert len(ir.scenes) == 2

    def test_defaults_applied(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL)
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert ir.hold == 0
        assert ir.background == []

    def test_with_hold(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  hold: 20,
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [0, 0], width: 100, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert ir.hold == 20

    def test_with_background(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  background: [
    { image: "bg.svg", position: [0, 0], width: 100, height: 100, object_fit: "cover" },
  ],
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [0, 0], width: 100, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert len(ir.background) == 1
        assert isinstance(ir.background[0], ImageElement)

    def test_all_three_element_types(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [
    {
      elements: [
        { image: "img.jpg", position: [0, 0], width: 100, height: 100, object_fit: "cover" },
        { html: "<p>hi</p>", position: [10, 10], width: 80, height: "auto" },
        { markdown: "# Hello", position: [10, 50], width: 80, height: "auto" },
      ],
    },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        elements = ir.scenes[0].elements
        assert isinstance(elements[0], ImageElement)
        assert isinstance(elements[1], HtmlElement)
        assert isinstance(elements[2], MarkdownElement)

    def test_markdown_color(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [
    { elements: [{ markdown: "# Hi", color: "#fff", position: [0, 0], width: 80, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert ir.scenes[0].elements[0].color == "#fff"

    def test_json5_features_work(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  // Comments allowed
  title: "T",
  scene_distance: 100,
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [10, 30], width: 80, height: "auto", }] },
    { elements: [{ html: "<p>B</p>", position: [10, 30], width: 80, height: "auto", }] },
  ],  // trailing comma
}
""",
        )
        ir = parse_json5_ir(src, StoryboardIR, "storyboard")
        assert ir.title == "T"


class TestParseErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(SlideSourceError, match="not found"):
            parse_json5_ir(tmp_path / "no_such.storyboard.json", StoryboardIR, "storyboard")

    def test_invalid_json5(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", "{{bad json")
        with pytest.raises(SlideSourceError, match="not valid JSON5"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_top_level_not_object(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", "[1, 2, 3]")
        with pytest.raises(SlideSourceError, match="JSON object"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_missing_title(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  scene_distance: 100,
  scenes: [{ elements: [{ html: "<p>A</p>", position: [0, 0], width: 100, height: "auto" }] }],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_missing_scenes(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", '{ title: "T", scene_distance: 100 }')
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_empty_scenes(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{ title: "T", scene_distance: 100, scenes: [] }
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_hold_too_large(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  hold: 50,
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [0, 0], width: 100, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, StoryboardIR, "storyboard")

    def test_empty_scene_elements(self, tmp_path):
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [{ elements: [] }],
}
""",
        )
        with pytest.raises(SlideSourceError, match="validation failed"):
            parse_json5_ir(src, StoryboardIR, "storyboard")
