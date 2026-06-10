"""Tests for the slide renderer — HTML emission + metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.slide.ir.slide import SlideIR
from scrolly.slide.renderers.slide import SlideRenderer


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _renderer() -> SlideRenderer:
    return SlideRenderer()


def _build(source_path: Path):
    ir = SlideIR.from_file(source_path)
    return _renderer().render(ir)


MINIMAL = """\
{
  title: "Test slide",
  scroll_range: 1000,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
"""


def test_suffix() -> None:
    assert SlideIR.SUFFIX == ".slide.json"


def test_slide_type_property() -> None:
    ir = SlideIR(
        title="T",
        scroll_range=100,
        elements=[{"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}],
    )
    assert ir.slide_type == "slide-json"


def test_registered() -> None:
    from scrolly.slide.registry import registered_suffixes

    assert ".slide.json" in registered_suffixes()


def test_wrapper_div(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    # MINIMAL uses a numeric scroll_range, so the wrapper opts into
    # the animation-mode counter-translate via the class. The base
    # class is always present.
    assert "slide-type-slide-json" in chunk.html
    assert "scroll-mode-animation" in chunk.html


def test_layer_div_with_data_id(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert '<div class="slide-element" data-element-id="0">' in chunk.html


def test_html_layer_content_passthrough(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "<p>hi</p>" in chunk.html


def test_markdown_layer_rendered(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", markdown: "# Hello\\n\\nWorld", position: [0, 0], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "<h1>Hello</h1>" in chunk.html
    assert "<p>World</p>" in chunk.html


def test_asset_layer_emits_img_with_asset_prefix(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "hero.jpg", "fake image")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "bg", image: "hero.jpg", position: [0, 0], width: 100, height: 120, object_fit: "cover" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert '<img src="__asset__/hero.jpg" alt="">' in chunk.html


def test_multiple_layers_all_present(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "img.svg", "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "bg", image: "img.svg", position: [0, 0], width: 100, height: 100, object_fit: "cover" },
    { name: "sep", html: "<div>box</div>", position: [0, 0], width: 100, height: 100 },
    { name: "txt", markdown: "# Cap", position: [10, 40], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'data-element-id="0"' in chunk.html
    assert 'data-element-id="1"' in chunk.html
    assert 'data-element-id="2"' in chunk.html


def test_mermaid_layer_emits_pre_tag(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert '<pre class="mermaid">' in chunk.html
    assert "graph LR" in chunk.html


def test_mermaid_content_html_escaped(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "dia", mermaid: "graph LR\\n  A -->|<yes>| B", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "&lt;yes&gt;" in chunk.html


def test_has_mermaid_flag_set(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.has_mermaid is True


def test_has_mermaid_flag_false_without_mermaid(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.has_mermaid is False


def test_mermaid_scoped_css(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert ".mermaid svg" in chunk.scoped_css


def test_layer_order_matches_source(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "first", html: "<p>1</p>", position: [0, 0], width: 100, height: 100 },
    {name: "second", html: "<p>2</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)
    pos_first = chunk.html.index('data-element-id="0"')
    pos_second = chunk.html.index('data-element-id="1"')

    # --- assert -----------------------
    assert pos_first < pos_second


def test_chunk_assets_populated_for_asset_layer(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "hero.jpg", "fake")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "bg", image: "hero.jpg", position: [0, 0], width: 100, height: 120, object_fit: "cover" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert len(chunk.assets) == 1
    assert chunk.assets[0].name == "hero.jpg"
    assert chunk.assets[0].is_absolute()


def test_chunk_assets_empty_for_non_asset_layers(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.assets == ()


def test_multiple_asset_layers(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "a.jpg", "fake")
    _write(tmp_path / "b.svg", "fake")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bg", image: "a.jpg", position: [0, 0], width: 100, height: 100, object_fit: "cover" },
    {name: "mid", html: "<div></div>", position: [0, 0], width: 100, height: 100 },
    {name: "fg", image: "b.svg", position: [0, 0], width: 100, height: 100, object_fit: "contain" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert len(chunk.assets) == 2
    names = {p.name for p in chunk.assets}
    assert names == {"a.jpg", "b.svg"}


def test_title(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.title == "Test slide"


def test_scroll_range_fixed_timeline(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.scroll_range == 1000


def test_scroll_range_zero_stays_zero(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 0,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    # An explicit 0 means "static slide" — it must not be conflated
    # with None (content-driven mode, where overflowing content would
    # make the slide physically scroll).
    assert chunk.scroll_range == 0
    assert "scroll-mode-animation" in chunk.html


def test_initial_scroll_position(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 1000,
  initial_scroll_position: 200,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.initial_scroll_position == 200


def test_scroll_speed(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 1000,
  scroll_speed: 0.5,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.scroll_speed == 0.5


def test_snap_positions_default_empty(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.snap_positions == ()


def test_snap_positions_flow_to_chunk(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 1000,
  snap_positions: [0, 500, 1000],
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.snap_positions == (0, 500, 1000)


def test_reverse_default_false(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.reverse is False


def test_reverse_flag_flows_to_chunk(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 1000,
  reverse: true,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.reverse is True


# ── Scoped CSS: static positioning ────────────────────────────────


def test_scoped_css_is_non_empty(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.scoped_css


def test_per_element_css_present(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    # The per-element rule is what's left in scoped_css after the
    # wrapper rules moved to canvas.css. Verify at least one such
    # rule is emitted.
    assert 'data-element-id="0"' in chunk.scoped_css


def test_left_top_from_static_position(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [15, 10], width: 80, height: 60 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "left: 15%" in chunk.scoped_css
    assert "top: 10%" in chunk.scoped_css


def test_default_initial_translate_zero(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [25, 50], width: 50, height: 50 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "left: 25%" in chunk.scoped_css
    assert "top: 50%" in chunk.scoped_css


def test_numeric_size(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 80, height: 60 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "width: 80%" in chunk.scoped_css
    assert "height: 60%" in chunk.scoped_css


def test_auto_height(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "width: 80%" in chunk.scoped_css
    assert "height: auto" in chunk.scoped_css


def test_auto_width(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "L", html: "<p>hi</p>", position: [0, 0], width: "auto", height: 50 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "width: auto" in chunk.scoped_css
    assert "height: 50%" in chunk.scoped_css


def test_text_align_center(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", markdown: "# Hi", position: [0, 0], width: 80, height: "auto", text_align: "center" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "text-align: center" in chunk.scoped_css


def test_text_align_default_not_emitted(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "L", markdown: "# Hi", position: [0, 0], width: 80, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "text-align" not in chunk.scoped_css


def test_anchor_sets_transform_origin_and_translate(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100, anchor: [50, 50] },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "transform-origin: 50% 50%" in chunk.scoped_css
    assert "translate(-50%, -50%)" in chunk.scoped_css


def test_default_anchor_no_translate(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", MINIMAL)

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "transform-origin: 0% 0%" in chunk.scoped_css
    assert "translate(" not in chunk.scoped_css


def test_animated_anchor_generates_calc_expressions(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 1000,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [50, 50], width: 100, height: 100, anchor: { keyframes: [[0, [50, 0]], [1000, [50, 100]]] } },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "calc(" in chunk.scoped_css
    assert "transform-origin:" in chunk.scoped_css
    assert "-1 *" in chunk.scoped_css


def test_initial_scale_and_rotate(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100, scale: 2, angle: 45 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "scale(2" in chunk.scoped_css
    assert "rotate(45deg)" in chunk.scoped_css


def test_initial_opacity(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "L", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100, opacity: 0.5 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "opacity: 0.5" in chunk.scoped_css


@pytest.mark.parametrize("object_fit", ["cover", "contain"])
def test_object_fit_passed_through(tmp_path: Path, object_fit: str) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "img.jpg", "fake")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bg", image: "img.jpg", position: [0, 0], width: 100, height: 120, object_fit: "%s" },
  ],
}
"""
        % object_fit,
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert f"object-fit: {object_fit}" in chunk.scoped_css


def test_auto_size_emits_img_rule_without_object_fit(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "img.jpg", "fake")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bg", image: "img.jpg", position: [0, 0], width: 100, height: "auto" },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "object-fit" not in chunk.scoped_css
    assert "] img {" in chunk.scoped_css
    assert "width: 100%" in chunk.scoped_css
    assert "height: 100%" in chunk.scoped_css


def test_z_index_follows_array_order(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bottom", html: "<p>1</p>", position: [0, 0], width: 100, height: 100 },
    {name: "middle", html: "<p>2</p>", position: [0, 0], width: 100, height: 100 },
    {name: "top", html: "<p>3</p>", position: [0, 0], width: 100, height: 100 },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)
    css = chunk.scoped_css
    bottom_section = css[css.index('data-element-id="0"') :]
    middle_section = css[css.index('data-element-id="1"') :]
    top_section = css[css.index('data-element-id="2"') :]

    # --- assert -----------------------
    assert "z-index: 0" in bottom_section.split("}")[0]
    assert "z-index: 1" in middle_section.split("}")[0]
    assert "z-index: 2" in top_section.split("}")[0]


# ── ImageSequenceElement ──────────────────────────────────────────


def _seq_slide(images: list[str], **extra: object) -> str:
    """Build a JSON5 source for a slide with a single image-sequence element."""
    image_list = "[" + ", ".join(f'"{name}"' for name in images) + "]"
    extra_lines = "".join(f"      {k}: {repr(v) if isinstance(v, str) else v},\n" for k, v in extra.items())
    return (
        "{\n"
        '  title: "T",\n'
        "  scroll_range: 2000,\n"
        "  elements: [\n"
        "    {\n"
        f'      name: "seq",\n'
        f"      image_sequence: {image_list},\n"
        f"      frame_distance: 400,\n"
        f"      hold_fraction: 0.5,\n"
        f"      position: [0, 0],\n"
        f"      width: 80,\n"
        f'      height: "auto",\n'
        f"{extra_lines}"
        "    },\n"
        "  ],\n"
        "}\n"
    )


def test_one_img_per_unique_consecutive_path(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.html.count("<img ") == 3


def test_consecutive_repeats_collapse_to_one_img(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        _seq_slide(["a.svg", "b.svg", "b.svg", "b.svg", "c.svg"]),
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.html.count("<img ") == 3


def test_data_frame_index_uses_run_start(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        _seq_slide(["a.svg", "b.svg", "b.svg", "c.svg"]),
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'data-frame-index="0"' in chunk.html
    assert 'data-frame-index="1"' in chunk.html
    assert 'data-frame-index="3"' in chunk.html
    assert 'data-frame-index="2"' not in chunk.html


def test_each_img_has_data_opacity_keyframes(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.html.count("data-opacity-keyframes") == 3


def test_img_src_uses_asset_prefix(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        assert f'src="__asset__/{name}"' in chunk.html


def test_empty_slot_emits_no_img(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "", "b.svg"]))

    # --- act --------------------------
    chunk = _build(src)
    # Two real frames -> two <img> tags; the empty slot emits nothing.

    # --- assert -----------------------
    assert chunk.html.count("<img ") == 2
    # No data-frame-index="1" since that slot is empty.
    assert 'data-frame-index="0"' in chunk.html
    assert 'data-frame-index="1"' not in chunk.html
    assert 'data-frame-index="2"' in chunk.html


def test_consecutive_empty_slots_emit_no_img(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "", "", "b.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert chunk.html.count("<img ") == 2


def test_asset_paths_resolved_and_unique(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        _seq_slide(["a.svg", "b.svg", "b.svg", "c.svg"]),
    )

    # --- act --------------------------
    chunk = _build(src)
    names = [p.name for p in chunk.assets]

    # --- assert -----------------------
    assert sorted(names) == ["a.svg", "b.svg", "c.svg"]


def test_assets_are_absolute_paths(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    for path in chunk.assets:
        assert path.is_absolute()


def test_empty_slots_excluded_from_assets(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "", "b.svg", ""]))

    # --- act --------------------------
    chunk = _build(src)
    names = sorted(p.name for p in chunk.assets)

    # --- assert -----------------------
    assert names == ["a.svg", "b.svg"]


def test_first_img_in_flow_rest_absolute_for_stacking(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg"]))

    # --- act --------------------------
    chunk = _build(src)
    # Base img rule covers all imgs and does NOT use absolute positioning
    # (the first img must stay in normal flow so it establishes the box height).
    base_idx = chunk.scoped_css.index("img {")
    base_section = chunk.scoped_css[base_idx : base_idx + chunk.scoped_css[base_idx:].index("}")]

    # --- assert -----------------------
    assert "position: absolute" not in base_section
    # The :not(:first-of-type) rule overlays the rest.
    assert "img:not(:first-of-type)" in chunk.scoped_css
    stack_idx = chunk.scoped_css.index("img:not(:first-of-type)")
    stack_section = chunk.scoped_css[stack_idx : stack_idx + chunk.scoped_css[stack_idx:].index("}")]
    assert "position: absolute" in stack_section
    assert "top: 0" in stack_section
    assert "left: 0" in stack_section


def test_per_run_opacity_rule_emitted(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg", "c.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'img[data-frame-index="0"]' in chunk.scoped_css
    assert 'img[data-frame-index="1"]' in chunk.scoped_css
    assert 'img[data-frame-index="2"]' in chunk.scoped_css
    assert "opacity: calc(" in chunk.scoped_css


def test_object_fit_emitted_when_set(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        _seq_slide(["a.svg", "b.svg"], height=100, object_fit="cover"),
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "object-fit: cover" in chunk.scoped_css


def test_no_opacity_rule_for_empty_slot(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(tmp_path / "s.slide.json", _seq_slide(["a.svg", "", "b.svg"]))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'img[data-frame-index="0"]' in chunk.scoped_css
    assert 'img[data-frame-index="1"]' not in chunk.scoped_css
    assert 'img[data-frame-index="2"]' in chunk.scoped_css


def test_run_keyframes_basic() -> None:
    from pathlib import Path

    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )
    from scrolly.slide.ir import ImageSequenceElement

    el = ImageSequenceElement(
        image_sequence=[Path("a.svg"), Path("b.svg"), Path("c.svg"), Path("d.svg")],
        frame_distance=400,
        hold_fraction=0.5,
        scroll_offset=0,
        position=[0, 0],
        width=80,
        height="auto",
    )
    runs = _image_sequence_runs(list(el.image_sequence))
    assert len(runs) == 4
    # Snaps at 0/400/800/1200; symmetric hold half-width = 0.5*400/2 = 100;
    # crossfade = 400*(1-0.5) = 200.
    assert _image_sequence_run_keyframes(el, runs, 0) == [(0.0, 1.0), (100.0, 1.0), (300.0, 0.0)]
    assert _image_sequence_run_keyframes(el, runs, 1) == [
        (100.0, 0.0),
        (300.0, 1.0),
        (500.0, 1.0),
        (700.0, 0.0),
    ]
    assert _image_sequence_run_keyframes(el, runs, 3) == [(900.0, 0.0), (1100.0, 1.0), (1200.0, 1.0)]


def test_runs_group_consecutive_empty_slots() -> None:
    from pathlib import Path

    from scrolly.slide.element_ir.renderers.image_sequence import _image_sequence_runs

    runs = _image_sequence_runs([Path("a.svg"), None, None, Path("b.svg")])
    # Two consecutive Nones collapse to a single run, just like two identical paths would.
    assert runs == [(Path("a.svg"), 0, 0), (None, 1, 2), (Path("b.svg"), 3, 3)]


def test_real_frame_keyframes_unchanged_by_empty_slot() -> None:
    from pathlib import Path

    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )
    from scrolly.slide.ir import ImageSequenceElement

    el = ImageSequenceElement(
        image_sequence=[Path("a.svg"), None, Path("b.svg")],
        frame_distance=400,
        hold_fraction=0.5,
        scroll_offset=0,
        position=[0, 0],
        width=80,
        height="auto",
    )
    runs = _image_sequence_runs(list(el.image_sequence))
    # A (first, not last) fades out into the empty slot's hold window.
    assert _image_sequence_run_keyframes(el, runs, 0) == [(0.0, 1.0), (100.0, 1.0), (300.0, 0.0)]
    # B (not first, last) fades in out of the empty slot's hold window.
    assert _image_sequence_run_keyframes(el, runs, 2) == [(500.0, 0.0), (700.0, 1.0), (800.0, 1.0)]
    # The empty slot's hold [300, 500] sits cleanly between A's fade-out end and B's fade-in start.


def test_run_keyframes_with_repeats() -> None:
    from pathlib import Path

    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )
    from scrolly.slide.ir import ImageSequenceElement

    el = ImageSequenceElement(
        image_sequence=[Path("a.svg"), Path("b.svg"), Path("b.svg"), Path("c.svg")],
        frame_distance=400,
        hold_fraction=0.5,
        scroll_offset=0,
        position=[0, 0],
        width=80,
        height="auto",
    )
    runs = _image_sequence_runs(list(el.image_sequence))
    # b is run [1, 2]: hold from 300 to 900 (snaps 400 and 800, each ±100)
    assert runs[1] == (Path("b.svg"), 1, 2)
    b_kfs = _image_sequence_run_keyframes(el, runs, 1)
    assert b_kfs == [(100.0, 0.0), (300.0, 1.0), (900.0, 1.0), (1100.0, 0.0)]


def test_run_keyframes_with_fade_in_out() -> None:
    from pathlib import Path

    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )
    from scrolly.slide.ir import ImageSequenceElement

    el = ImageSequenceElement(
        image_sequence=[Path("a.svg"), Path("b.svg")],
        frame_distance=400,
        hold_fraction=0.5,
        scroll_offset=500,
        fade_in=300,
        fade_out=150,
        position=[0, 0],
        width=80,
        height="auto",
    )
    runs = _image_sequence_runs(list(el.image_sequence))
    # First run (snap 500): fade-in side half = 0.5*300/2 = 75 → hold_lo 425;
    # ramp from 500-300 = 200; interior side half = 100 → hold_hi 600; crossfade 200.
    assert _image_sequence_run_keyframes(el, runs, 0) == [
        (200.0, 0.0),
        (425.0, 1.0),
        (600.0, 1.0),
        (800.0, 0.0),
    ]
    # Last run (snap 900): hold_lo 800; fade-out side half = 0.5*150/2 = 37.5 → hold_hi
    # 937.5; timeline ends at last_snap + fade_out = 900 + 150 = 1050.
    assert _image_sequence_run_keyframes(el, runs, 1) == [
        (600.0, 0.0),
        (800.0, 1.0),
        (937.5, 1.0),
        (1050.0, 0.0),
    ]


# Element-derived snaps (image-sequence frame grid) merge into the chunk.


def _image_seq_ir(scroll_range: int, snap_positions: tuple[int, ...] = ()) -> SlideIR:
    return SlideIR(
        title="T",
        scroll_range=scroll_range,
        snap_positions=list(snap_positions),
        elements=[
            {
                "image_sequence": ["a.svg", "b.svg", "c.svg"],
                "frame_distance": 400,
                "hold_fraction": 0.5,
                "scroll_offset": 0,
                "position": [0, 0],
                "width": 80,
                "height": "auto",
            }
        ],
    )


def test_derived_snaps_merged_when_no_author_snaps() -> None:
    # --- arrange / act ----------------
    chunk = _renderer().render(_image_seq_ir(scroll_range=1000))

    # --- assert -----------------------
    # frame grid = scroll_offset + i*frame_distance → 0, 400, 800
    assert chunk.snap_positions == (0.0, 400.0, 800.0)


def test_author_and_derived_snaps_merged_sorted() -> None:
    # --- arrange / act ----------------
    chunk = _renderer().render(_image_seq_ir(scroll_range=1000, snap_positions=(200, 1000)))

    # --- assert -----------------------
    assert chunk.snap_positions == (0.0, 200, 400.0, 800.0, 1000)


def test_coinciding_author_snap_not_double_emitted() -> None:
    # --- arrange / act ----------------
    # Author 400 coincides with the middle frame's grid snap.
    chunk = _renderer().render(_image_seq_ir(scroll_range=1000, snap_positions=(400, 1000)))

    # --- assert -----------------------
    assert chunk.snap_positions == (0.0, 400, 800.0, 1000)
    assert len(chunk.snap_positions) == 4


# Per-mode coverage of the trailing-edge keyframe shape.
#
# Leading edges are identical across modes (fade-in only differs by
# ``fade_in``); the trailing edge is what each mode controls.


def _make_el(
    compositing: str = "blend",
    fade_in: float = 0,
    fade_out: float = 0,
) -> "ImageSequenceElement":
    from pathlib import Path

    from scrolly.slide.ir import ImageSequenceElement

    return ImageSequenceElement(
        image_sequence=[Path("a.svg"), Path("b.svg"), Path("c.svg"), Path("d.svg")],
        frame_distance=400,
        hold_fraction=0.5,
        scroll_offset=0,
        fade_in=fade_in,
        fade_out=fade_out,
        compositing=compositing,
        position=[0, 0],
        width=80,
        height="auto",
    )


def test_default_compositing_is_blend() -> None:
    # --- arrange / act ----------------
    el = _make_el()

    # --- assert -----------------------
    assert el.compositing == "blend"


def test_blend_mode_matches_legacy_shape() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="blend")
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act / assert -----------------
    # Symmetric crossfade: 1→0 over the crossfade window into the next run.
    assert _image_sequence_run_keyframes(el, runs, 1) == [
        (100.0, 0.0),
        (300.0, 1.0),
        (500.0, 1.0),
        (700.0, 0.0),
    ]


def test_overlay_extends_hold_and_drops_to_zero() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _STEP_RAMP_WIDTH,
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="overlay")
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act --------------------------
    kfs = _image_sequence_run_keyframes(el, runs, 1)

    # --- assert -----------------------
    # Run 1's hold extends to 700 (start of run 2's hold, i.e. where run 2
    # reaches full opacity), then drops to 0 over a tiny 1-unit ramp — a
    # true step discontinuity isn't expressible in CSS calc(), so we use a
    # near-instantaneous ramp that is visually indistinguishable from a
    # step but keeps slopes well-defined.
    assert kfs == [
        (100.0, 0.0),
        (300.0, 1.0),
        (700.0, 1.0),
        (700.0 + _STEP_RAMP_WIDTH, 0.0),
    ]


def test_overlay_last_run_behaves_like_blend() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="overlay")
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act / assert -----------------
    # No next-run hold to extend through; trailing edge is just the hold,
    # plus optional fade_out (none here).
    assert _image_sequence_run_keyframes(el, runs, 3) == [
        (900.0, 0.0),
        (1100.0, 1.0),
        (1200.0, 1.0),
    ]


def test_incremental_holds_until_sequence_end() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="incremental")
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act / assert -----------------
    # Run 0 holds at 1 from its snap (0) until the sequence's final hold
    # (1200). No fade_out, so no trailing 0 keyframe.
    assert _image_sequence_run_keyframes(el, runs, 0) == [
        (0.0, 1.0),
        (1200.0, 1.0),
    ]
    # Run 1 fades in normally, then also holds until 1200.
    assert _image_sequence_run_keyframes(el, runs, 1) == [
        (100.0, 0.0),
        (300.0, 1.0),
        (1200.0, 1.0),
    ]
    # Last run: identical trailing edge — its own hold already reaches the
    # sequence's final hold.
    assert _image_sequence_run_keyframes(el, runs, 3) == [
        (900.0, 0.0),
        (1100.0, 1.0),
        (1200.0, 1.0),
    ]


