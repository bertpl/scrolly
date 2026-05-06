"""Tests for storyboard end-to-end dispatch via the new registry."""

from __future__ import annotations

from pathlib import Path

import pytest

import scrolly.slide  # noqa: F401 — trigger registration
from scrolly.slide.compilers.storyboard import StoryboardCompiler
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR
from scrolly.slide.registry import find_compiler, find_renderer, get_ir_class_for_path, registered_suffixes


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL_STORYBOARD = """\
{
  title: "Test Storyboard",
  scene_distance: 100,
  scenes: [
    { elements: [{ html: "<p>Scene 1</p>", position: [10, 30], width: 80, height: "auto" }] },
    { elements: [{ html: "<p>Scene 2</p>", position: [10, 30], width: 80, height: "auto" }] },
  ],
}
"""


class TestRegistration:
    def test_suffix_registered(self):
        assert ".storyboard.json" in registered_suffixes()

    def test_lookup_by_path(self):
        cls = get_ir_class_for_path(Path("/foo/thing.storyboard.json"))
        assert cls is StoryboardIR


class TestDispatchChain:
    def test_from_file_returns_storyboard_ir(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        assert isinstance(ir, StoryboardIR)

    def test_compiler_found_for_storyboard_ir(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        assert find_renderer(ir) is None
        compiler = find_compiler(ir)
        assert isinstance(compiler, StoryboardCompiler)

    def test_compile_produces_scrollimation_ir(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        compiler = find_compiler(ir)
        result = compiler.compile(ir)
        assert isinstance(result, ScrollimationIR)

    def test_renderer_found_for_compiled_ir(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        compiler = find_compiler(ir)
        scrollimation_ir = compiler.compile(ir)
        renderer = find_renderer(scrollimation_ir)
        assert renderer is not None

    def test_full_chain_produces_chunk(self, tmp_path):
        src = _write(tmp_path / "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        compiler = find_compiler(ir)
        scrollimation_ir = compiler.compile(ir)
        renderer = find_renderer(scrollimation_ir)
        chunk = renderer.render(scrollimation_ir)
        assert chunk.title == "Test Storyboard"
        assert chunk.scroll_range == 100
        assert chunk.snap_positions == (0, 100)

    def test_asset_paths_resolved_to_absolute(self, tmp_path):
        _write(tmp_path / "bg.svg", "<svg/>")
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
        ir = StoryboardIR.from_file(src)
        assert ir.background[0].image.is_absolute()

    def test_scene_asset_paths_resolved(self, tmp_path):
        _write(tmp_path / "img.jpg", "fake")
        src = _write(
            tmp_path / "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [
    { elements: [{ image: "img.jpg", position: [0, 0], width: 100, height: 100, object_fit: "cover" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert ir.scenes[0].elements[0].image.is_absolute()
