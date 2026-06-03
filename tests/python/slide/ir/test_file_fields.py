"""Tests for the ``_file`` suffix pattern — external file refs for element content."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import IframeElement, MermaidElement
from scrolly.slide.ir.slide import SlideIR


def _write(path: Path, text: str) -> Path:
    """Write ``text`` to ``path`` (creating parents) and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── markdown_file ────────────────────────────────────────────────


def test_markdown_file(tmp_path: Path) -> None:
    _write(tmp_path / "content.md", "# Hello from file")
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert ir.elements[0].markdown == "# Hello from file"


# ── html_file ────────────────────────────────────────────────────


def test_html_file(tmp_path: Path) -> None:
    _write(tmp_path / "box.html", "<div>hello</div>")
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert ir.elements[0].html == "<div>hello</div>"


# ── mermaid_file ─────────────────────────────────────────────────


def test_mermaid_file(tmp_path: Path) -> None:
    _write(tmp_path / "diagram.mmd", "graph LR\n  A --> B --> C")
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert isinstance(ir.elements[0], MermaidElement)
    assert ir.elements[0].mermaid == "graph LR\n  A --> B --> C"


# ── iframe_html_file ─────────────────────────────────────────────


def test_iframe_html_file(tmp_path: Path) -> None:
    _write(tmp_path / "demo.html", "<!doctype html><p>iframe content</p>")
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert isinstance(ir.elements[0], IframeElement)
    assert ir.elements[0].iframe_html == "<!doctype html><p>iframe content</p>"


# ── Path resolution ──────────────────────────────────────────────


def test_relative_to_source_file(tmp_path: Path) -> None:
    subdir = tmp_path / "slides"
    _write(subdir / "content.md", "# Relative")
    src = _write(
        subdir / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert ir.elements[0].markdown == "# Relative"


def test_subdirectory_path(tmp_path: Path) -> None:
    _write(tmp_path / "diagrams" / "arch.mmd", "graph LR\n  A --> B")
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert "A --> B" in ir.elements[0].mermaid


# ── Error cases ──────────────────────────────────────────────────


def test_both_inline_and_file_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "content.md", "# Hi")
    src = _write(
        tmp_path / "s.slide.json",
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
        SlideIR.from_file(src)


def test_missing_file_raises_error(tmp_path: Path) -> None:
    src = _write(
        tmp_path / "s.slide.json",
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
        SlideIR.from_file(src)


def test_both_html_and_html_file_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "box.html", "<div/>")
    src = _write(
        tmp_path / "s.slide.json",
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
        SlideIR.from_file(src)


def test_both_iframe_html_and_iframe_html_file_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "demo.html", "<!doctype html>")
    src = _write(
        tmp_path / "s.slide.json",
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
        SlideIR.from_file(src)


# ── Non-element dicts left untouched ─────────────────────────────


def test_unrelated_file_suffixed_keys_ignored(tmp_path: Path) -> None:
    """Top-level / non-element ``_file`` keys must not be resolved."""
    src = _write(
        tmp_path / "s.slide.json",
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
    ir = SlideIR.from_file(src)
    assert ir.elements[0].html == "<p>hi</p>"
