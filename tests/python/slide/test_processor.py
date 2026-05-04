"""Tests for the IRProcessor / Renderer / Compiler ABCs."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

import pytest

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Compiler, IRProcessor, Renderer

# ---------------------------------------------------------------------------
# Concrete test helpers
# ---------------------------------------------------------------------------


class _FakeIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".fake.md"
    value: str = "fake"

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls()


class _OtherIR(SlideIR, frozen=True):
    SUFFIX: ClassVar[str] = ".other.json"
    converted: str = "other"

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        return cls()


class _FakeRenderer(Renderer):
    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, _FakeIR)

    def render(self, ir: SlideIR) -> SlideHTML:
        assert isinstance(ir, _FakeIR)
        return SlideHTML(title=ir.value, html=f"<p>{ir.value}</p>")


class _FakeCompiler(Compiler):
    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, _OtherIR)

    def compile(self, ir: SlideIR) -> SlideIR:
        assert isinstance(ir, _OtherIR)
        return _FakeIR(value=ir.converted.upper())


# ---------------------------------------------------------------------------
# Cannot instantiate ABCs directly
# ---------------------------------------------------------------------------


class TestABCInstantiation:
    def test_ir_processor_not_instantiable(self):
        with pytest.raises(TypeError):
            IRProcessor()  # type: ignore[abstract]

    def test_renderer_not_instantiable(self):
        with pytest.raises(TypeError):
            Renderer()  # type: ignore[abstract]

    def test_compiler_not_instantiable(self):
        with pytest.raises(TypeError):
            Compiler()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Partial implementations are rejected
# ---------------------------------------------------------------------------


class TestPartialImplementation:
    def test_renderer_missing_can_process(self):
        with pytest.raises(TypeError):

            class _Bad(Renderer):
                def render(self, ir: SlideIR) -> SlideHTML:
                    return SlideHTML(title="x", html="x")

            _Bad()

    def test_renderer_missing_render(self):
        with pytest.raises(TypeError):

            class _Bad(Renderer):
                @classmethod
                def can_process(cls, ir: SlideIR) -> bool:
                    return True

            _Bad()

    def test_compiler_missing_can_process(self):
        with pytest.raises(TypeError):

            class _Bad(Compiler):
                def compile(self, ir: SlideIR) -> SlideIR:
                    return _FakeIR()

            _Bad()

    def test_compiler_missing_compile(self):
        with pytest.raises(TypeError):

            class _Bad(Compiler):
                @classmethod
                def can_process(cls, ir: SlideIR) -> bool:
                    return True

            _Bad()


# ---------------------------------------------------------------------------
# can_process is a classmethod
# ---------------------------------------------------------------------------


class TestCanProcess:
    def test_renderer_can_process_is_classmethod(self):
        assert _FakeRenderer.can_process(_FakeIR()) is True
        assert _FakeRenderer.can_process(_OtherIR()) is False

    def test_compiler_can_process_is_classmethod(self):
        assert _FakeCompiler.can_process(_OtherIR()) is True
        assert _FakeCompiler.can_process(_FakeIR()) is False


# ---------------------------------------------------------------------------
# Concrete implementations work end-to-end
# ---------------------------------------------------------------------------


class TestConcreteRenderer:
    def test_render(self):
        renderer = _FakeRenderer()
        chunk = renderer.render(_FakeIR(value="hello"))
        assert chunk.title == "hello"
        assert "<p>hello</p>" in chunk.html


class TestConcreteCompiler:
    def test_compile(self):
        compiler = _FakeCompiler()
        result = compiler.compile(_OtherIR(converted="hello"))
        assert isinstance(result, _FakeIR)
        assert result.value == "HELLO"


# ---------------------------------------------------------------------------
# Inheritance hierarchy
# ---------------------------------------------------------------------------


class TestInheritance:
    def test_renderer_is_ir_processor(self):
        assert issubclass(_FakeRenderer, IRProcessor)

    def test_compiler_is_ir_processor(self):
        assert issubclass(_FakeCompiler, IRProcessor)

    def test_renderer_instance_is_ir_processor(self):
        assert isinstance(_FakeRenderer(), IRProcessor)

    def test_compiler_instance_is_ir_processor(self):
        assert isinstance(_FakeCompiler(), IRProcessor)
