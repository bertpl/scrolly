"""``Renderer`` ABC — single-step ``SlideIR → SlideHTML`` conversion.

With the v0.2.0 collapse to a single slide type the ABC is dormant — one
concrete subclass (``SlideRenderer``) is the only registered renderer —
but kept so a future second type can register without re-architecting
the dispatch surface.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR

if TYPE_CHECKING:
    from scrolly.pipeline._bundler import PayloadBundler


class Renderer(abc.ABC):
    """Converts a ``SlideIR`` into a ``SlideHTML``."""

    @classmethod
    @abc.abstractmethod
    def can_process(cls, ir: SlideIR) -> bool: ...

    @abc.abstractmethod
    def render(
        self,
        ir: SlideIR,
        css_namespace: str = "",
        *,
        bundler: PayloadBundler | None = None,
    ) -> SlideHTML: ...