def test_incremental_fade_out_applies_to_every_run() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="incremental", fade_out=150)
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act / assert -----------------
    # Every run shares the trailing fade — final hold (1237.5) → 0 at
    # last_snap + fade_out = 1200 + 150 = 1350.
    expected_trailer = [(1237.5, 1.0), (1350.0, 0.0)]
    for run_idx in range(len(runs)):
        kfs = _image_sequence_run_keyframes(el, runs, run_idx)
        assert kfs[-2:] == expected_trailer, f"run {run_idx} trailing edge"


def test_overlay_fade_out_only_on_last_run() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _STEP_RAMP_WIDTH,
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    el = _make_el(compositing="overlay", fade_out=150)
    runs = _image_sequence_runs(list(el.image_sequence))

    # --- act / assert -----------------
    # Non-last runs still drop out at the next run's hold start;
    # only the last run uses the trailing fade_out.
    assert _image_sequence_run_keyframes(el, runs, 1)[-2:] == [
        (700.0, 1.0),
        (700.0 + _STEP_RAMP_WIDTH, 0.0),
    ]
    assert _image_sequence_run_keyframes(el, runs, 3) == [
        (900.0, 0.0),
        (1100.0, 1.0),
        (1237.5, 1.0),
        (1350.0, 0.0),
    ]


