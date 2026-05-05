"""ABC hierarchy for IR processors: renderers and compilers.

Renderers convert an IR into a SlideHTML (terminal).  Compilers convert an
IR into another IR (intermediate).  Both share the ``can_process``
dispatch classmethod via ``IRProcessor``.
"""

from __future__ import annotations

import abc

from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR


class IRProcessor(abc.ABC):
    """Base for all IR processors."""

    @classmethod
    @abc.abstractmethod
    def can_process(cls, ir: SlideIR) -> bool: ...


class Renderer(IRProcessor, abc.ABC):
    """Converts an IR into a SlideHTML."""

    @abc.abstractmethod
    def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML: ...


class Compiler(IRProcessor, abc.ABC):
    """Converts an IR into another IR."""

    @abc.abstractmethod
    def compile(self, ir: SlideIR) -> SlideIR: ...
