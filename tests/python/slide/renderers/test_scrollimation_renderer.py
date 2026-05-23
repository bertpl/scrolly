"""Tests for the scrollimation renderer — HTML emission + metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.renderers.scrollimation import ScrollimationRenderer


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _renderer() -> ScrollimationRenderer:
    return ScrollimationRenderer()


def _build(source_path: Path):
    ir = ScrollimationIR.from_file(source_path)
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


class TestRegistration:
    def test_suffix(self) -> None:
        assert ScrollimationIR.SUFFIX == ".scrollimation.json"

    def test_slide_type_property(self) -> None:
        ir = ScrollimationIR(
            title="T",
            scroll_range=100,
            elements=[{"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}],
        )
        assert ir.slide_type == "scrollimation-json"

    def test_registered(self) -> None:
        from scrolly.slide.registry import registered_suffixes

        assert ".scrollimation.json" in registered_suffixes()


class TestHtmlEmission:
    def test_wrapper_div(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert '<div class="slide-type-scrollimation-json">' in chunk.html

    def test_layer_div_with_data_id(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert '<div class="scrollimation-element" data-element-id="0">' in chunk.html

    def test_html_layer_content_passthrough(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert "<p>hi</p>" in chunk.html

    def test_markdown_layer_rendered(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "<h1>Hello</h1>" in chunk.html
        assert "<p>World</p>" in chunk.html

    def test_asset_layer_emits_img_with_asset_prefix(self, tmp_path: Path) -> None:
        _write(tmp_path / "hero.jpg", "fake image")
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert '<img src="__asset__/hero.jpg" alt="">' in chunk.html

    def test_multiple_layers_all_present(self, tmp_path: Path) -> None:
        _write(tmp_path / "img.svg", "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert 'data-element-id="0"' in chunk.html
        assert 'data-element-id="1"' in chunk.html
        assert 'data-element-id="2"' in chunk.html

    def test_mermaid_layer_emits_pre_tag(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert '<pre class="mermaid">' in chunk.html
        assert "graph LR" in chunk.html

    def test_mermaid_content_html_escaped(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "&lt;yes&gt;" in chunk.html

    def test_has_mermaid_flag_set(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.has_mermaid is True

    def test_has_mermaid_flag_false_without_mermaid(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.has_mermaid is False

    def test_mermaid_scoped_css(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert ".mermaid svg" in chunk.scoped_css

    def test_layer_order_matches_source(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        pos_first = chunk.html.index('data-element-id="0"')
        pos_second = chunk.html.index('data-element-id="1"')
        assert pos_first < pos_second


class TestAssets:
    def test_chunk_assets_populated_for_asset_layer(self, tmp_path: Path) -> None:
        _write(tmp_path / "hero.jpg", "fake")
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert len(chunk.assets) == 1
        assert chunk.assets[0].name == "hero.jpg"
        assert chunk.assets[0].is_absolute()

    def test_chunk_assets_empty_for_non_asset_layers(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.assets == ()

    def test_multiple_asset_layers(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.jpg", "fake")
        _write(tmp_path / "b.svg", "fake")
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert len(chunk.assets) == 2
        names = {p.name for p in chunk.assets}
        assert names == {"a.jpg", "b.svg"}


class TestMetadata:
    def test_title(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.title == "Test slide"

    def test_scroll_range_fixed_timeline(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.scroll_range == 1000

    def test_scroll_range_zero_becomes_none(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.scroll_range is None

    def test_initial_scroll_position(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.initial_scroll_position == 200

    def test_scroll_speed(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.scroll_speed == 0.5

    def test_snap_positions_default_empty(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.snap_positions == ()

    def test_snap_positions_flow_to_chunk(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.snap_positions == (0, 500, 1000)

    def test_reverse_default_false(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.reverse is False

    def test_reverse_flag_flows_to_chunk(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert chunk.reverse is True


# ── Scoped CSS: static positioning ────────────────────────────────


class TestScopedCssBase:
    def test_scoped_css_is_non_empty(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert chunk.scoped_css

    def test_wrapper_is_absolute_positioned(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert "position: absolute" in chunk.scoped_css

    def test_layers_are_absolute_with_overflow_hidden(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert "position: absolute" in chunk.scoped_css
        assert "overflow: hidden" in chunk.scoped_css


class TestScopedCssPosition:
    def test_left_top_from_static_position(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "left: 15%" in chunk.scoped_css
        assert "top: 10%" in chunk.scoped_css

    def test_default_initial_translate_zero(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "left: 25%" in chunk.scoped_css
        assert "top: 50%" in chunk.scoped_css


class TestScopedCssSize:
    def test_numeric_size(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "width: 80%" in chunk.scoped_css
        assert "height: 60%" in chunk.scoped_css

    def test_auto_height(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "width: 80%" in chunk.scoped_css
        assert "height: auto" in chunk.scoped_css

    def test_auto_width(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "width: auto" in chunk.scoped_css
        assert "height: 50%" in chunk.scoped_css


class TestScopedCssMarkdown:
    def test_text_align_center(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "text-align: center" in chunk.scoped_css

    def test_text_align_default_not_emitted(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "text-align" not in chunk.scoped_css


class TestScopedCssTransform:
    def test_anchor_sets_transform_origin_and_translate(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "transform-origin: 50% 50%" in chunk.scoped_css
        assert "translate(-50%, -50%)" in chunk.scoped_css

    def test_default_anchor_no_translate(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", MINIMAL)
        chunk = _build(src)
        assert "transform-origin: 0% 0%" in chunk.scoped_css
        assert "translate(" not in chunk.scoped_css

    def test_animated_anchor_generates_calc_expressions(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "calc(" in chunk.scoped_css
        assert "transform-origin:" in chunk.scoped_css
        assert "-1 *" in chunk.scoped_css

    def test_initial_scale_and_rotate(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "scale(2" in chunk.scoped_css
        assert "rotate(45deg)" in chunk.scoped_css

    def test_initial_opacity(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "opacity: 0.5" in chunk.scoped_css


class TestScopedCssAssetLayer:
    def test_object_fit_cover(self, tmp_path: Path) -> None:
        _write(tmp_path / "img.jpg", "fake")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bg", image: "img.jpg", position: [0, 0], width: 100, height: 120, object_fit: "cover" },
  ],
}
""",
        )
        chunk = _build(src)
        assert "object-fit: cover" in chunk.scoped_css

    def test_object_fit_contain(self, tmp_path: Path) -> None:
        _write(tmp_path / "img.jpg", "fake")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {name: "bg", image: "img.jpg", position: [0, 0], width: 100, height: 120, object_fit: "contain" },
  ],
}
""",
        )
        chunk = _build(src)
        assert "object-fit: contain" in chunk.scoped_css

    def test_auto_size_emits_img_rule_without_object_fit(self, tmp_path: Path) -> None:
        _write(tmp_path / "img.jpg", "fake")
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        assert "object-fit" not in chunk.scoped_css
        assert "] img {" in chunk.scoped_css
        assert "width: 100%" in chunk.scoped_css
        assert "height: 100%" in chunk.scoped_css


class TestScopedCssStacking:
    def test_z_index_follows_array_order(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
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
        chunk = _build(src)
        css = chunk.scoped_css
        bottom_section = css[css.index('data-element-id="0"') :]
        middle_section = css[css.index('data-element-id="1"') :]
        top_section = css[css.index('data-element-id="2"') :]
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
        f"      hold: 200,\n"
        f"      position: [0, 0],\n"
        f"      width: 80,\n"
        f'      height: "auto",\n'
        f"{extra_lines}"
        "    },\n"
        "  ],\n"
        "}\n"
    )


class TestImageSequenceHtml:
    def test_one_img_per_unique_consecutive_path(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))
        chunk = _build(src)
        assert chunk.html.count("<img ") == 3

    def test_consecutive_repeats_collapse_to_one_img(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            _seq_slide(["a.svg", "b.svg", "b.svg", "b.svg", "c.svg"]),
        )
        chunk = _build(src)
        assert chunk.html.count("<img ") == 3

    def test_data_frame_index_uses_run_start(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            _seq_slide(["a.svg", "b.svg", "b.svg", "c.svg"]),
        )
        chunk = _build(src)
        assert 'data-frame-index="0"' in chunk.html
        assert 'data-frame-index="1"' in chunk.html
        assert 'data-frame-index="3"' in chunk.html
        assert 'data-frame-index="2"' not in chunk.html

    def test_each_img_has_data_opacity_keyframes(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))
        chunk = _build(src)
        assert chunk.html.count("data-opacity-keyframes") == 3

    def test_img_src_uses_asset_prefix(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))
        chunk = _build(src)
        for name in ("a.svg", "b.svg", "c.svg"):
            assert f'src="__asset__/{name}"' in chunk.html

    def test_empty_slot_emits_no_img(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "", "b.svg"]))
        chunk = _build(src)
        # Two real frames -> two <img> tags; the empty slot emits nothing.
        assert chunk.html.count("<img ") == 2
        # No data-frame-index="1" since that slot is empty.
        assert 'data-frame-index="0"' in chunk.html
        assert 'data-frame-index="1"' not in chunk.html
        assert 'data-frame-index="2"' in chunk.html

    def test_consecutive_empty_slots_emit_no_img(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "", "", "b.svg"]))
        chunk = _build(src)
        assert chunk.html.count("<img ") == 2


class TestImageSequenceAssets:
    def test_asset_paths_resolved_and_unique(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            _seq_slide(["a.svg", "b.svg", "b.svg", "c.svg"]),
        )
        chunk = _build(src)
        names = [p.name for p in chunk.assets]
        assert sorted(names) == ["a.svg", "b.svg", "c.svg"]

    def test_assets_are_absolute_paths(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg"]))
        chunk = _build(src)
        for path in chunk.assets:
            assert path.is_absolute()

    def test_empty_slots_excluded_from_assets(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "", "b.svg", ""]))
        chunk = _build(src)
        names = sorted(p.name for p in chunk.assets)
        assert names == ["a.svg", "b.svg"]


class TestImageSequenceCss:
    def test_first_img_in_flow_rest_absolute_for_stacking(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg"]))
        chunk = _build(src)
        # Base img rule covers all imgs and does NOT use absolute positioning
        # (the first img must stay in normal flow so it establishes the box height).
        base_idx = chunk.scoped_css.index("img {")
        base_section = chunk.scoped_css[base_idx : base_idx + chunk.scoped_css[base_idx:].index("}")]
        assert "position: absolute" not in base_section
        # The :not(:first-of-type) rule overlays the rest.
        assert "img:not(:first-of-type)" in chunk.scoped_css
        stack_idx = chunk.scoped_css.index("img:not(:first-of-type)")
        stack_section = chunk.scoped_css[stack_idx : stack_idx + chunk.scoped_css[stack_idx:].index("}")]
        assert "position: absolute" in stack_section
        assert "top: 0" in stack_section
        assert "left: 0" in stack_section

    def test_per_run_opacity_rule_emitted(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg", "c.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "b.svg", "c.svg"]))
        chunk = _build(src)
        assert 'img[data-frame-index="0"]' in chunk.scoped_css
        assert 'img[data-frame-index="1"]' in chunk.scoped_css
        assert 'img[data-frame-index="2"]' in chunk.scoped_css
        assert "opacity: calc(" in chunk.scoped_css

    def test_object_fit_emitted_when_set(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            _seq_slide(["a.svg", "b.svg"], height=100, object_fit="cover"),
        )
        chunk = _build(src)
        assert "object-fit: cover" in chunk.scoped_css

    def test_no_opacity_rule_for_empty_slot(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(tmp_path / "s.scrollimation.json", _seq_slide(["a.svg", "", "b.svg"]))
        chunk = _build(src)
        assert 'img[data-frame-index="0"]' in chunk.scoped_css
        assert 'img[data-frame-index="1"]' not in chunk.scoped_css
        assert 'img[data-frame-index="2"]' in chunk.scoped_css


class TestImageSequenceTimeline:
    def test_run_keyframes_basic(self) -> None:
        from pathlib import Path

        from scrolly.slide.ir import ImageSequenceElement
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = ImageSequenceElement(
            image_sequence=[Path("a.svg"), Path("b.svg"), Path("c.svg"), Path("d.svg")],
            frame_distance=400,
            hold=200,
            scroll_offset=0,
            position=[0, 0],
            width=80,
            height="auto",
        )
        runs = _image_sequence_runs(list(el.image_sequence))
        assert len(runs) == 4
        assert _image_sequence_run_keyframes(el, runs, 0) == [(0.0, 1.0), (200.0, 1.0), (400.0, 0.0)]
        assert _image_sequence_run_keyframes(el, runs, 1) == [
            (200.0, 0.0),
            (400.0, 1.0),
            (600.0, 1.0),
            (800.0, 0.0),
        ]
        assert _image_sequence_run_keyframes(el, runs, 3) == [(1000.0, 0.0), (1200.0, 1.0), (1400.0, 1.0)]

    def test_runs_group_consecutive_empty_slots(self) -> None:
        from pathlib import Path

        from scrolly.slide.renderers.scrollimation import _image_sequence_runs

        runs = _image_sequence_runs([Path("a.svg"), None, None, Path("b.svg")])
        # Two consecutive Nones collapse to a single run, just like two identical paths would.
        assert runs == [(Path("a.svg"), 0, 0), (None, 1, 2), (Path("b.svg"), 3, 3)]

    def test_real_frame_keyframes_unchanged_by_empty_slot(self) -> None:
        from pathlib import Path

        from scrolly.slide.ir import ImageSequenceElement
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = ImageSequenceElement(
            image_sequence=[Path("a.svg"), None, Path("b.svg")],
            frame_distance=400,
            hold=200,
            scroll_offset=0,
            position=[0, 0],
            width=80,
            height="auto",
        )
        runs = _image_sequence_runs(list(el.image_sequence))
        # A (first, not last) fades out into the empty slot's hold window.
        assert _image_sequence_run_keyframes(el, runs, 0) == [(0.0, 1.0), (200.0, 1.0), (400.0, 0.0)]
        # B (not first, last) fades in out of the empty slot's hold window.
        assert _image_sequence_run_keyframes(el, runs, 2) == [(600.0, 0.0), (800.0, 1.0), (1000.0, 1.0)]
        # The empty slot's hold [400, 600] sits cleanly between A's fade-out end and B's fade-in start.

    def test_run_keyframes_with_repeats(self) -> None:
        from pathlib import Path

        from scrolly.slide.ir import ImageSequenceElement
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = ImageSequenceElement(
            image_sequence=[Path("a.svg"), Path("b.svg"), Path("b.svg"), Path("c.svg")],
            frame_distance=400,
            hold=200,
            scroll_offset=0,
            position=[0, 0],
            width=80,
            height="auto",
        )
        runs = _image_sequence_runs(list(el.image_sequence))
        # b is run [1, 2]: hold from 400 to 1000 (covers slot 1 and slot 2)
        assert runs[1] == (Path("b.svg"), 1, 2)
        b_kfs = _image_sequence_run_keyframes(el, runs, 1)
        assert b_kfs == [(200.0, 0.0), (400.0, 1.0), (1000.0, 1.0), (1200.0, 0.0)]

    def test_run_keyframes_with_fade_in_out(self) -> None:
        from pathlib import Path

        from scrolly.slide.ir import ImageSequenceElement
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = ImageSequenceElement(
            image_sequence=[Path("a.svg"), Path("b.svg")],
            frame_distance=400,
            hold=200,
            scroll_offset=500,
            fade_in=300,
            fade_out=150,
            position=[0, 0],
            width=80,
            height="auto",
        )
        runs = _image_sequence_runs(list(el.image_sequence))
        # First run: fade in from (500 - 300) = 200, hold 500 to 700, then crossfade to 0 at 900.
        assert _image_sequence_run_keyframes(el, runs, 0) == [
            (200.0, 0.0),
            (500.0, 1.0),
            (700.0, 1.0),
            (900.0, 0.0),
        ]
        # Last run: crossfade in from 700 to 900, hold 900 to 1100, fade out to 0 at 1250.
        assert _image_sequence_run_keyframes(el, runs, 1) == [
            (700.0, 0.0),
            (900.0, 1.0),
            (1100.0, 1.0),
            (1250.0, 0.0),
        ]


class TestImageSequenceCompositingModes:
    """Per-mode coverage of the trailing-edge keyframe shape.

    Leading edges are identical across modes (fade-in only differs by
    ``fade_in``); the trailing edge is what each mode controls.
    """

    @staticmethod
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
            hold=200,
            scroll_offset=0,
            fade_in=fade_in,
            fade_out=fade_out,
            compositing=compositing,
            position=[0, 0],
            width=80,
            height="auto",
        )

    def test_default_compositing_is_blend(self) -> None:
        # --- arrange / act ----------------
        el = self._make_el()

        # --- assert -----------------------
        assert el.compositing == "blend"

    def test_blend_mode_matches_legacy_shape(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="blend")
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act / assert -----------------
        # Symmetric crossfade: 1→0 over the crossfade window into the next run.
        assert _image_sequence_run_keyframes(el, runs, 1) == [
            (200.0, 0.0),
            (400.0, 1.0),
            (600.0, 1.0),
            (800.0, 0.0),
        ]

    def test_overlay_extends_hold_and_drops_to_zero(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _STEP_RAMP_WIDTH,
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="overlay")
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act --------------------------
        kfs = _image_sequence_run_keyframes(el, runs, 1)

        # --- assert -----------------------
        # Run 1's hold extends to 800 (end of run 2's fade-in window),
        # then drops to 0 over a tiny 1-unit ramp — a true step
        # discontinuity isn't expressible in CSS calc(), so we use a
        # near-instantaneous ramp that is visually indistinguishable
        # from a step but keeps slopes well-defined.
        assert kfs == [
            (200.0, 0.0),
            (400.0, 1.0),
            (800.0, 1.0),
            (800.0 + _STEP_RAMP_WIDTH, 0.0),
        ]

    def test_overlay_last_run_behaves_like_blend(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="overlay")
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act / assert -----------------
        # No next-run hold to extend through; trailing edge is just the hold,
        # plus optional fade_out (none here).
        assert _image_sequence_run_keyframes(el, runs, 3) == [
            (1000.0, 0.0),
            (1200.0, 1.0),
            (1400.0, 1.0),
        ]

    def test_incremental_holds_until_sequence_end(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="incremental")
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act / assert -----------------
        # Run 0 holds at 1 from hold_start (0) until the sequence's final
        # hold_end (1400). No fade_out, so no trailing 0 keyframe.
        assert _image_sequence_run_keyframes(el, runs, 0) == [
            (0.0, 1.0),
            (1400.0, 1.0),
        ]
        # Run 1 fades in normally, then also holds until 1400.
        assert _image_sequence_run_keyframes(el, runs, 1) == [
            (200.0, 0.0),
            (400.0, 1.0),
            (1400.0, 1.0),
        ]
        # Last run: identical trailing edge — its own hold_end already
        # equals the sequence's final hold_end.
        assert _image_sequence_run_keyframes(el, runs, 3) == [
            (1000.0, 0.0),
            (1200.0, 1.0),
            (1400.0, 1.0),
        ]

    def test_incremental_fade_out_applies_to_every_run(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="incremental", fade_out=150)
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act / assert -----------------
        # Every run shares the trailing fade — 1400 → 0 at 1550.
        expected_trailer = [(1400.0, 1.0), (1550.0, 0.0)]
        for run_idx in range(len(runs)):
            kfs = _image_sequence_run_keyframes(el, runs, run_idx)
            assert kfs[-2:] == expected_trailer, f"run {run_idx} trailing edge"

    def test_overlay_fade_out_only_on_last_run(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _STEP_RAMP_WIDTH,
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        el = self._make_el(compositing="overlay", fade_out=150)
        runs = _image_sequence_runs(list(el.image_sequence))

        # --- act / assert -----------------
        # Non-last runs still drop out at the next run's fade-in end;
        # only the last run uses the trailing fade_out.
        assert _image_sequence_run_keyframes(el, runs, 1)[-2:] == [
            (800.0, 1.0),
            (800.0 + _STEP_RAMP_WIDTH, 0.0),
        ]
        assert _image_sequence_run_keyframes(el, runs, 3) == [
            (1000.0, 0.0),
            (1200.0, 1.0),
            (1400.0, 1.0),
            (1550.0, 0.0),
        ]

    def test_fade_in_unchanged_across_modes(self) -> None:
        # --- arrange ----------------------
        from scrolly.slide.renderers.scrollimation import (
            _image_sequence_run_keyframes,
            _image_sequence_runs,
        )

        # --- act / assert -----------------
        # Leading-edge fade_in keyframes are identical regardless of mode.
        for mode in ("blend", "overlay", "incremental"):
            el = self._make_el(compositing=mode, fade_in=100)
            runs = _image_sequence_runs(list(el.image_sequence))
            kfs = _image_sequence_run_keyframes(el, runs, 0)
            assert kfs[:2] == [(-100.0, 0.0), (0.0, 1.0)], mode


class TestIframeElement:
    BASE = """\
{{
  title: "T",
  scroll_range: 100,
  elements: [
    {{ {name}iframe_html: "<!doctype html><p>iframe</p>", position: [10, 10], width: 80, height: 80{decor} }},
  ],
}}
"""

    def _slide(self, *, name: str = "", decor: str = "") -> str:
        name_field = f'name: "{name}", ' if name else ""
        return self.BASE.format(name=name_field, decor=decor)

    def test_iframe_tag_with_srcdoc(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        assert "<iframe " in chunk.html
        assert "srcdoc=" in chunk.html

    def test_iframe_srcdoc_html_escaped(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        # The raw `<p>iframe</p>` from the source becomes `&lt;p&gt;iframe&lt;/p&gt;` inside srcdoc.
        assert "&lt;p&gt;iframe&lt;/p&gt;" in chunk.html
        # And the literal `<p>iframe</p>` doesn't appear (it's only inside srcdoc, escaped).
        assert "<p>iframe</p>" not in chunk.html

    def test_iframe_sandbox_allow_scripts(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        assert 'sandbox="allow-scripts"' in chunk.html

    def test_iframe_title_from_name(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide(name="demo"))
        chunk = _build(src)
        assert 'title="demo"' in chunk.html

    def test_iframe_title_omitted_without_name(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        assert "title=" not in chunk.html

    def test_iframe_fill_css_rule(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        # The wrapper-internal iframe rule sets the iframe to fill its wrapper without a default browser border.
        assert "] iframe {" in chunk.scoped_css
        idx = chunk.scoped_css.index("] iframe {")
        section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]
        assert "width: 100%" in section
        assert "height: 100%" in section
        assert "border: 0" in section
        assert "display: block" in section


class TestIframeDecorations:
    def _slide(self, **decor) -> str:
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

    def test_no_decoration_by_default(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide())
        chunk = _build(src)
        # Wrapper rule has no border, no box-shadow, no box-sizing. The iframe
        # child rule's `border: 0` is in a separate rule and not checked here.
        idx = chunk.scoped_css.index('data-element-id="0"')
        wrapper_section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]
        assert "border:" not in wrapper_section
        assert "box-shadow" not in wrapper_section
        assert "box-sizing" not in wrapper_section

    def test_border_only(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide(border_width=4, border_color="#333"))
        chunk = _build(src)
        assert "border: 4px solid #333" in chunk.scoped_css
        assert "box-sizing: border-box" in chunk.scoped_css
        assert "box-shadow" not in chunk.scoped_css

    def test_shadow_only(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.scrollimation.json", self._slide(shadow_size=12, shadow_color="rgba(0,0,0,0.3)"))
        chunk = _build(src)
        assert "box-shadow: 0 0 12px rgba(0,0,0,0.3)" in chunk.scoped_css
        assert "box-sizing: border-box" in chunk.scoped_css
        # The "border: 0" line on the inner iframe is still emitted; the wrapper has no border.
        idx = chunk.scoped_css.index('data-element-id="0"')
        wrapper_section = chunk.scoped_css[idx : idx + chunk.scoped_css[idx:].index("}")]
        assert "border:" not in wrapper_section

    def test_border_and_shadow_together(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            self._slide(border_width=2, border_color="#000", shadow_size=8, shadow_color="#888"),
        )
        chunk = _build(src)
        assert "border: 2px solid #000" in chunk.scoped_css
        assert "box-shadow: 0 0 8px #888" in chunk.scoped_css
        assert "box-sizing: border-box" in chunk.scoped_css

    def test_zero_decoration_values_emit_nothing(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            self._slide(border_width=0, shadow_size=0),
        )
        chunk = _build(src)
        # Explicit 0 should behave identically to the default — no box-sizing override.
        assert "box-sizing" not in chunk.scoped_css


class TestIframeBundler:
    HTML_PAYLOAD = "<!doctype html><p>iframe body</p>"

    def _slide(self, html_content: str) -> str:
        import json

        escaped = json.dumps(html_content)
        return (
            '{\n  title: "T",\n  scroll_range: 100,\n  elements: [\n'
            f"    {{ iframe_html: {escaped}, position: [10, 10], width: 80, height: 80 }},\n"
            "  ],\n}\n"
        )

    def test_with_bundler_emits_data_scrolly_target_no_srcdoc(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        from scrolly.pipeline._bundler import PayloadBundler

        src = _write(tmp_path / "s.scrollimation.json", self._slide(self.HTML_PAYLOAD))
        ir = ScrollimationIR.from_file(src)
        bundler = PayloadBundler()

        # --- act --------------------------------
        chunk = _renderer().render(ir, bundler=bundler)

        # --- assert ------------------------------
        assert 'data-scrolly-target="0"' in chunk.html
        assert "srcdoc=" not in chunk.html
        assert 'sandbox="allow-scripts"' in chunk.html

    def test_with_bundler_registers_text_payload_for_srcdoc(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        from scrolly.pipeline._bundler import PayloadBundler

        src = _write(tmp_path / "s.scrollimation.json", self._slide(self.HTML_PAYLOAD))
        ir = ScrollimationIR.from_file(src)
        bundler = PayloadBundler()

        # --- act --------------------------------
        _renderer().render(ir, bundler=bundler)

        # --- assert ------------------------------
        # The payload is recoverable via inline_fallback() — escaped srcdoc form.
        from html import escape as html_escape

        fallback = bundler.inline_fallback()
        assert fallback == {"0": f'srcdoc="{html_escape(self.HTML_PAYLOAD)}"'}

    def test_without_bundler_emits_uncompressed_srcdoc(self, tmp_path: Path) -> None:
        # --- arrange ----------------------------
        src = _write(tmp_path / "s.scrollimation.json", self._slide(self.HTML_PAYLOAD))
        ir = ScrollimationIR.from_file(src)

        # --- act --------------------------------
        chunk = _renderer().render(ir)

        # --- assert ------------------------------
        assert "srcdoc=" in chunk.html
        assert "data-scrolly-target" not in chunk.html
        assert 'sandbox="allow-scripts"' in chunk.html


class TestImageSequenceInteractions:
    def test_element_level_animated_opacity_on_outer_div(self, tmp_path: Path) -> None:
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / name, "<svg/>")
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 2000,
  elements: [
    {
      name: "seq",
      image_sequence: ["a.svg", "b.svg"],
      frame_distance: 400,
      hold: 200,
      position: [0, 0],
      width: 80,
      height: "auto",
      opacity: { keyframes: [[0, 0.0], [500, 1.0]] },
    },
  ],
}
""",
        )
        chunk = _build(src)
        # The outer div gets data-opacity-keyframes from element-level opacity (inherited mechanism).
        # Plus per-img data-opacity-keyframes from frame ramps.
        assert chunk.html.count("data-opacity-keyframes") == 1 + 2