def test_fade_in_unchanged_across_modes() -> None:
    # --- arrange ----------------------
    from scrolly.slide.element_ir.renderers.image_sequence import (
        _image_sequence_run_keyframes,
        _image_sequence_runs,
    )

    # --- act / assert -----------------
    # Leading-edge fade_in keyframes are identical regardless of mode.
    for mode in ("blend", "overlay", "incremental"):
        el = _make_el(compositing=mode, fade_in=100)
        runs = _image_sequence_runs(list(el.image_sequence))
        kfs = _image_sequence_run_keyframes(el, runs, 0)
        # fade-in ramp from S - fade_in (-100) up to the hold start
        # (S - hold_fraction*fade_in/2 = -25).
        assert kfs[:2] == [(-100.0, 0.0), (-25.0, 1.0)], mode


# ── Iframe element ────────────────────────────────────────────────


IFRAME_BASE = """\
{{
  title: "T",
  scroll_range: 100,
  elements: [
    {{ {name}iframe_html: "<!doctype html><p>iframe</p>", position: [10, 10], width: 80, height: 80{decor} }},
  ],
}}
"""


def _iframe_slide(*, name: str = "", decor: str = "") -> str:
    name_field = f'name: "{name}", ' if name else ""
    return IFRAME_BASE.format(name=name_field, decor=decor)


