"""Tests for the SlideIR base class."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

import pytest

from scrolly.slide.ir import SlideIR


# ---------------------------------------------------------------------------
# Concrete test helper
# ---------------------------------------------------------------------------
class _DummyIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".dummy.md"
    value: str

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls(value=source_path.name)


# ---------------------------------------------------------------------------
# Cannot instantiate base directly
# ---------------------------------------------------------------------------
class TestABCInstantiation:
    def test_slide_ir_not_instantiable(self):
        with pytest.raises(TypeError):
            SlideIR()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete subclass works
# ---------------------------------------------------------------------------
class TestConcreteIR:
    def test_from_file(self):
        ir = _DummyIR.from_file(Path("/foo/test.dummy.md"))
        assert isinstance(ir, _DummyIR)
        assert ir.value == "test.dummy.md"

    def test_frozen(self):
        ir = _DummyIR(value="x")
        with pytest.raises(Exception):
            ir.value = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# slide_type property
# ---------------------------------------------------------------------------
class TestSlideTypeProperty:
    def test_single_dot_suffix(self):
        class _SingleDot(SlideIR, frozen=True):
            SUFFIX: ClassVar[str] = ".html"
            value: str = ""

            @classmethod
            def from_file(cls, source_path: Path) -> Self:
                return cls()

        assert _SingleDot().slide_type == "html"

    def test_double_dot_suffix(self):
        assert _DummyIR(value="x").slide_type == "dummy-md"

    def test_triple_dot_suffix(self):
        class _TripleDot(SlideIR, frozen=True):
            SUFFIX: ClassVar[str] = ".deep.static.md"
            value: str = ""

            @classmethod
            def from_file(cls, source_path: Path) -> Self:
                return cls()

        assert _TripleDot().slide_type == "deep-static-md"
