"""``ElementIR`` — base for authored elements within a slide.

``ElementIR`` is the base for everything an author can place in a slide,
high-level or primitive. ``PrimitiveElement`` marks the closed set of
types the element renderer can emit directly — the bottom of the
compile-lowering chain.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ElementIR(BaseModel, frozen=True):
    """Base for all authored elements within a slide.

    Concrete subclasses carry content and substrate fields. The element
    compile loop dispatches by ``can_process`` over registered
    ``ElementCompiler`` and ``ElementRenderer`` classes.
    """

    model_config = ConfigDict(extra="forbid")


class PrimitiveElement(ElementIR):
    """Marker for ``ElementIR`` subclasses the renderer can emit directly.

    The compile loop terminates on instances of ``PrimitiveElement``:
    instead of invoking a compiler, it finds a registered
    ``ElementRenderer`` and calls it to produce the rendered
    contribution bundle.
    """
