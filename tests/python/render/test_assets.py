"""Invariant checks on the static assets shipped by `scrolly.render`."""

from __future__ import annotations

from importlib.resources import files


def _read_asset(name: str) -> str:
    return (files("scrolly.render.assets") / name).read_text()


def test_subcanvas_is_z_index_isolated():
    """Layer A's UI must be guaranteed-on-top relative to chunk content.

    `isolation: isolate` on `.subcanvas` forces every subcanvas to be its
    own stacking context, so any z-index a chunk uses internally is local
    and cannot compete with siblings of `.slide-container` (e.g. the bezier
    overlay at z-index 5 or any future within-canvas Layer A overlay).
    """
    css = _read_asset("canvas.css")
    # Find the .subcanvas rule and assert isolation: isolate is in it.
    # The block can have other properties; we just check the property
    # appears between the `.subcanvas {` and the matching `}`.
    start = css.index(".slide-container .subcanvas {")
    end = css.index("}", start)
    block = css[start:end]
    assert "isolation: isolate" in block, "expected `.subcanvas { isolation: isolate; ... }` to sandbox chunk z-index"


def test_root_font_size_is_viewport_proportional():
    """SlideHTML text scales with viewport; UA-stylesheet em-keyed headings inherit it.

    Setting `:root { font-size: <viewport-unit> }` makes every rem and
    UA-stylesheet em multiplier viewport-relative. The baseline is a
    linear combination of vw and vh (sum of dimensions), so both axes
    contribute — bigger external monitors get noticeably bigger text
    than laptops without narrow split-views falling off a cliff.
    """
    css = _read_asset("canvas.css")
    start = css.index(":root {")
    end = css.index("}", start)
    block = css[start:end]
    assert "font-size:" in block, "expected `:root { font-size: ... }` to set the viewport-proportional rem baseline"
    assert "vw" in block and "vh" in block, "expected the rem baseline to use a vw + vh combination"


def test_chunk_no_longer_carries_padding_in_canvas_css():
    """Padding is a per-slide-type concern (carried by SlideHTML.scoped_css),
    not a universal canvas.css rule. Each slide-type renderer emits its
    own padding policy in scoped_css. canvas.css's `.chunk` rule keeps
    only structural rules (width, min-height, box-sizing, scroll
    transform) and Layer A's universal --font-scale plumbing.
    """
    css = _read_asset("canvas.css")
    start = css.index(".slide-container .chunk {")
    end = css.index("}", start)
    block = css[start:end]
    # Match the declaration syntax (`padding:` with colon) rather than the
    # word "padding" alone, so the explanatory comment in this rule is fine.
    assert "padding:" not in block, (
        "expected `.chunk` rule to no longer set padding (content-presentation moved to per-type scoped_css in v0.0.7)"
    )


def test_chrome_safe_insets_declared_at_root():
    """Layer A publishes its chrome reach as four CSS custom properties
    on `:root`. Each slide-type's scoped_css can read these as a floor
    for its padding policy via `var(--chrome-safe-{side})`.
    """
    css = _read_asset("canvas.css")
    for side in ("top", "right", "bottom", "left"):
        assert f"--chrome-safe-{side}:" in css, (
            f"expected `--chrome-safe-{side}` declared on :root for Layer B types to consume"
        )


def test_scrollbar_offset_macos_style_2px_inset():
    """Scrollbar at `left: 2px` — macOS-native feel, nearly flush with the
    viewport edge. 2px inset on all three sides (left, top, bottom).
    """
    css = _read_asset("canvas.css")
    start = css.index(".slide-scrollbar {")
    end = css.index("}", start)
    block = css[start:end]
    assert "left: 2px" in block, "expected `.slide-scrollbar { left: 2px; ... }` for macOS-style inset"


def test_chunk_pre_and_h1_rules_no_longer_in_canvas_css():
    """Markdown-specific rules (`.chunk pre`, `.chunk h1`, `.chunk code`)
    moved to static's scoped_css in v0.0.7 — they aren't universal Layer
    A rules; they're static-type content-presentation, and future
    non-markdown types may not have these elements at all.
    """
    css = _read_asset("canvas.css")
    assert ".slide-container .chunk pre" not in css
    assert ".slide-container .chunk h1" not in css
    assert ".slide-container .chunk code" not in css
