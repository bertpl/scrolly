"""Tests for the storyboard → scrollimation compiler."""

from __future__ import annotations

from pathlib import Path

from scrolly.slide.compilers.storyboard import StoryboardCompiler, compile_storyboard
from scrolly.slide.ir import (
    ElementAnimation,
    HtmlElement,
    ImageElement,
    MarkdownElement,
)
from scrolly.slide.ir.scrollimation import ScrollimationIR
from scrolly.slide.ir.storyboard import StoryboardIR, StoryboardScene
from scrolly.slide.processor import Compiler as CompilerBase

# ── helpers ───────────────────────────────────────────────────────


def _html_element(**overrides) -> HtmlElement:
    base = {"html": "<p>hi</p>", "position": (10, 30), "size": (80, "auto")}
    return HtmlElement(**{**base, **overrides})


def _md_element(**overrides) -> MarkdownElement:
    base = {"markdown": "# Hi", "position": (10, 30), "size": (80, "auto")}
    return MarkdownElement(**{**base, **overrides})


def _image_element(**overrides) -> ImageElement:
    base = {"image": Path("/abs/img.jpg"), "position": (0, 0), "size": (100, 100), "object_fit": "cover"}
    return ImageElement(**{**base, **overrides})


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
        assert result.scroll_range == 100  # 2 scenes → 1 gap

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
        assert isinstance(result.elements[0].element, HtmlElement)
        assert isinstance(result.elements[1].element, MarkdownElement)

    def test_background_elements_first(self):
        ir = _storyboard(background=[_image_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0].element, ImageElement)
        assert isinstance(result.elements[1].element, HtmlElement)

    def test_multiple_items_per_scene(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(), _md_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert len(result.elements) == 3
        assert isinstance(result.elements[0].element, HtmlElement)
        assert isinstance(result.elements[1].element, MarkdownElement)
        assert isinstance(result.elements[2].element, HtmlElement)

    def test_multiple_background_items(self):
        ir = _storyboard(background=[_image_element(), _html_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0].element, ImageElement)
        assert isinstance(result.elements[1].element, HtmlElement)


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
        assert isinstance(result.elements[0].element, HtmlElement)

    def test_markdown_item_becomes_markdown_element(self):
        result = compile_storyboard(_storyboard())
        assert isinstance(result.elements[1].element, MarkdownElement)

    def test_asset_item_becomes_image_element(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_image_element()]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0].element, ImageElement)
        assert result.elements[0].element.image == Path("/abs/img.jpg")
        assert result.elements[0].element.object_fit == "cover"

    def test_markdown_color_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_md_element(color="#fff")]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].element.color == "#fff"

    def test_position_and_size_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(position=(25, 50), size=(60, 40))]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].element.position == (25, 50)
        assert result.elements[0].element.size == (60, 40)

    def test_anchor_preserved(self):
        ir = _storyboard(
            scenes=[
                StoryboardScene(elements=[_html_element(anchor=(50, 50))]),
                StoryboardScene(elements=[_html_element()]),
            ]
        )
        result = compile_storyboard(ir)
        assert result.elements[0].element.anchor == (50, 50)


# ── Opacity keyframes — no hold ──────────────────────────────────


class TestOpacityNoHold:
    def test_scene_0_fades_out(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        anim = result.elements[0]  # s0-0
        assert anim.initial.opacity == 1.0
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # hold at 1, fade out from 0 to 100
        assert kfs == [(0, 1.0), (100, 0.0)]

    def test_last_scene_no_fade_out(self):
        result = compile_storyboard(_storyboard(scene_distance=100))
        anim = result.elements[1]  # s1-0 (last scene)
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # fade in only, no fade out
        assert kfs == [(0, 0.0), (100, 1.0)]

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
        anim = result.elements[1]  # s1-0 (middle scene)
        assert anim.initial.opacity == 0.0
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # fade in 0→100, then fade out 100→200
        assert kfs == [(0, 0.0), (100, 1.0), (200, 0.0)]

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
        anim = result.elements[2]  # s2-0 (last)
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        assert kfs == [(100, 0.0), (200, 1.0)]

    def test_single_scene_no_keyframes(self):
        ir = _storyboard(scenes=[StoryboardScene(elements=[_html_element()])])
        result = compile_storyboard(ir)
        anim = result.elements[0]
        assert anim.initial.opacity == 1.0
        assert anim.keyframes == []


# ── Opacity keyframes — with hold ────────────────────────────────


class TestOpacityWithHold:
    def test_scene_0_fades_out_with_hold(self):
        result = compile_storyboard(_storyboard(scene_distance=100, hold=15))
        anim = result.elements[0]
        assert anim.initial.opacity == 1.0
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # hold at 1 until 15, fade out to 85
        assert kfs == [(15, 1.0), (85, 0.0)]

    def test_last_scene_fade_in_with_hold(self):
        result = compile_storyboard(_storyboard(scene_distance=100, hold=15))
        anim = result.elements[1]  # s1-0 (last)
        assert anim.initial.opacity == 0.0
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # fade in from 15 to 85
        assert kfs == [(15, 0.0), (85, 1.0)]

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
        anim = result.elements[1]  # s1-0 (middle)
        kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
        # fade in 15→85, hold 85→115, fade out 115→185
        assert kfs == [(15, 0.0), (85, 1.0), (115, 1.0), (185, 0.0)]


# ── Background elements ─────────────────────────────────────────


class TestBackgroundElements:
    def test_background_at_opacity_1_no_keyframes(self):
        ir = _storyboard(background=[_image_element()])
        result = compile_storyboard(ir)
        bg = result.elements[0]
        assert isinstance(bg.element, ImageElement)
        assert bg.initial.opacity == 1.0
        assert bg.keyframes == []

    def test_multiple_background_items(self):
        ir = _storyboard(background=[_image_element(), _html_element()])
        result = compile_storyboard(ir)
        assert isinstance(result.elements[0].element, ImageElement)
        assert isinstance(result.elements[1].element, HtmlElement)
        assert all(a.initial.opacity == 1.0 for a in result.elements[:2])
        assert all(a.keyframes == [] for a in result.elements[:2])


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
        for anim in result.elements[1:]:
            assert anim.initial.opacity == 0.0
            kfs = [(kf.at, kf.opacity) for kf in anim.keyframes]
            assert kfs == [(0, 0.0), (100, 1.0)]


# ── StoryboardCompiler class ────────────────────────────────────────


class TestStoryboardCompiler:
    def test_is_compiler(self):
        assert issubclass(StoryboardCompiler, CompilerBase)

    def test_can_process_storyboard_ir(self):
        ir = _storyboard()
        assert StoryboardCompiler.can_process(ir) is True

    def test_cannot_process_other_ir(self):
        from scrolly.slide.ir.scrollimation import ScrollimationIR

        other = ScrollimationIR(
            title="T",
            scroll_range=100,
            elements=[{"element": {"html": "<p>hi</p>", "position": [0, 0], "size": [100, 100]}}],
        )
        assert StoryboardCompiler.can_process(other) is False

    def test_compile_returns_scrollimation_ir(self):
        compiler = StoryboardCompiler()
        result = compiler.compile(_storyboard())
        assert isinstance(result, ScrollimationIR)