def test_iframe_tag_with_srcdoc(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide())

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "<iframe " in chunk.html
    assert "srcdoc=" in chunk.html


def test_iframe_srcdoc_html_escaped(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide())

    # --- act --------------------------
    chunk = _build(src)
    # The raw `<p>iframe</p>` from the source becomes `&lt;p&gt;iframe&lt;/p&gt;` inside srcdoc.

    # --- assert -----------------------
    assert "&lt;p&gt;iframe&lt;/p&gt;" in chunk.html
    # And the literal `<p>iframe</p>` doesn't appear (it's only inside srcdoc, escaped).
    assert "<p>iframe</p>" not in chunk.html


def test_iframe_sandbox_allow_scripts(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide())

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'sandbox="allow-scripts"' in chunk.html


def test_iframe_title_from_name(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide(name="demo"))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert 'title="demo"' in chunk.html


def test_iframe_title_omitted_without_name(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide())

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "title=" not in chunk.html


def test_iframe_fill_css_rule(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_slide())

    # --- act --------------------------
    chunk = _build(src)
    # The wrapper-internal iframe rule sets the iframe to fill its wrapper without a default browser border.

    # --- assert -----------------------
    assert "] iframe {" in chunk.scoped_css
    idx = chunk.scoped_css.index("] iframe {")
    section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]
    assert "width: 100%" in section
    assert "height: 100%" in section
    assert "border: 0" in section
    assert "display: block" in section


