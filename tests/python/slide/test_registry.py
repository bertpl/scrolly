"""Tests for slide-IR + renderer registration and dispatch.

After the v0.2.0 collapse to a single slide type the registry holds
one ``SlideIR`` and one ``SlideRenderer``; the look-up surface still
supports adding a second type without re-architecting, so the tests
here exercise both the dormant-multi-type machinery and the single
registered entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

import pytest
from pydantic import Field

import scrolly.slide  # noqa: F401 — trigger built-in registration
from scrolly.errors import UnknownSlideTypeError
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Renderer
from scrolly.slide.registry import (
    find_renderer,
    get_ir_class_for_path,
    register_ir,
    register_renderer,
    registered_ir_types,
    registered_suffixes,
)


# ---------------------------------------------------------------------------
# Test IR + renderer (suffix is test-only, never collides with the real one)
# ---------------------------------------------------------------------------
class _FakeIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".testfake.slide.json"
    DESCRIPTION: ClassVar[str] = "Test fake"
    marker: str = Field(default="fake")

    @classmethod
    def from_file(cls, source_path: Path) -> Self:  # noqa: D401
        """Stub loader for tests."""
        return cls(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])


class _NoSuffixIR(SlideIR, frozen=True):
    """SlideIR subclass that blanks out the inherited SUFFIX."""

    SUFFIX: ClassVar[str] = ""
    marker: str = Field(default="x")

    @classmethod
    def from_file(cls, source_path: Path) -> Self:  # noqa: D401
        """Stub loader for tests."""
        return cls(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])


class _FakeRenderer(Renderer):
    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        """Match `_FakeIR` instances only."""
        return isinstance(ir, _FakeIR)

    def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:  # type: ignore[override]
        """Trivial render — returns a minimal SlideHTML."""
        return SlideHTML(title="fake", html="<p>fake</p>")


# ---------------------------------------------------------------------------
# IR registration + suffix lookup
# ---------------------------------------------------------------------------
def test_slide_suffix_is_registered_on_import() -> None:
    assert ".slide.json" in registered_suffixes()


def test_register_ir_and_lookup() -> None:
    register_ir(_FakeIR)
    cls = get_ir_class_for_path(Path("/foo/bar.testfake.slide.json"))
    assert cls is _FakeIR


def test_unknown_suffix_raises() -> None:
    with pytest.raises(UnknownSlideTypeError, match="no slide type matches"):
        get_ir_class_for_path(Path("/foo/bar.totally-unknown-suffix.xyz"))


def test_register_ir_rejects_type_without_suffix() -> None:
    with pytest.raises(TypeError, match="SUFFIX"):
        register_ir(_NoSuffixIR)


def test_register_ir_rejects_duplicate_suffix_from_different_class() -> None:
    class _DuplicateSlideIR(SlideIR, frozen=True):
        SUFFIX: ClassVar[str] = ".slide.json"

        @classmethod
        def from_file(cls, source_path: Path) -> Self:  # noqa: D401
            """Stub loader for tests."""
            return cls(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])

    with pytest.raises(ValueError, match="already registered"):
        register_ir(_DuplicateSlideIR)


def test_register_ir_is_idempotent_for_same_class() -> None:
    register_ir(_FakeIR)
    register_ir(_FakeIR)
    assert ".testfake.slide.json" in registered_suffixes()


def test_longest_suffix_match_wins() -> None:
    class _DeepIR(SlideIR, frozen=True):
        SUFFIX: ClassVar[str] = ".deep.slide.json"

        @classmethod
        def from_file(cls, source_path: Path) -> Self:  # noqa: D401
            """Stub loader for tests."""
            return cls(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])

    register_ir(_DeepIR)
    assert get_ir_class_for_path(Path("/foo/x.deep.slide.json")) is _DeepIR
    assert get_ir_class_for_path(Path("/foo/x.slide.json")) is SlideIR


# ---------------------------------------------------------------------------
# Renderer registration + dispatch
# ---------------------------------------------------------------------------
def test_register_renderer_and_find() -> None:
    register_renderer(_FakeRenderer)
    ir = _FakeIR(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])
    renderer = find_renderer(ir)
    assert isinstance(renderer, _FakeRenderer)


def test_register_renderer_is_idempotent() -> None:
    register_renderer(_FakeRenderer)
    register_renderer(_FakeRenderer)
    ir = _FakeIR(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])
    assert find_renderer(ir) is not None


def test_find_renderer_returns_fresh_instance() -> None:
    register_renderer(_FakeRenderer)
    sample = _FakeIR(title="t", elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}])
    a = find_renderer(sample)
    b = find_renderer(sample)
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in registration resolves correctly
# ---------------------------------------------------------------------------
def test_slide_ir_finds_renderer() -> None:
    ir = SlideIR(
        title="T",
        scroll_range=100,
        elements=[{"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}],
    )
    assert find_renderer(ir) is not None


def test_registered_ir_types_contains_builtin_slide() -> None:
    types = registered_ir_types()
    assert "slide" in types
    assert types["slide"] is SlideIR
