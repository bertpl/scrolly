"""Element compiler / renderer registration, dispatch, and the compile loop.

Mirrors ``scrolly.slide.registry`` at the element level. Registrations
populate two module-level lists, checked in registration order via
``can_process``. The compile loop lowers an ``ElementIR`` to a flat list
of ``PrimitiveElement`` instances, with per-lineage cycle detection so
chained lowerings that would loop terminate with a clear error.
"""

from __future__ import annotations

from scrolly.errors import SlideSourceError
from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementCompiler, ElementRenderer

_COMPILERS: list[type[ElementCompiler]] = []
_RENDERERS: list[type[ElementRenderer]] = []


def register_element_compiler(compiler_cls: type[ElementCompiler]) -> None:
    """Register an ``ElementCompiler`` subclass. Checked in registration order."""
    if compiler_cls not in _COMPILERS:
        _COMPILERS.append(compiler_cls)


def register_element_renderer(renderer_cls: type[ElementRenderer]) -> None:
    """Register an ``ElementRenderer`` subclass. Checked in registration order."""
    if renderer_cls not in _RENDERERS:
        _RENDERERS.append(renderer_cls)


def find_element_compiler(ir: ElementIR) -> ElementCompiler | None:
    """Return a fresh ``ElementCompiler`` instance that can process ``ir``, or ``None``."""
    for cls in _COMPILERS:
        if cls.can_process(ir):
            return cls()
    return None


def find_element_renderer(ir: ElementIR) -> ElementRenderer | None:
    """Return a fresh ``ElementRenderer`` instance that can process ``ir``, or ``None``."""
    for cls in _RENDERERS:
        if cls.can_process(ir):
            return cls()
    return None


def compile_to_primitives(ir: ElementIR) -> list[PrimitiveElement]:
    """Lower ``ir`` to a flat list of ``PrimitiveElement`` instances.

    Recursively invokes registered compilers depth-first, left-to-right.
    A ``PrimitiveElement`` terminates its branch immediately. Cycle
    detection runs per root-to-leaf lineage: a given ``ElementIR``
    subclass appearing twice along the same lineage raises
    ``SlideSourceError``. Sibling occurrences of the same type are not a
    cycle.

    Args:
        ir: The root element to lower.

    Returns:
        Flat list of primitives in depth-first, left-to-right order.

    Raises:
        SlideSourceError: When a non-primitive element has no registered
            compiler, or when the same element type appears twice along
            a single lowering lineage.
    """
    return _compile_one(ir, frozenset({type(ir)}))


def _compile_one(ir: ElementIR, lineage: frozenset[type[ElementIR]]) -> list[PrimitiveElement]:
    """Lower a single ``ElementIR`` carrying its ancestry for cycle detection.

    Args:
        ir: The element to lower.
        lineage: The set of ``ElementIR`` subclasses already seen on the
            path from the root to (and including) ``ir``.

    Returns:
        Flat list of primitives in depth-first, left-to-right order.

    Raises:
        SlideSourceError: As described in ``compile_to_primitives``.
    """
    if isinstance(ir, PrimitiveElement):
        return [ir]

    compiler = find_element_compiler(ir)
    if compiler is None:
        raise SlideSourceError(f"no element compiler or renderer registered for {type(ir).__name__}")

    results = compiler.compile(ir)
    out: list[PrimitiveElement] = []
    for result in results:
        result_type = type(result)
        if result_type in lineage:
            raise SlideSourceError(
                f"element conversion cycle detected: {result_type.__name__} produced twice along the same lineage"
            )
        out.extend(_compile_one(result, lineage | {result_type}))
    return out
