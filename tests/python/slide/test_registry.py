"""Tests for slide IR, renderer, and compiler registration and dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

import pytest

import scrolly.slide  # noqa: F401 — trigger built-in type registration
from scrolly.errors import UnknownSlideTypeError
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Compiler, Renderer
from scrolly.slide.registry import (
    _IR_TYPES,
    find_compiler,
    find_renderer,
    get_ir_class_for_path,
    register_compiler,
    register_ir,
    register_renderer,
    registered_ir_types,
    registered_suffixes,
)


# ---------------------------------------------------------------------------
# Test IR models
# ---------------------------------------------------------------------------
class _FakeIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".testfake.md"
    DESCRIPTION: ClassVar[str] = "Test fake"
    value: str = "fake"

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls()


class _OtherIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".testother.json"
    DESCRIPTION: ClassVar[str] = "Test other"
    value: str = "other"

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls()


# ---------------------------------------------------------------------------
# Test processors
# ---------------------------------------------------------------------------
class _FakeRenderer(Renderer):
    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, _FakeIR)

    def render(self, ir: SlideIR) -> SlideHTML:
        return SlideHTML(title="fake", html="")


class _FakeCompiler(Compiler):
    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, _OtherIR)

    def compile(self, ir: SlideIR) -> SlideIR:
        return _FakeIR(value="compiled")


# ---------------------------------------------------------------------------
# IR registration + suffix lookup
# ---------------------------------------------------------------------------
def test_static_suffix_is_registered_on_import():
    assert ".static.md" in registered_suffixes()


def test_scrollimation_suffix_is_registered_on_import():
    assert ".scrollimation.json" in registered_suffixes()


def test_storyboard_suffix_is_registered_on_import():
    assert ".storyboard.json" in registered_suffixes()


def test_register_ir_and_lookup():
    register_ir(_FakeIR)
    cls = get_ir_class_for_path(Path("/foo/bar.testfake.md"))
    assert cls is _FakeIR


def test_unknown_suffix_raises():
    with pytest.raises(UnknownSlideTypeError, match="no slide type matches"):
        get_ir_class_for_path(Path("/foo/bar.totally-unknown-suffix.xyz"))


class _NoSuffixIR(SlideIR, frozen=True):
    value: str = ""

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls()


def test_register_ir_rejects_type_without_suffix():
    with pytest.raises(TypeError, match="SUFFIX"):
        register_ir(_NoSuffixIR)


def test_register_ir_rejects_duplicate_suffix_from_different_class():
    class _DuplicateStaticIR(SlideIR, frozen=True):
        SUFFIX: ClassVar[str] = ".static.md"
        value: str = ""

        @classmethod
        def from_file(cls, source_path: Path) -> Self:
            return cls()

    with pytest.raises(ValueError, match="already registered"):
        register_ir(_DuplicateStaticIR)


def test_register_ir_is_idempotent_for_same_class():
    register_ir(_FakeIR)
    register_ir(_FakeIR)
    assert ".testfake.md" in registered_suffixes()


def test_longest_suffix_match_wins():
    class _DeepIR(SlideIR, frozen=True):
        SUFFIX: ClassVar[str] = ".deep.static.md"
        value: str = "deep"

        @classmethod
        def from_file(cls, source_path: Path) -> Self:
            return cls()

    register_ir(_DeepIR)
    assert get_ir_class_for_path(Path("/foo/x.deep.static.md")) is _DeepIR
    from scrolly.slide.ir.static import StaticIR

    assert get_ir_class_for_path(Path("/foo/x.static.md")) is StaticIR


# ---------------------------------------------------------------------------
# Renderer registration + dispatch
# ---------------------------------------------------------------------------
def test_register_renderer_and_find():
    register_renderer(_FakeRenderer)
    ir = _FakeIR()
    renderer = find_renderer(ir)
    assert isinstance(renderer, _FakeRenderer)


def test_find_renderer_returns_none_for_unhandled_ir():
    ir = _OtherIR()
    # _OtherIR has no renderer registered (only a compiler)
    register_compiler(_FakeCompiler)
    result = find_renderer(ir)
    assert result is None


def test_register_renderer_is_idempotent():
    register_renderer(_FakeRenderer)
    register_renderer(_FakeRenderer)
    ir = _FakeIR()
    assert find_renderer(ir) is not None


def test_find_renderer_returns_fresh_instance():
    register_renderer(_FakeRenderer)
    a = find_renderer(_FakeIR())
    b = find_renderer(_FakeIR())
    assert a is not b


# ---------------------------------------------------------------------------
# Compiler registration + dispatch
# ---------------------------------------------------------------------------
def test_register_compiler_and_find():
    register_compiler(_FakeCompiler)
    ir = _OtherIR()
    compiler = find_compiler(ir)
    assert isinstance(compiler, _FakeCompiler)


def test_find_compiler_returns_none_for_unhandled_ir():
    ir = _FakeIR()
    result = find_compiler(ir)
    assert result is None


def test_register_compiler_is_idempotent():
    register_compiler(_FakeCompiler)
    register_compiler(_FakeCompiler)
    ir = _OtherIR()
    assert find_compiler(ir) is not None


# ---------------------------------------------------------------------------
# Built-in renderers + compilers resolve correctly
# ---------------------------------------------------------------------------
def test_static_ir_finds_renderer():
    from scrolly.slide.ir.static import StaticIR

    ir = StaticIR(title="x", body="# x", initial_scroll_position=0)
    assert find_renderer(ir) is not None


def test_scrollimation_ir_finds_renderer():
    from scrolly.slide.ir.scrollimation import ScrollimationIR

    ir = ScrollimationIR(
        title="T",
        scroll_range=100,
        elements=[{"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}],
    )
    assert find_renderer(ir) is not None


def test_storyboard_ir_finds_compiler():
    from scrolly.slide.ir.storyboard import StoryboardIR

    ir = StoryboardIR(
        title="T",
        scene_distance=100,
        scenes=[
            {"elements": [{"html": "<p>1</p>", "position": [0, 0], "width": 80, "height": "auto"}]},
            {"elements": [{"html": "<p>2</p>", "position": [0, 0], "width": 80, "height": "auto"}]},
        ],
    )
    assert find_compiler(ir) is not None
    assert find_renderer(ir) is None


# ---------------------------------------------------------------------------
# registered_ir_types
# ---------------------------------------------------------------------------
def test_registered_ir_types_contains_builtins():
    types = registered_ir_types()
    assert "static" in types
    assert "scrollimation" in types
    assert "storyboard" in types


def test_registered_ir_types_maps_to_correct_classes():
    from scrolly.slide.ir.scrollimation import ScrollimationIR
    from scrolly.slide.ir.static import StaticIR
    from scrolly.slide.ir.storyboard import StoryboardIR

    types = registered_ir_types()
    assert types["static"] is StaticIR
    assert types["scrollimation"] is ScrollimationIR
    assert types["storyboard"] is StoryboardIR
