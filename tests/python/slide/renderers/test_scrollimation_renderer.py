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
    { element: { html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
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
            elements=[{"element": {"html": "<p>hi</p>", "position": [0, 0], "size": [100, 100]}}],
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
    { element: { name: "L", markdown: "# Hello\\n\\nWorld", position: [0, 0], size: [80, "auto"] } },
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
    { element: { name: "bg", image: "hero.jpg", position: [0, 0], size: [100, 120], object_fit: "cover" } },
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
    { element: { name: "bg", image: "img.svg", position: [0, 0], size: [100, 100], object_fit: "cover" } },
    { element: { name: "sep", html: "<div>box</div>", position: [0, 0], size: [100, 100] } },
    { element: { name: "txt", markdown: "# Cap", position: [10, 40], size: [80, "auto"] } },
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
    { element: { name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], size: [80, "auto"] } },
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
    { element: { name: "dia", mermaid: "graph LR\\n  A -->|<yes>| B", position: [10, 10], size: [80, "auto"] } },
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
    { element: { name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], size: [80, "auto"] } },
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
    { element: { name: "dia", mermaid: "graph LR\\n  A --> B", position: [10, 10], size: [80, "auto"] } },
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
    { element: { name: "first", html: "<p>1</p>", position: [0, 0], size: [100, 100] } },
    { element: { name: "second", html: "<p>2</p>", position: [0, 0], size: [100, 100] } },
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
    { element: { name: "bg", image: "hero.jpg", position: [0, 0], size: [100, 120], object_fit: "cover" } },
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
    { element: { name: "bg", image: "a.jpg", position: [0, 0], size: [100, 100], object_fit: "cover" } },
    { element: { name: "mid", html: "<div></div>", position: [0, 0], size: [100, 100] } },
    { element: { name: "fg", image: "b.svg", position: [0, 0], size: [100, 100], object_fit: "contain" } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] } },
  ],
}
""",
        )
        chunk = _build(src)
        assert chunk.snap_positions == (0, 500, 1000)


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
    def test_left_top_from_position_plus_initial_translate(self, tmp_path: Path) -> None:
        src = _write(
            tmp_path / "s.scrollimation.json",
            """\
{
  title: "T",
  scroll_range: 100,
  elements: [
    {
      element: { name: "L", html: "<p>hi</p>", position: [10, 20], size: [80, 60] },
      initial: { translate: [5, -10] },
    },
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
    { element: { name: "L", html: "<p>hi</p>", position: [25, 50], size: [50, 50] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [80, 60] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [80, "auto"] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: ["auto", 50] } },
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
    { element: { name: "L", markdown: "# Hi", position: [0, 0], size: [80, "auto"], text_align: "center" } },
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
    { element: { name: "L", markdown: "# Hi", position: [0, 0], size: [80, "auto"] } },
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
    { element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100], anchor: [50, 50] } },
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
    {
      element: { name: "L", html: "<p>hi</p>", position: [50, 50], size: [100, 100] },
      initial: { anchor: [50, 0] },
      keyframes: [{ at: 1000, anchor: [50, 100] }],
    },
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
    {
      element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] },
      initial: { scale: 2, rotate: 45 },
    },
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
    {
      element: { name: "L", html: "<p>hi</p>", position: [0, 0], size: [100, 100] },
      initial: { opacity: 0.5 },
    },
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
    { element: { name: "bg", image: "img.jpg", position: [0, 0], size: [100, 120], object_fit: "cover" } },
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
    { element: { name: "bg", image: "img.jpg", position: [0, 0], size: [100, 120], object_fit: "contain" } },
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
    { element: { name: "bg", image: "img.jpg", position: [0, 0], size: [100, "auto"] } },
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
    { element: { name: "bottom", html: "<p>1</p>", position: [0, 0], size: [100, 100] } },
    { element: { name: "middle", html: "<p>2</p>", position: [0, 0], size: [100, 100] } },
    { element: { name: "top", html: "<p>3</p>", position: [0, 0], size: [100, 100] } },
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
