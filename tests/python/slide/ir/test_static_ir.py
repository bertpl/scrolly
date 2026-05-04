"""Tests for StaticIR model and the parse/render_ir split."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import SlideIR
from scrolly.slide.ir.static import StaticIR
from scrolly.slide.renderers.static import StaticRenderer

# ---------------------------------------------------------------------------
# StaticIR model
# ---------------------------------------------------------------------------


class TestStaticIR:
    def test_is_slide_ir(self):
        assert issubclass(StaticIR, SlideIR)

    def test_is_pydantic_model(self):
        assert issubclass(StaticIR, BaseModel)

    def test_minimal(self):
        ir = StaticIR(title=None, body="# Hello", initial_scroll_position=0, font_scale=1.0)
        assert ir.title is None
        assert ir.body == "# Hello"
        assert ir.initial_scroll_position == 0
        assert ir.font_scale == 1.0

    def test_with_title(self):
        ir = StaticIR(title="My Title", body="body", initial_scroll_position=0, font_scale=1.0)
        assert ir.title == "My Title"

    def test_frozen(self):
        ir = StaticIR(title=None, body="x", initial_scroll_position=0, font_scale=1.0)
        with pytest.raises(ValidationError):
            ir.body = "changed"

    def test_negative_initial_scroll_position_rejected(self):
        with pytest.raises(ValidationError, match="initial_scroll_position"):
            StaticIR(title=None, body="x", initial_scroll_position=-1, font_scale=1.0)

    def test_zero_font_scale_rejected(self):
        with pytest.raises(ValidationError, match="font_scale"):
            StaticIR(title=None, body="x", initial_scroll_position=0, font_scale=0)

    def test_negative_font_scale_rejected(self):
        with pytest.raises(ValidationError, match="font_scale"):
            StaticIR(title=None, body="x", initial_scroll_position=0, font_scale=-0.5)

    def test_font_scale_default(self):
        ir = StaticIR(title=None, body="x", initial_scroll_position=0)
        assert ir.font_scale == 1.0


# ---------------------------------------------------------------------------
# parse() independently
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


class TestFromFile:
    def test_returns_static_ir(self, tmp_path):
        src = _write(tmp_path, "s.static.md", "---\ninitial_scroll_position: 0\n---\n# Title\n\nBody.")
        ir = StaticIR.from_file(src)
        assert isinstance(ir, StaticIR)
        assert ir.title is None
        assert "# Title" in ir.body
        assert "Body." in ir.body
        assert ir.initial_scroll_position == 0
        assert ir.font_scale == 1.0

    def test_frontmatter_title_captured(self, tmp_path):
        src = _write(tmp_path, "s.static.md", "---\ninitial_scroll_position: 0\ntitle: FM Title\n---\n# H1")
        ir = StaticIR.from_file(src)
        assert ir.title == "FM Title"

    def test_font_scale_captured(self, tmp_path):
        src = _write(tmp_path, "s.static.md", "---\ninitial_scroll_position: 0\nfont_scale: 2.0\n---\n# x")
        ir = StaticIR.from_file(src)
        assert ir.font_scale == 2.0

    def test_missing_file_raises(self):
        with pytest.raises(SlideSourceError, match="not found"):
            StaticIR.from_file(Path("/no/such/file.static.md"))

    def test_slide_type_property(self, tmp_path):
        src = _write(tmp_path, "s.static.md", "---\ninitial_scroll_position: 0\n---\n# x")
        ir = StaticIR.from_file(src)
        assert ir.slide_type == "static-md"


# ---------------------------------------------------------------------------
# render() independently
# ---------------------------------------------------------------------------


class TestRender:
    def test_produces_chunk_from_ir(self):
        ir = StaticIR(title="Hello", body="Paragraph.", initial_scroll_position=0, font_scale=1.0)
        chunk = StaticRenderer().render(ir)
        assert chunk.title == "Hello"
        assert "<p>Paragraph.</p>" in chunk.html
        assert chunk.scroll_range is None
        assert chunk.initial_scroll_position == 0

    def test_h1_extraction_when_title_is_none(self):
        ir = StaticIR(title=None, body="# From Body", initial_scroll_position=0, font_scale=1.0)
        chunk = StaticRenderer().render(ir)
        assert chunk.title == "From Body"

    def test_missing_title_and_no_h1_raises(self):
        ir = StaticIR(title=None, body="No heading here.", initial_scroll_position=0, font_scale=1.0)
        with pytest.raises(SlideSourceError, match="could not determine title"):
            StaticRenderer().render(ir)

    def test_font_scale_passes_through(self):
        ir = StaticIR(title="x", body="# x", initial_scroll_position=0, font_scale=1.8)
        chunk = StaticRenderer().render(ir)
        assert chunk.font_scale == 1.8

    def test_initial_scroll_position_passes_through(self):
        ir = StaticIR(title="x", body="# x", initial_scroll_position=99, font_scale=1.0)
        chunk = StaticRenderer().render(ir)
        assert chunk.initial_scroll_position == 99

    def test_html_wrapped_in_type_div(self):
        ir = StaticIR(title="x", body="# x", initial_scroll_position=0, font_scale=1.0)
        chunk = StaticRenderer().render(ir)
        assert chunk.html.startswith('<div class="slide-type-static-md">')

    def test_scoped_css_present(self):
        ir = StaticIR(title="x", body="# x", initial_scroll_position=0, font_scale=1.0)
        chunk = StaticRenderer().render(ir)
        assert ".slide-type-static-md {" in chunk.scoped_css
