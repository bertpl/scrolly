"""Tests for the _file suffix pattern — external file references for element content."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import IframeElement, MermaidElement
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── markdown_file ────────────────────────────────────────────────


class TestMarkdownFile:
    def test_scrollimation_markdown_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "content.md", "# Hello from file")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "txt", markdown_file: "content.md", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert ir.elements[0].markdown == "# Hello from file"

    def test_storyboard_markdown_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "content.md", "# Scene text")
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [{ elements: [{ markdown_file: "content.md", position: [10, 10], width: 80, height: "auto" }] }],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert ir.scenes[0].elements[0].markdown == "# Scene text"


# ── html_file ────────────────────────────────────────────────────


class TestHtmlFile:
    def test_scrollimation_html_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "box.html", "<div>hello</div>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "h", html_file: "box.html", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert ir.elements[0].html == "<div>hello</div>"


# ── mermaid_file ─────────────────────────────────────────────────


class TestMermaidFile:
    def test_scrollimation_mermaid_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "diagram.mmd", "graph LR\n  A --> B --> C")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "dia", mermaid_file: "diagram.mmd", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert isinstance(ir.elements[0], MermaidElement)
        assert ir.elements[0].mermaid == "graph LR\n  A --> B --> C"

    def test_storyboard_mermaid_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "diagram.mmd", "graph TD\n  X --> Y")
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [{ elements: [{ mermaid_file: "diagram.mmd", position: [10, 10], width: 80, height: "auto" }] }],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert isinstance(ir.scenes[0].elements[0], MermaidElement)


# ── iframe_html_file ─────────────────────────────────────────────


class TestIframeHtmlFile:
    def test_scrollimation_iframe_html_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "demo.html", "<!doctype html><p>iframe content</p>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "frame", iframe_html_file: "demo.html", position: [10, 10], width: 80, height: 80 },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert isinstance(ir.elements[0], IframeElement)
        assert ir.elements[0].iframe_html == "<!doctype html><p>iframe content</p>"

    def test_storyboard_iframe_html_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "demo.html", "<!doctype html><h1>Scene iframe</h1>")
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [{ elements: [{ iframe_html_file: "demo.html", position: [10, 10], width: 80, height: 80 }] }],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert isinstance(ir.scenes[0].elements[0], IframeElement)
        assert ir.scenes[0].elements[0].iframe_html == "<!doctype html><h1>Scene iframe</h1>"


# ── Path resolution ──────────────────────────────────────────────


class TestPathResolution:
    def test_relative_to_source_file(self, tmp_path: Path) -> None:
        subdir = tmp_path / "slides"
        _write(subdir / "content.md", "# Relative")
        src = _write(
            subdir / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "txt", markdown_file: "content.md", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert ir.elements[0].markdown == "# Relative"

    def test_subdirectory_path(self, tmp_path: Path) -> None:
        _write(tmp_path / "diagrams" / "arch.mmd", "graph LR\n  A --> B")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "dia", mermaid_file: "diagrams/arch.mmd", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert "A --> B" in ir.elements[0].mermaid


# ── Error cases ──────────────────────────────────────────────────


class TestErrors:
    def test_both_inline_and_file_rejected(self, tmp_path: Path) -> None:
        _write(tmp_path / "content.md", "# Hi")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "txt", markdown: "inline", markdown_file: "content.md", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="cannot specify both"):
            ScrollimationIR.from_file(src)

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "txt", markdown_file: "nonexistent.md", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="not found"):
            ScrollimationIR.from_file(src)

    def test_both_html_and_html_file_rejected(self, tmp_path: Path) -> None:
        _write(tmp_path / "box.html", "<div/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "h", html: "<p>inline</p>", html_file: "box.html", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="cannot specify both"):
            ScrollimationIR.from_file(src)

    def test_both_iframe_html_and_iframe_html_file_rejected(self, tmp_path: Path) -> None:
        _write(tmp_path / "demo.html", "<!doctype html>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      name: "frame",
      iframe_html: "<!doctype html>inline",
      iframe_html_file: "demo.html",
      position: [0, 0],
      width: 100,
      height: 100,
    },
  ],
}
""",
        )
        with pytest.raises(SlideSourceError, match="cannot specify both"):
            ScrollimationIR.from_file(src)


# ── Non-element dicts left untouched ─────────────────────────────


class TestNonElementDicts:
    def test_unrelated_file_suffixed_keys_ignored(self, tmp_path: Path) -> None:
        """Top-level or non-element keys ending in _file should not be resolved."""
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
        )
        ir = ScrollimationIR.from_file(src)
        assert ir.elements[0].html == "<p>hi</p>"
