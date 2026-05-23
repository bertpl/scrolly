"""Tests for element-IR registration, dispatch, and the compile loop."""

from __future__ import annotations

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.element_ir import (
    ElementCompiler,
    ElementIR,
    ElementRenderer,
    PrimitiveElement,
    RenderContext,
    RenderedElement,
    compile_to_primitives,
    find_element_compiler,
    find_element_renderer,
    register_element_compiler,
    register_element_renderer,
)


# ==================================================================================================
#  Test ElementIR types
# ==================================================================================================
class _Composite(ElementIR, frozen=True):
    """High-level test type that lowers to a single primitive."""

    label: str = "composite"


class _Primitive(PrimitiveElement, frozen=True):
    """Primitive test type — terminates the compile loop."""

    label: str = "primitive"


class _High(ElementIR, frozen=True):
    """Top of a multi-step lowering chain."""

    label: str = "high"


class _Middle(ElementIR, frozen=True):
    """Intermediate step in a multi-step lowering chain."""

    label: str = "middle"


class _Fanout(ElementIR, frozen=True):
    """High-level type that expands to multiple primitives."""

    label: str = "fanout"


class _Mixed(ElementIR, frozen=True):
    """High-level type that expands to siblings of different types."""

    label: str = "mixed"


class _OtherPrimitive(PrimitiveElement, frozen=True):
    """A second primitive type used to test mixed-sibling lineages."""

    label: str = "other"


class _CyclicA(ElementIR, frozen=True):
    """Half of a two-step cycle."""


class _CyclicB(ElementIR, frozen=True):
    """The other half of a two-step cycle."""


class _Orphan(ElementIR, frozen=True):
    """Non-primitive type with no registered compiler."""


# ==================================================================================================
#  Test compilers
# ==================================================================================================
class _CompositeToPrimitiveCompiler(ElementCompiler):
    """Compiles _Composite → [_Primitive]."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_Composite`."""
        return isinstance(ir, _Composite)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower a `_Composite` to a single `_Primitive`."""
        assert isinstance(ir, _Composite)
        return [_Primitive(label=f"from-{ir.label}")]


class _HighToMiddleCompiler(ElementCompiler):
    """Compiles _High → [_Middle]."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_High`."""
        return isinstance(ir, _High)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower a `_High` to a single `_Middle`."""
        return [_Middle()]


class _MiddleToPrimitiveCompiler(ElementCompiler):
    """Compiles _Middle → [_Primitive]."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_Middle`."""
        return isinstance(ir, _Middle)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower a `_Middle` to a single `_Primitive`."""
        return [_Primitive(label="middle-lowered")]


class _FanoutCompiler(ElementCompiler):
    """Compiles _Fanout → [a, b, c] primitives."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_Fanout`."""
        return isinstance(ir, _Fanout)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower a `_Fanout` to three primitives in author order."""
        return [_Primitive(label="a"), _Primitive(label="b"), _Primitive(label="c")]


class _MixedCompiler(ElementCompiler):
    """Compiles _Mixed → [_Primitive, _OtherPrimitive, _Primitive]."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_Mixed`."""
        return isinstance(ir, _Mixed)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower to siblings of two different primitive types."""
        return [_Primitive(label="x"), _OtherPrimitive(label="y"), _Primitive(label="z")]


class _CyclicAToBCompiler(ElementCompiler):
    """Compiles _CyclicA → [_CyclicB]; pair with the inverse to create a cycle."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_CyclicA`."""
        return isinstance(ir, _CyclicA)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower `_CyclicA` to `_CyclicB`."""
        return [_CyclicB()]


class _CyclicBToACompiler(ElementCompiler):
    """Compiles _CyclicB → [_CyclicA]; pair with the inverse to create a cycle."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_CyclicB`."""
        return isinstance(ir, _CyclicB)

    def compile(self, ir: ElementIR) -> list[ElementIR]:
        """Lower `_CyclicB` to `_CyclicA`."""
        return [_CyclicA()]


# ==================================================================================================
#  Test renderers
# ==================================================================================================
class _PrimitiveRenderer(ElementRenderer):
    """Renders a `_Primitive` to a `RenderedElement`."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match instances of `_Primitive`."""
        return isinstance(ir, _Primitive)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render the primitive's label as a paragraph (ctx is unused in this test stub)."""
        assert isinstance(ir, _Primitive)
        return RenderedElement(html=f"<p>{ir.label}</p>")


# Pre-register every compiler / renderer used below. Registration is
# idempotent, so repeated test invocations don't accumulate duplicates.
register_element_compiler(_CompositeToPrimitiveCompiler)
register_element_compiler(_HighToMiddleCompiler)
register_element_compiler(_MiddleToPrimitiveCompiler)
register_element_compiler(_FanoutCompiler)
register_element_compiler(_MixedCompiler)
register_element_compiler(_CyclicAToBCompiler)
register_element_compiler(_CyclicBToACompiler)
register_element_renderer(_PrimitiveRenderer)


# ==================================================================================================
#  Registration + dispatch
# ==================================================================================================
def test_register_and_find_compiler_returns_matching_instance() -> None:
    """A registered compiler is discoverable by an IR it matches."""
    # --- arrange / act ----------------------
    compiler = find_element_compiler(_Composite())

    # --- assert -----------------------------
    assert isinstance(compiler, _CompositeToPrimitiveCompiler)


