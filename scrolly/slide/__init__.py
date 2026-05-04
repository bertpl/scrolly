"""Layer B — SlideHTML contract, IR base, processors, and per-type implementations.

Importing this package registers all built-in slide types with the registry.
"""

# ---- Built-in type registration (side effect on import) -------------------
from scrolly.slide.compilers.storyboard import StoryboardCompiler  # noqa: E402
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.ir.scrollimation import ScrollimationIR  # noqa: E402
from scrolly.slide.ir.static import StaticIR  # noqa: E402
from scrolly.slide.ir.storyboard import StoryboardIR  # noqa: E402
from scrolly.slide.processor import Compiler, IRProcessor, Renderer
from scrolly.slide.registry import (
    find_compiler,
    find_renderer,
    get_ir_class_for_path,
    register_compiler,
    register_ir,
    register_renderer,
    registered_ir_types,
    registered_suffixes,
)
from scrolly.slide.renderers.scrollimation import ScrollimationRenderer  # noqa: E402
from scrolly.slide.renderers.static import StaticRenderer  # noqa: E402

register_ir(StaticIR)
register_ir(ScrollimationIR)
register_ir(StoryboardIR)

register_renderer(StaticRenderer)
register_renderer(ScrollimationRenderer)

register_compiler(StoryboardCompiler)

__all__ = [
    "SlideHTML",
    "Compiler",
    "IRProcessor",
    "Renderer",
    "SlideIR",
    "find_compiler",
    "find_renderer",
    "get_ir_class_for_path",
    "register_compiler",
    "register_ir",
    "register_renderer",
    "registered_ir_types",
    "registered_suffixes",
]
