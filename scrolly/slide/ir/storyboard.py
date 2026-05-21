"""StoryboardIR model and scene types.

A storyboard is a sequence of scenes cross-faded by scrolling.  The IR
captures the authored structure; the compiler generates
``ScrollimationIR`` with the appropriate opacity keyframes.  Storyboard
uses the shared ``SlideElement`` types directly — all animatable fields
must be static (the compiler owns all animation).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scrolly.slide.ir import (
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
    parse_json5_ir,
    resolve_asset_paths,
)
from scrolly.slide.ir.scrollimation import AnyElement


def _validate_static_element(el: AnyElement, context: str) -> None:
    """Raise ValueError if any animatable field is animated."""
    for field_name in ("position", "anchor", "opacity", "scale", "angle", "width", "height"):
        field_val = getattr(el, field_name)
        if field_val.is_animated:
            raise ValueError(f"{context}: field '{field_name}' must be static in storyboard elements")


class StoryboardScene(BaseModel, frozen=True):
    """One scene in a storyboard — a group of elements shown together."""

    model_config = ConfigDict(extra="forbid")

    elements: list[AnyElement] = Field(
        description="Elements visible during this scene. Cross-faded as a group.",
    )

    @model_validator(mode="after")
    def _validate(self) -> StoryboardScene:
        """Validate scene has elements and all are static."""
        if not self.elements:
            raise ValueError("a scene must have at least one element")
        for i, el in enumerate(self.elements):
            label = f"'{el.name}'" if el.name else f"element [{i}]"
            _validate_static_element(el, label)
        return self


class StoryboardIR(SlideIR, frozen=True):
    """Top-level IR for a .storyboard.json source file."""

    SUFFIX: ClassVar[str] = ".storyboard.json"
    DESCRIPTION: ClassVar[str] = "Scene-based cross-fade"

    title: str = Field(description="Human-readable slide title, shown in navigation UI.")
    scene_distance: int = Field(
        description="Scroll distance (in abstract units) between consecutive scene positions.",
    )
    hold: int = Field(
        default=0,
        description=(
            "Dead zone in scroll units on each side of a scene position. "
            "During hold, the scene is fully visible (opacity 1). "
            "Must satisfy: 2 * hold < scene_distance."
        ),
    )
    background: list[AnyElement] = Field(
        default_factory=list,
        description="Elements always visible at full opacity behind all scenes.",
    )
    scenes: list[StoryboardScene] = Field(
        description="Ordered list of scenes. Each scene cross-fades to the next as the user scrolls.",
    )

    @model_validator(mode="after")
    def _validate(self) -> StoryboardIR:
        """Validate storyboard-level constraints."""
        if self.scene_distance <= 0:
            raise ValueError(f"scene_distance must be > 0, got {self.scene_distance}")
        if self.hold < 0:
            raise ValueError(f"hold must be >= 0, got {self.hold}")
        if 2 * self.hold >= self.scene_distance:
            raise ValueError(f"2 * hold ({2 * self.hold}) must be < scene_distance ({self.scene_distance})")
        if not self.scenes:
            raise ValueError("at least one scene is required")
        for i, el in enumerate(self.background):
            label = f"background '{el.name}'" if el.name else f"background [{i}]"
            _validate_static_element(el, label)
        return self

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        """Parse a .storyboard.json source file."""
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
