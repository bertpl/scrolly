"""Tests for the ``Renderer`` ABC."""

from __future__ import annotations

import pytest

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Renderer


# ---------------------------------------------------------------------------
# Partial implementations are rejected
# ---------------------------------------------------------------------------
def test_renderer_not_instantiable_directly() -> None:
    with pytest.raises(TypeError):
        Renderer()  # type: ignore[abstract]


def test_renderer_missing_can_process() -> None:
    with pytest.raises(TypeError):

        class _Bad(Renderer):
            def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:
                return SlideHTML(title="x", html="x")

        _Bad()


def test_renderer_missing_render() -> None:
    with pytest.raises(TypeError):

        class _Bad(Renderer):
            @classmethod
            def can_process(cls, ir: SlideIR) -> bool:
                return True

        _Bad()


# ---------------------------------------------------------------------------
# can_process is a classmethod
# ---------------------------------------------------------------------------
def test_renderer_can_process_is_classmethod() -> None:
    class _AlwaysRenderer(Renderer):
        @classmethod
        def can_process(cls, ir: SlideIR) -> bool:
            return True

        def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:
            return SlideHTML(title="x", html="<p>x</p>")

    sample_ir = SlideIR(
        title="T",
        elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}],
    )
    assert _AlwaysRenderer.can_process(sample_ir) is True
