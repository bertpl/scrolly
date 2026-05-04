"""StoryboardIR model and scene types.

A storyboard is a sequence of scenes cross-faded by scrolling.  The IR
captures the authored structure; the compiler generates
``ScrollimationIR`` with the appropriate opacity keyframes.  Storyboard
uses the shared ``SlideElement`` types directly (no animation wrapper).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scrolly.slide.ir import (
    HtmlElement,
    ImageElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
    parse_json5_ir,
    resolve_asset_paths,
)


class StoryboardScene(BaseModel, frozen=True):
    """One scene in a storyboard — a group of elements shown together."""

    model_config = ConfigDict(extra="forbid")

    elements: list[ImageElement | HtmlElement | MarkdownElement | MermaidElement]

    @model_validator(mode="after")
    def _validate(self) -> StoryboardScene:
        if not self.elements:
            raise ValueError("a scene must have at least one element")
        for el in self.elements:
            if el.id is not None:
                raise ValueError("storyboard elements must not set 'id' — the compiler generates IDs")
        return self


class StoryboardIR(SlideIR, frozen=True):
    """Top-level IR for a .storyboard.json source file."""

    SUFFIX: ClassVar[str] = ".storyboard.json"
    DESCRIPTION: ClassVar[str] = "Scene-based cross-fade"

    title: str
    scene_distance: int
    hold: int = 0
    background: list[ImageElement | HtmlElement | MarkdownElement | MermaidElement] = Field(default_factory=list)
    scenes: list[StoryboardScene]

    @model_validator(mode="after")
    def _validate(self) -> StoryboardIR:
        if self.scene_distance <= 0:
            raise ValueError(f"scene_distance must be > 0, got {self.scene_distance}")
        if self.hold < 0:
            raise ValueError(f"hold must be >= 0, got {self.hold}")
        if 2 * self.hold >= self.scene_distance:
            raise ValueError(f"2 * hold ({2 * self.hold}) must be < scene_distance ({self.scene_distance})")
        if not self.scenes:
            raise ValueError("at least one scene is required")
        for el in self.background:
            if el.id is not None:
                raise ValueError("storyboard background elements must not set 'id' — the compiler generates IDs")
        return self

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        ir = parse_json5_ir(source_path, cls, "storyboard")
        source_dir = source_path.parent

        resolved_bg = resolve_asset_paths(ir.background, source_dir)
        resolved_scenes = []
        for scene in ir.scenes:
            resolved_elements = resolve_asset_paths(scene.elements, source_dir)
            if resolved_elements != list(scene.elements):
                scene = scene.model_copy(update={"elements": resolved_elements})
            resolved_scenes.append(scene)

        if resolved_bg != list(ir.background) or resolved_scenes != list(ir.scenes):
            ir = ir.model_copy(update={"background": resolved_bg, "scenes": resolved_scenes})
        return ir
