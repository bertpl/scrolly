"""Tests for StoryboardIR models — structural validation via pydantic."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from scrolly.slide.ir import HtmlElement, ImageElement, MarkdownElement, MermaidElement, SlideIR
from scrolly.slide.ir.storyboard import StoryboardIR, StoryboardScene

# ── helpers ───────────────────────────────────────────────────────


def _html_element(**overrides) -> dict:
    base = {"html": "<p>hi</p>", "position": [10, 30], "size": [80, "auto"]}
    return {**base, **overrides}


def _image_element(**overrides) -> dict:
    base = {"image": "img.jpg", "position": [0, 0], "size": [100, 100], "object_fit": "cover"}
    return {**base, **overrides}


def _md_element(**overrides) -> dict:
    base = {"markdown": "# Hi", "position": [10, 30], "size": [80, "auto"]}
    return {**base, **overrides}


def _mermaid_element(**overrides) -> dict:
    base = {"mermaid": "graph LR\n  A --> B", "position": [10, 10], "size": [80, "auto"]}
    return {**base, **overrides}


def _scene(**overrides) -> dict:
    base = {"elements": [_html_element()]}
    return {**base, **overrides}


def _storyboard(**overrides) -> dict:
    base = {
        "title": "Test",
        "scene_distance": 100,
        "scenes": [_scene(), _scene(elements=[_md_element()])],
    }
    return {**base, **overrides}


# ── Element types ─────────────────────────────────────────────────


class TestHtmlElement:
    def test_valid(self):
        item = HtmlElement(**_html_element())
        assert item.html == "<p>hi</p>"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            HtmlElement(**_html_element(asset="sneaky.jpg"))


class TestImageElement:
    def test_valid(self):
        item = ImageElement(**_image_element())
        assert item.object_fit == "cover"

    def test_object_fit_required_when_both_numeric(self):
        with pytest.raises(ValidationError, match="object_fit is required"):
            ImageElement(**_image_element(object_fit=None))

    def test_object_fit_forbidden_with_auto(self):
        with pytest.raises(ValidationError, match="object_fit is forbidden"):
            ImageElement(**_image_element(size=[100, "auto"], object_fit="cover"))

    def test_auto_size_without_object_fit(self):
        item = ImageElement(**_image_element(size=[100, "auto"], object_fit=None))
        assert item.object_fit is None


class TestMarkdownElement:
    def test_valid(self):
        item = MarkdownElement(**_md_element())
        assert item.markdown == "# Hi"

    def test_default_color(self):
        item = MarkdownElement(**_md_element())
        assert item.color == "#808080"

    def test_custom_color(self):
        item = MarkdownElement(**_md_element(color="#fff"))
        assert item.color == "#fff"


class TestMermaidElement:
    def test_valid(self):
        item = MermaidElement(**_mermaid_element())
        assert item.mermaid == "graph LR\n  A --> B"

    def test_in_scene(self):
        scene = StoryboardScene(elements=[_mermaid_element()])
        assert isinstance(scene.elements[0], MermaidElement)

    def test_in_background(self):
        sb = StoryboardIR(**_storyboard(background=[_mermaid_element()]))
        assert isinstance(sb.background[0], MermaidElement)

    def test_mixed_scene(self):
        scene = StoryboardScene(elements=[_html_element(), _mermaid_element()])
        assert isinstance(scene.elements[0], HtmlElement)
        assert isinstance(scene.elements[1], MermaidElement)


# ── Size validation ───────────────────────────────────────────────


class TestElementSizeValidation:
    def test_auto_auto_rejected(self):
        with pytest.raises(ValidationError, match="at least one size dimension"):
            HtmlElement(**_html_element(size=["auto", "auto"]))

    def test_zero_width_rejected(self):
        with pytest.raises(ValidationError, match="width must be > 0"):
            HtmlElement(**_html_element(size=[0, 100]))

    def test_negative_height_rejected(self):
        with pytest.raises(ValidationError, match="height must be > 0"):
            HtmlElement(**_html_element(size=[100, -5]))


# ── StoryboardScene ──────────────────────────────────────────────


class TestStoryboardScene:
    def test_valid(self):
        scene = StoryboardScene(**_scene())
        assert len(scene.elements) == 1

    def test_empty_elements_rejected(self):
        with pytest.raises(ValidationError, match="at least one element"):
            StoryboardScene(elements=[])

    def test_multiple_elements(self):
        scene = StoryboardScene(elements=[_html_element(), _md_element(), _image_element()])
        assert len(scene.elements) == 3
        assert isinstance(scene.elements[0], HtmlElement)
        assert isinstance(scene.elements[1], MarkdownElement)
        assert isinstance(scene.elements[2], ImageElement)

    def test_element_with_id_rejected(self):
        with pytest.raises(ValidationError, match="must not set 'id'"):
            StoryboardScene(elements=[_html_element(id="sneaky")])

    def test_element_with_explicit_none_id_accepted(self):
        scene = StoryboardScene(elements=[_html_element(id=None)])
        assert scene.elements[0].id is None


# ── StoryboardIR ─────────────────────────────────────────────────


class TestStoryboardIR:
    def test_is_slide_ir(self):
        assert issubclass(StoryboardIR, SlideIR)

    def test_is_pydantic_model(self):
        assert issubclass(StoryboardIR, BaseModel)

    def test_valid_construction(self):
        ir = StoryboardIR(**_storyboard())
        assert ir.title == "Test"
        assert ir.scene_distance == 100
        assert ir.hold == 0
        assert ir.background == []
        assert len(ir.scenes) == 2

    def test_defaults(self):
        ir = StoryboardIR(**_storyboard())
        assert ir.hold == 0
        assert ir.background == []

    def test_with_hold(self):
        ir = StoryboardIR(**_storyboard(hold=20))
        assert ir.hold == 20

    def test_with_background(self):
        ir = StoryboardIR(**_storyboard(background=[_image_element()]))
        assert len(ir.background) == 1
        assert isinstance(ir.background[0], ImageElement)

    def test_background_element_with_id_rejected(self):
        with pytest.raises(ValidationError, match="must not set 'id'"):
            StoryboardIR(**_storyboard(background=[_image_element(id="bad")]))

    def test_scene_distance_zero_rejected(self):
        with pytest.raises(ValidationError, match="scene_distance must be > 0"):
            StoryboardIR(**_storyboard(scene_distance=0))

    def test_scene_distance_negative_rejected(self):
        with pytest.raises(ValidationError, match="scene_distance must be > 0"):
            StoryboardIR(**_storyboard(scene_distance=-10))

    def test_hold_negative_rejected(self):
        with pytest.raises(ValidationError, match="hold must be >= 0"):
            StoryboardIR(**_storyboard(hold=-1))

    def test_hold_too_large_rejected(self):
        with pytest.raises(ValidationError, match="2 \\* hold"):
            StoryboardIR(**_storyboard(scene_distance=100, hold=50))

    def test_hold_exactly_half_rejected(self):
        with pytest.raises(ValidationError, match="2 \\* hold"):
            StoryboardIR(**_storyboard(scene_distance=100, hold=50))

    def test_hold_just_under_half_accepted(self):
        ir = StoryboardIR(**_storyboard(scene_distance=100, hold=49))
        assert ir.hold == 49

    def test_empty_scenes_rejected(self):
        with pytest.raises(ValidationError, match="at least one scene"):
            StoryboardIR(**_storyboard(scenes=[]))

    def test_single_scene_accepted(self):
        ir = StoryboardIR(**_storyboard(scenes=[_scene()]))
        assert len(ir.scenes) == 1

    def test_frozen(self):
        ir = StoryboardIR(**_storyboard())
        with pytest.raises(ValidationError):
            ir.title = "changed"


# ── from_file ─────────────────────────────────────────────────────


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


MINIMAL_STORYBOARD = """\
{
  title: "Test",
  scene_distance: 100,
  scenes: [
    { elements: [{ html: "<p>Scene 1</p>", position: [10, 30], size: [80, "auto"] }] },
    { elements: [{ html: "<p>Scene 2</p>", position: [10, 30], size: [80, "auto"] }] },
  ],
}
"""


class TestFromFile:
    def test_returns_storyboard_ir(self, tmp_path):
        src = _write(tmp_path, "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        assert isinstance(ir, StoryboardIR)
        assert ir.title == "Test"
        assert ir.scene_distance == 100

    def test_background_asset_paths_resolved(self, tmp_path):
        _write(tmp_path, "bg.svg", "<svg/>")
        src = _write(
            tmp_path,
            "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  background: [
    { image: "bg.svg", position: [0, 0], size: [100, 100], object_fit: "cover" },
  ],
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [0, 0], size: [100, "auto"] }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], size: [100, "auto"] }] },
  ],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert ir.background[0].image.is_absolute()

    def test_scene_asset_paths_resolved(self, tmp_path):
        _write(tmp_path, "img.jpg", "fake")
        src = _write(
            tmp_path,
            "s.storyboard.json",
            """\
{
  title: "T",
  scene_distance: 100,
  scenes: [
    { elements: [{ image: "img.jpg", position: [0, 0], size: [100, 100], object_fit: "cover" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], size: [100, "auto"] }] },
  ],
}
""",
        )
        ir = StoryboardIR.from_file(src)
        assert ir.scenes[0].elements[0].image.is_absolute()

    def test_slide_type_property(self, tmp_path):
        src = _write(tmp_path, "s.storyboard.json", MINIMAL_STORYBOARD)
        ir = StoryboardIR.from_file(src)
        assert ir.slide_type == "storyboard-json"

    def test_missing_file_raises(self):
        from scrolly.errors import SlideSourceError

        with pytest.raises(SlideSourceError, match="not found"):
            StoryboardIR.from_file(Path("/no/such/file.storyboard.json"))
