"""Render a StaticIR into a SlideHTML."""

from __future__ import annotations

import re
from typing import ClassVar

import markdown

from scrolly.errors import SlideSourceError
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import SlideIR
from scrolly.slide.ir.static import StaticIR
from scrolly.slide.processor import Renderer


class StaticRenderer(Renderer):
    """Renderer for the `static` slide type."""

    _MD_EXTENSIONS: ClassVar[tuple[str, ...]] = (
        "fenced_code",
        "tables",
        "sane_lists",
    )

    _H1_RE: ClassVar[re.Pattern[str]] = re.compile(r"^# +(.+?)\s*$", re.MULTILINE)

    _SCOPED_CSS: ClassVar[str] = """\
.slide-type-static-md {
  padding-top: max(4rem, var(--chrome-safe-top));
  padding-right: max(4rem, var(--chrome-safe-right));
  padding-bottom: max(4rem, var(--chrome-safe-bottom));
  padding-left: max(4rem, var(--chrome-safe-left));
}

.slide-type-static-md h1 {
  margin-top: 0;
}

.slide-type-static-md pre {
  background: #f0f0f0;
  padding: 0.75rem 1rem;
  border-radius: 4px;
  overflow: auto;
}

.slide-type-static-md code {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
"""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        return isinstance(ir, StaticIR)

    def render(self, ir: SlideIR, css_namespace: str = "") -> SlideHTML:
        assert isinstance(ir, StaticIR)
        title = ir.title or self._extract_first_h1(ir.body)
        if title is None:
            raise SlideSourceError("could not determine title — provide a frontmatter 'title' field or a top-level H1")

        body_html = markdown.markdown(ir.body, extensions=list(self._MD_EXTENSIONS))
        slide_type = ir.slide_type
        html = f'<div class="slide-type-{slide_type}">{body_html}</div>'

        try:
            return SlideHTML(
                title=title,
                html=html,
                scoped_css=self._SCOPED_CSS,
                initial_scroll_position=ir.initial_scroll_position,
                font_scale=ir.font_scale,
            )
        except ValueError as e:
            raise SlideSourceError(str(e)) from e

    @staticmethod
    def _extract_first_h1(body: str) -> str | None:
        match = StaticRenderer._H1_RE.search(body)
        return match.group(1).strip() if match else None
