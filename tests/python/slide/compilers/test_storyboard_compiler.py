"""Tests for the storyboard -> scrollimation compiler."""

from __future__ import annotations

from pathlib import Path

from scrolly.slide.compilers.storyboard import StoryboardCompiler, compile_storyboard
from scrolly.slide.ir import (
    HtmlElement,
    IframeElement,
    ImageElement,
    MarkdownElement,
)
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR, StoryboardScene
from scrolly.slide.processor import Compiler as CompilerBase

# ── helpers ───────────────────────────────────────────────────────


def _html_element(**overrides) -> HtmlElement:
    base = {"html": "<p>hi</p>", "position": (10, 30), "width": 80, "height": "auto"}
    return HtmlElement(**{**base, **overrides})


def _md_element(**overrides) -> MarkdownElement:
    base = {"markdown": "# Hi", "position": (10, 30), "width": 80, "height": "auto"}
    return MarkdownElement(**{**base, **overrides})


def _image_element(**overrides) -> ImageElement:
    base = {"image": Path("/abs/img.jpg"), "position": (0, 0), "width": 100, "height": 100, "object_fit": "cover"}
    return ImageElement(**{**base, **overrides})


def _iframe_element(**overrides) -> IframeElement:
    base = {
        "iframe_html": "<!doctype html><p>x</p>",
        "position": (10, 10),
        "width": 80,
        "height": 80,
    }
    return IframeElement(**{**base, **overrides})


def _storyboard(**overrides) -> StoryboardIR:
    base = {
        "title": "Test",
        "scene_distance": 100,
        "scenes": [
            StoryboardScene(elements=[_html_element()]),
            StoryboardScene(elements=[_md_element()]),
        ],
    }
    return StoryboardIR(**{**base, **overrides})


# ── Basic output shape ────────────────────────────────────────────


class TestOutputShape:
    def test_returns_scrollimation_ir(self):
        result = compile_storyboard(_storyboard())
        assert isinstance(result, ScrollimationIR)

    def test_title_passes_through(self):
        result = compile_storyboard(_storyboard(title="My Title"))
        assert result.title == "My Title"

    def test_scroll_range_computed(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        assert result.scroll_range == 100  # 2 scenes -> 1 gap

    def test_scroll_range_three_scenes(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.scroll_range == 200

    def test_scroll_range_single_scene(self):
        ir = _storyboard(scenes=[StoryboardScene(elements=[_html_element()])])
        result = compile_storyboard(ir)
        assert result.scroll_range == 0


# ── Snap positions ────────────────────────────────────────────────


class TestSnapPositions:
    def test_two_scenes(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        assert result.snap_positions == (0, 100)

    def test_three_scenes(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ],
            scene_distance=200,
        )
        result = compile_storyboard(ir)
        assert result.snap_positions == (0, 200, 400)

    def test_single_scene(self):
        ir = _storyboard(scenes=[StoryboardScene(elements=[_html_element()])])
        result = compile_storyboard(ir)
        assert result.snap_positions == (0,)


# ── Element ordering ─────────────────────────────────────────────


class TestElementOrdering:
    def test_scene_elements_ordered_by_scene_index(self):
        result = compile_storyboard(_storyboard())
        assert len(result.elements) == 2
        assert isinstance(result.elements[0], HtmlElement)
        assert isinstance(result.elements[1], MarkdownElement)

    def test_background_elements_first(self):
        ir = _storyboard(background=[_image_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], ImageElement)
        assert isinstance(result.elements[1], HtmlElement)

    def test_multiple_items_per_scene(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(), _md_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert len(result.elements) == 3
        assert isinstance(result.elements[0], HtmlElement)
        assert isinstance(result.elements[1], MarkdownElement)
        assert isinstance(result.elements[2], HtmlElement)

    def test_multiple_background_items(self):
        ir = _storyboard(background=[_image_element(), _html_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], ImageElement)
        assert isinstance(result.elements[1], HtmlElement)


# ── Element types ────────────────────────────────────────────────


class TestElementTypes:
    def test_html_item_becomes_html_element(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], HtmlElement)

    def test_markdown_item_becomes_markdown_element(self):
        result = compile_storyboard(_storyboard())
        assert isinstance(result.elements[1], MarkdownElement)

    def test_asset_item_becomes_image_element(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_image_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], ImageElement)
        assert result.elements[0].image == Path("/abs/img.jpg")
        assert result.elements[0].object_fit == "cover"

    def test_iframe_item_becomes_iframe_element(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_iframe_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], IframeElement)
        assert result.elements[0].iframe_html == "<!doctype html><p>x</p>"

    def test_iframe_decorations_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(
                    elements=[
                        _iframe_element(
                            border_width=3,
                            border_color="#abc",
                            shadow_size=9,
                            shadow_color="#def",
                        ),
                    ],
                ),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].border_width == 3
        assert result.elements[0].border_color == "#abc"
        assert result.elements[0].shadow_size == 9
        assert result.elements[0].shadow_color == "#def"

    def test_markdown_color_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_md_element(color="#fff")]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].color == "#fff"

    def test_position_and_size_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(position=(25, 50), width=60, height=40)]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].position.static_value == (25, 50)
        assert result.elements[0].width.static_value == 60
        assert result.elements[0].height.static_value == 40

    def test_anchor_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(anchor=(50, 50))]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].anchor.static_value == (50, 50)


