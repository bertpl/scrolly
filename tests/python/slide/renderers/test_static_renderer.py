from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir.static import StaticIR
from scrolly.slide.renderers.static import StaticRenderer


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def _build(source_path: Path):
    ir = StaticIR.from_file(source_path)
    return StaticRenderer().render(ir)


def test_renders_minimal_slide(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# Title\n\nBody paragraph.",
    )
    chunk = _build(src)
    assert chunk.title == "Title"
    assert "<h1>Title</h1>" in chunk.html
    assert "<p>Body paragraph.</p>" in chunk.html
    # static is content-driven — runtime computes scroll_range from overflow.
    assert chunk.scroll_range is None
    assert chunk.initial_scroll_position == 0


def test_title_defaults_to_first_h1(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# First H1\n\nMore text\n\n# Second H1",
    )
    chunk = _build(src)
    assert chunk.title == "First H1"


def test_frontmatter_title_overrides_h1(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\ntitle: From Frontmatter\n---\n# H1 Body Title",
    )
    chunk = _build(src)
    assert chunk.title == "From Frontmatter"


def test_frontmatter_title_used_when_no_h1(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\ntitle: Just FM\n---\nBody with no h1.",
    )
    chunk = _build(src)
    assert chunk.title == "Just FM"


def test_missing_title_raises(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n## Only H2 here\n\nBody text.",
    )
    with pytest.raises(SlideSourceError, match="could not determine title"):
        _build(src)


def test_h1_with_inline_formatting_kept_as_literal(tmp_path):
    # The plan: title is a plain string; markdown inline formatting in the
    # H1 line is kept as raw text rather than rendered. The hover pill
    # decides display; for now we just preserve the source.
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# Title with **bold** and `code`",
    )
    chunk = _build(src)
    assert chunk.title == "Title with **bold** and `code`"


def test_code_block_rendered(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\ntitle: Code\n---\n```py\nprint('hi')\n```",
    )
    chunk = _build(src)
    # fenced_code extension renders code blocks with <pre> and <code>
    assert "<pre>" in chunk.html
    assert "<code" in chunk.html


def test_missing_file_raises():
    with pytest.raises(SlideSourceError, match="not found"):
        _build(Path("/definitely/does/not/exist.slide.md"))


def test_nonzero_initial_position_passes_through_to_chunk(tmp_path):
    # `static` is content-driven — the upper-bound check on
    # initial_scroll_position vs scroll_range moves to the runtime
    # (where the live range is observed). At build time we just store
    # the author-declared value; a value larger than the runtime range
    # gets clamped at runtime.
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 42\n---\n# x",
    )
    chunk = _build(src)
    assert chunk.initial_scroll_position == 42
    assert chunk.scroll_range is None


def test_renders_l_shape_fixture_slides(tmp_path):
    # Build the three L-shape slides and verify each renders cleanly.
    for name in ("intro", "details", "appendix"):
        _write(
            tmp_path,
            f"{name}.slide.md",
            f"---\ninitial_scroll_position: 0\n---\n# {name.title()}\n",
        )
    for name in ("intro", "details", "appendix"):
        chunk = _build(tmp_path / f"{name}.slide.md")
        assert chunk.title == name.title()
        assert f"<h1>{name.title()}</h1>" in chunk.html


def test_font_scale_defaults_to_one_when_absent(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# x",
    )
    chunk = _build(src)
    assert chunk.font_scale == 1.0


def test_font_scale_passes_through_to_chunk(tmp_path):
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\nfont_scale: 1.4\n---\n# x",
    )
    chunk = _build(src)
    assert chunk.font_scale == 1.4


def test_emitted_html_wraps_in_slide_type_static_div(tmp_path):
    # Static renderer wraps its rendered markdown in a type-namespacing
    # div so its scoped_css (`.slide-type-static-md …`) targets only static
    # content and doesn't collide with future types' scoped CSS.
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# Title\n\nBody.",
    )
    chunk = _build(src)
    assert chunk.html.startswith('<div class="slide-type-static-md">')
    assert chunk.html.endswith("</div>")
    # The markdown-rendered content sits inside the wrapper.
    assert "<h1>Title</h1>" in chunk.html
    assert "<p>Body.</p>" in chunk.html


def test_emitted_scoped_css_floors_padding_against_chrome_safe(tmp_path):
    # Static's padding policy: max(4rem, var(--chrome-safe-{side})) per
    # side. On big viewports 4rem dominates; on small viewports the
    # chrome-safe floor takes over so nav UI never overlaps content.
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# Title",
    )
    chunk = _build(src)
    assert ".slide-type-static-md {" in chunk.scoped_css
    for side in ("top", "right", "bottom", "left"):
        expected = f"padding-{side}: max(4rem, var(--chrome-safe-{side}))"
        assert expected in chunk.scoped_css, (
            f"expected `{expected}` floored against chrome-safe inset for the {side} side"
        )


def test_emitted_scoped_css_carries_pre_h1_and_code_rules(tmp_path):
    # Markdown-specific styling (h1 margin-top, pre block, inline code
    # font) lives in static's scoped_css now, not in canvas.css. Future
    # non-markdown slide types simply don't carry these rules.
    src = _write(
        tmp_path,
        "s.slide.md",
        "---\ninitial_scroll_position: 0\n---\n# Title",
    )
    chunk = _build(src)
    assert ".slide-type-static-md h1 {" in chunk.scoped_css
    assert ".slide-type-static-md pre {" in chunk.scoped_css
    assert ".slide-type-static-md code {" in chunk.scoped_css
