"""Slide IR, renderer, and compiler registration and dispatch.

Built-in types register themselves on ``import scrolly.slide`` via
``scrolly/slide/types/__init__.py``.

Dispatch is by filename suffix: each IR class declares a ``SUFFIX``
(e.g. ``".static.md"``); ``get_ir_class_for_path`` finds the registered
IR whose suffix is a tail-match of the source filename.

For rendering and compilation, the pipeline calls ``find_renderer`` and
``find_compiler``, which iterate their respective lists and return the
first whose ``can_process`` returns ``True``.
"""

from __future__ import annotations

from pathlib import Path

from scrolly.errors import UnknownSlideTypeError
from scrolly.slide.ir import SlideIR
from scrolly.slide.processor import Compiler, Renderer

_IR_TYPES: dict[str, type[SlideIR]] = {}
_RENDERERS: list[type[Renderer]] = []
_COMPILERS: list[type[Compiler]] = []


def register_ir(ir_cls: type[SlideIR]) -> None:
    """Register a SlideIR subclass under its ``SUFFIX``.

    Re-registering the same class for the same suffix is a no-op.
    Two distinct classes claiming the same suffix is an error.
    """
    if not hasattr(ir_cls, "SUFFIX") or not ir_cls.SUFFIX:
        raise TypeError(f"{ir_cls.__name__} must define a non-empty SUFFIX class attribute")
    suffix = ir_cls.SUFFIX
    if suffix in _IR_TYPES:
        existing = _IR_TYPES[suffix]
        if existing is ir_cls:
            return
        raise ValueError(
            f"SUFFIX '{suffix}' is already registered by {existing.__name__}; cannot also register {ir_cls.__name__}"
        )
    _IR_TYPES[suffix] = ir_cls


def register_renderer(renderer_cls: type[Renderer]) -> None:
    """Register a Renderer subclass. Checked in registration order."""
    if renderer_cls not in _RENDERERS:
        _RENDERERS.append(renderer_cls)


def register_compiler(compiler_cls: type[Compiler]) -> None:
    """Register a Compiler subclass. Checked in registration order."""
    if compiler_cls not in _COMPILERS:
        _COMPILERS.append(compiler_cls)


def get_ir_class_for_path(source_path: Path) -> type[SlideIR]:
    """Return the SlideIR subclass whose SUFFIX matches ``source_path``.

    Picks the type whose ``SUFFIX`` is the longest tail-match of the
    filename.  Raises ``UnknownSlideTypeError`` if no registered suffix matches.
    """
    name = source_path.name
    matches = sorted(
        (suffix for suffix in _IR_TYPES if name.endswith(suffix)),
        key=len,
        reverse=True,
    )
    if not matches:
        known = ", ".join(sorted(_IR_TYPES)) or "(none registered)"
        raise UnknownSlideTypeError(f"no slide type matches source filename '{name}' (registered suffixes: {known})")
    return _IR_TYPES[matches[0]]


def find_renderer(ir: SlideIR) -> Renderer | None:
    """Return a fresh Renderer instance that can process ``ir``, or None."""
    for cls in _RENDERERS:
        if cls.can_process(ir):
            return cls()
    return None


def find_compiler(ir: SlideIR) -> Compiler | None:
    """Return a fresh Compiler instance that can process ``ir``, or None."""
    for cls in _COMPILERS:
        if cls.can_process(ir):
            return cls()
    return None


def registered_suffixes() -> list[str]:
    """Return the list of currently registered suffixes."""
    return sorted(_IR_TYPES)


def registered_ir_types() -> dict[str, type[SlideIR]]:
    """Return a mapping of type name to IR class for all registered types."""
    return {suffix.lstrip(".").split(".")[0]: cls for suffix, cls in _IR_TYPES.items()}