# ── Opacity keyframes — no hold ──────────────────────────────────


class TestOpacityNoHold:
    def test_scene_0_fades_out(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        el = result.elements[0]  # s0-0
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(0, 1.0), (100, 0.0)]

    def test_last_scene_no_fade_out(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        el = result.elements[1]  # s1-0 (last scene)
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(0, 0.0), (100, 1.0)]

    def test_middle_scene_fades_in_and_out(self):
        ir = _storyboard(
            scene_distance=100,
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ],
        )
        result = compile_storyboard(ir)
        el = result.elements[1]  # s1-0 (middle scene)
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(0, 0.0), (100, 1.0), (200, 0.0)]

    def test_last_scene_fade_in_only(self):
        ir = _storyboard(
            scene_distance=100,
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ],
        )
        result = compile_storyboard(ir)
        el = result.elements[2]  # s2-0 (last)
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(100, 0.0), (200, 1.0)]

    def test_single_scene_no_keyframes(self):
        ir = _storyboard(scenes=[StoryboardScene(elements=[_html_element()])])
        result = compile_storyboard(ir)
        el = result.elements[0]
        assert not el.opacity.is_animated
        assert el.opacity.static_value == 1.0


# ── Opacity keyframes — with hold ────────────────────────────────


class TestOpacityWithHold:
    def test_scene_0_fades_out_with_hold(self):
        result = compile_storyboard(_storyboard(scene_distance=100, hold=15))
        el = result.elements[0]
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(15, 1.0), (85, 0.0)]

    def test_last_scene_fade_in_with_hold(self):
        result = compile_storyboard(_storyboard(scene_distance=100, hold=15))
        el = result.elements[1]  # s1-0 (last)
        assert el.opacity.is_animated
        assert el.opacity.keyframes == [(15, 0.0), (85, 1.0)]

    def test_middle_scene_with_hold(self):
        ir = _storyboard(
            scene_distance=100,
            hold=15,
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element()]),
            ],
        )
        result = compile_storyboard(ir)
        el = result.elements[1]  # s1-0 (middle)
        assert el.opacity.is_animated
        # fade in 15->85, hold 85->115, fade out 115->185
        assert el.opacity.keyframes == [(15, 0.0), (85, 1.0), (115, 1.0), (185, 0.0)]


# ── Background elements ─────────────────────────────────────────


class TestBackgroundElements:
    def test_background_at_opacity_1_no_keyframes(self):
        ir = _storyboard(background=[_image_element()])
        result = compile_storyboard(ir)
        bg = result.elements[0]
        assert isinstance(bg, ImageElement)
        assert not bg.opacity.is_animated
        assert bg.opacity.static_value == 1.0

    def test_multiple_background_items(self):
        ir = _storyboard(background=[_image_element(), _html_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0], ImageElement)
        assert isinstance(result.elements[1], HtmlElement)
        assert all(not el.opacity.is_animated for el in result.elements[:2])
        assert all(el.opacity.static_value == 1.0 for el in result.elements[:2])


# ── All items in a scene share keyframes ──────────────────────────


class TestMultiItemScene:
    def test_all_items_in_scene_share_opacity_keyframes(self):
        ir = _storyboard(
            scene_distance=100,
            scenes=[
                StoryboardScene(elements=[_html_element()]),
                StoryboardScene(elements=[_html_element(), _md_element(), _image_element()]),
            ],
        )
        result = compile_storyboard(ir)
        # s1-0, s1-1, s1-2 should all have the same keyframes (last scene — fade in only)
        for el in result.elements[1:]:
            assert el.opacity.is_animated
            assert el.opacity.keyframes == [(0, 0.0), (100, 1.0)]


# ── StoryboardCompiler class ────────────────────────────────────────


class TestStoryboardCompiler:
    def test_is_compiler(self):
        assert issubclass(StoryboardCompiler, CompilerBase)

    def test_can_process_storyboard_ir(self):
        ir = _storyboard()
        assert StoryboardCompiler.can_process(ir) is True

    def test_cannot_process_other_ir(self):
        other = ScrollimationIR(
            title="T",
            scroll_range=100,
            elements=[{"html": "<p>hi</p>", "position": [0, 0], "width": 100, "height": 100}],
        )
        assert StoryboardCompiler.can_process(other) is False

    def test_compile_returns_scrollimation_ir(self):
        compiler = StoryboardCompiler()
        result = compiler.compile(_storyboard())
        assert isinstance(result, ScrollimationIR)