def _iframe_decoration_slide(**decor) -> str:
    decor_lines = "".join(f", {k}: {v!r}" if isinstance(v, str) else f", {k}: {v}" for k, v in decor.items())
    return f"""\
{{
  title: "T",
  scroll_range: 100,
  elements: [
    {{ name: "frame", iframe_html: "<!doctype html><p>x</p>", position: [10, 10], width: 80, height: 80{decor_lines} }},
  ],
}}
"""


def test_no_decoration_by_default(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_decoration_slide())

    # --- act --------------------------
    chunk = _build(src)
    # Wrapper rule has no border, no box-shadow, no box-sizing. The iframe
    # child rule's `border: 0` is in a separate rule and not checked here.
    idx = chunk.scoped_css.index('data-element-id="0"')
    wrapper_section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]

    # --- assert -----------------------
    assert "border:" not in wrapper_section
    assert "box-shadow" not in wrapper_section
    assert "box-sizing" not in wrapper_section


def test_border_only(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_decoration_slide(border_width=4, border_color="#333"))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "border: 4px solid #333" in chunk.scoped_css
    assert "box-sizing: border-box" in chunk.scoped_css
    assert "box-shadow" not in chunk.scoped_css


def test_shadow_only(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _iframe_decoration_slide(shadow_size=12, shadow_color="rgba(0,0,0,0.3)"))

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "box-shadow: 0 0 12px rgba(0,0,0,0.3)" in chunk.scoped_css
    assert "box-sizing: border-box" in chunk.scoped_css
    # The "border: 0" line on the inner iframe is still emitted; the wrapper has no border.
    idx = chunk.scoped_css.index('data-element-id="0"')
    wrapper_section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]
    assert "border:" not in wrapper_section