def test_register_and_find_renderer_returns_matching_instance() -> None:
    """A registered renderer is discoverable by a primitive it matches."""
    # --- arrange / act ----------------------
    renderer = find_element_renderer(_Primitive())

    # --- assert -----------------------------
    assert isinstance(renderer, _PrimitiveRenderer)


def test_find_compiler_returns_none_when_no_match() -> None:
    """No compiler claims a primitive — `find_element_compiler` returns None."""
    # --- arrange / act ----------------------
    compiler = find_element_compiler(_Primitive())

    # --- assert -----------------------------
    assert compiler is None


def test_find_renderer_returns_none_when_no_match() -> None:
    """No renderer claims a high-level type — `find_element_renderer` returns None."""
    # --- arrange / act ----------------------
    renderer = find_element_renderer(_Composite())

    # --- assert -----------------------------
    assert renderer is None


def test_find_returns_fresh_instance_each_call() -> None:
    """Successive lookups return distinct instances of the matching class."""
    # --- arrange / act ----------------------
    a = find_element_compiler(_Composite())
    b = find_element_compiler(_Composite())

    # --- assert -----------------------------
    assert a is not b
    assert type(a) is type(b)


def test_register_compiler_is_idempotent() -> None:
    """Re-registering the same compiler class is a no-op."""
    # --- arrange ----------------------------
    from scrolly.slide.element_ir.registry import _COMPILERS

    before = list(_COMPILERS)

    # --- act --------------------------------
    register_element_compiler(_CompositeToPrimitiveCompiler)

    # --- assert -----------------------------
    assert list(_COMPILERS) == before


def test_register_renderer_is_idempotent() -> None:
    """Re-registering the same renderer class is a no-op."""
    # --- arrange ----------------------------
    from scrolly.slide.element_ir.registry import _RENDERERS

    before = list(_RENDERERS)

    # --- act --------------------------------
    register_element_renderer(_PrimitiveRenderer)

    # --- assert -----------------------------
    assert list(_RENDERERS) == before


# ==================================================================================================
#  compile_to_primitives — happy paths
# ==================================================================================================
def test_compile_to_primitives_returns_primitive_unchanged() -> None:
    """A primitive root is returned as-is."""
    # --- arrange ----------------------------
    root = _Primitive(label="solo")

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    assert primitives == [root]


def test_compile_to_primitives_single_step_lowering() -> None:
    """A one-hop compiler lowers its input to one primitive."""
    # --- arrange ----------------------------
    root = _Composite(label="hello")

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    assert primitives == [_Primitive(label="from-hello")]


def test_compile_to_primitives_chained_lowering() -> None:
    """Multi-hop chains run to completion (_High → _Middle → _Primitive)."""
    # --- arrange ----------------------------
    root = _High()

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    assert primitives == [_Primitive(label="middle-lowered")]


def test_compile_to_primitives_fanout_preserves_order() -> None:
    """A fan-out compiler emits its outputs in author order."""
    # --- arrange ----------------------------
    root = _Fanout()

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    assert [p.label for p in primitives] == ["a", "b", "c"]


def test_compile_to_primitives_mixed_siblings_keep_distinct_lineages() -> None:
    """Siblings of different primitive types are passed through without false cycle."""
    # --- arrange ----------------------------
    root = _Mixed()

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    assert [type(p) for p in primitives] == [_Primitive, _OtherPrimitive, _Primitive]
    assert [p.label for p in primitives] == ["x", "y", "z"]


# ==================================================================================================
#  compile_to_primitives — error paths
# ==================================================================================================
def test_compile_to_primitives_raises_when_no_compiler_or_renderer() -> None:
    """A non-primitive without a compiler raises a clear error."""
    # --- arrange ----------------------------
    root = _Orphan()

    # --- act / assert -----------------------
    with pytest.raises(SlideSourceError, match="no element compiler or renderer"):
        compile_to_primitives(root)


def test_compile_to_primitives_detects_cycle_along_lineage() -> None:
    """Two compilers that lower into each other raise a cycle error."""
    # --- arrange ----------------------------
    root = _CyclicA()

    # --- act / assert -----------------------
    with pytest.raises(SlideSourceError, match="cycle detected"):
        compile_to_primitives(root)


def test_compile_to_primitives_allows_same_type_as_sibling() -> None:
    """Repeating a type across siblings (not down a lineage) is allowed."""
    # --- arrange ----------------------------
    root = _Fanout()

    # --- act --------------------------------
    primitives = compile_to_primitives(root)

    # --- assert -----------------------------
    # All three children are `_Primitive`; siblings, not a lineage repeat.
    assert all(isinstance(p, _Primitive) for p in primitives)
    assert len(primitives) == 3


# ==================================================================================================
#  RenderedElement — smoke
# ==================================================================================================
def test_rendered_element_defaults_are_empty() -> None:
    """The contribution bundle's optional fields default to empty / False."""
    # --- arrange / act ----------------------
    rendered = RenderedElement(html="<p>x</p>")

    # --- assert -----------------------------
    assert rendered.html == "<p>x</p>"
    assert rendered.scoped_css == ""
    assert rendered.snap_positions == ()
    assert rendered.assets == ()
    assert rendered.has_mermaid is False


def test_rendered_element_is_frozen() -> None:
    """The contribution bundle is immutable post-construction."""
    # --- arrange ----------------------------
    rendered = RenderedElement(html="<p>x</p>")

    # --- act / assert -----------------------
    with pytest.raises(Exception):  # FrozenInstanceError on a frozen dataclass.
        rendered.html = "<p>y</p>"  # type: ignore[misc]