def test_border_and_shadow_together(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _iframe_decoration_slide(border_width=2, border_color="#000", shadow_size=8, shadow_color="#888"),
    )

    # --- act --------------------------
    chunk = _build(src)

    # --- assert -----------------------
    assert "border: 2px solid #000" in chunk.scoped_css
    assert "box-shadow: 0 0 8px #888" in chunk.scoped_css
    assert "box-sizing: border-box" in chunk.scoped_css


def test_zero_decoration_values_emit_nothing(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _iframe_decoration_slide(border_width=0, shadow_size=0),
    )

    # --- act --------------------------
    chunk = _build(src)
    # Explicit 0 should behave identically to the default — no box-sizing override.

    # --- assert -----------------------
    assert "box-sizing" not in chunk.scoped_css


IFRAME_HTML_PAYLOAD = "<!doctype html><p>iframe body</p>"


def _iframe_bundler_slide(html_content: str) -> str:
    import json

    escaped = json.dumps(html_content)
    return (
        '{\n  title: "T",\n  scroll_range: 100,\n  elements: [\n'
        f"    {{ iframe_html: {escaped}, position: [10, 10], width: 80, height: 80 }},\n"
        "  ],\n}\n"
    )


def test_with_bundler_emits_data_scrolly_target_no_srcdoc(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    from scrolly.pipeline._bundler import PayloadBundler

    src = _write(tmp_path / "s.slide.json", _iframe_bundler_slide(IFRAME_HTML_PAYLOAD))
    ir = SlideIR.from_file(src)
    bundler = PayloadBundler()

    # --- act --------------------------------
    chunk = _renderer().render(ir, bundler=bundler)

    # --- assert ------------------------------
    assert 'data-scrolly-target="0"' in chunk.html
    assert "srcdoc=" not in chunk.html
    assert 'sandbox="allow-scripts"' in chunk.html


def test_with_bundler_registers_text_payload_for_srcdoc(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    from scrolly.pipeline._bundler import PayloadBundler

    src = _write(tmp_path / "s.slide.json", _iframe_bundler_slide(IFRAME_HTML_PAYLOAD))
    ir = SlideIR.from_file(src)
    bundler = PayloadBundler()

    # --- act --------------------------------
    _renderer().render(ir, bundler=bundler)

    # --- assert ------------------------------
    # The payload is recoverable via inline_fallback() — escaped srcdoc form.
    from html import escape as html_escape

    fallback = bundler.inline_fallback()
    assert fallback == {"0": f'srcdoc="{html_escape(IFRAME_HTML_PAYLOAD)}"'}


def test_without_bundler_emits_uncompressed_srcdoc(tmp_path: Path) -> None:
    # --- arrange ----------------------------
    src = _write(tmp_path / "s.slide.json", _iframe_bundler_slide(IFRAME_HTML_PAYLOAD))
    ir = SlideIR.from_file(src)

    # --- act --------------------------------
    chunk = _renderer().render(ir)

    # --- assert ------------------------------
    assert "srcdoc=" in chunk.html
    assert "data-scrolly-target" not in chunk.html
    assert 'sandbox="allow-scripts"' in chunk.html


def test_element_level_animated_opacity_on_outer_div(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for name in ("a.svg", "b.svg"):
        _write(tmp_path / name, "<svg/>")
    src = _write(
        tmp_path / "s.slide.json",
        """\
{
  title: "T",
  scroll_range: 2000,
  elements: [
    {
      name: "seq",
      image_sequence: ["a.svg", "b.svg"],
      frame_distance: 400,
      hold_fraction: 0.5,
      position: [0, 0],
      width: 80,
      height: "auto",
      opacity: { keyframes: [[0, 0.0], [500, 1.0]] },
    },
  ],
}
""",
    )

    # --- act --------------------------
    chunk = _build(src)
    # The outer div gets data-opacity-keyframes from element-level opacity (inherited mechanism).
    # Plus per-img data-opacity-keyframes from frame ramps.

    # --- assert -----------------------
    assert chunk.html.count("data-opacity-keyframes") == 1 + 2


# SlideHTML pass-through for scroll_range="auto" and font_scale (v0.2.0 item C/D).


def test_scroll_range_auto_maps_to_none() -> None:
    # --- arrange ----------------------------
    ir = SlideIR(
        title="T",
        scroll_range="auto",
        elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}],
    )

    # --- act --------------------------------
    chunk = _renderer().render(ir)

    # --- assert -----------------------------
    assert chunk.scroll_range is None


def test_scroll_range_zero_passes_through() -> None:
    # --- arrange ----------------------------
    ir = SlideIR(
        title="T",
        scroll_range=0,
        elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}],
    )

    # --- act --------------------------------
    chunk = _renderer().render(ir)

    # --- assert -----------------------------
    # Explicit 0 means a static slide — distinct from None (content-driven).
    assert chunk.scroll_range == 0


def test_scroll_range_positive_maps_to_int() -> None:
    # --- arrange ----------------------------
    ir = SlideIR(
        title="T",
        scroll_range=750,
        elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}],
    )

    # --- act --------------------------------
    chunk = _renderer().render(ir)

    # --- assert -----------------------------
    assert chunk.scroll_range == 750


@pytest.mark.parametrize(
    ("ir_kwargs", "expected"),
    [
        pytest.param({}, 1.0, id="default"),
        pytest.param({"font_scale": 1.75}, 1.75, id="explicit"),
    ],
)
def test_font_scale_passes_through(ir_kwargs: dict, expected: float) -> None:
    # --- arrange ----------------------------
    ir = SlideIR(
        title="T",
        scroll_range=100,
        elements=[{"html": "<p>x</p>", "position": [0, 0], "width": 100, "height": 100}],
        **ir_kwargs,
    )

    # --- act --------------------------------
    chunk = _renderer().render(ir)

    # --- assert -----------------------------
    assert chunk.font_scale == expected
