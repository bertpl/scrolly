"""StaticIR model and frontmatter parsing for the static slide type."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self

import yaml
from pydantic import model_validator

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import SlideIR


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Frontmatter:
    """Parsed slide-file frontmatter."""

    initial_scroll_position: int
    title: str | None = None
    font_scale: float = 1.0


def split_frontmatter(source_text: str) -> tuple[str, str]:
    """Split the raw slide text into (yaml_text, body_markdown).

    Raises `SlideSourceError` if the format is unrecognised.
    """
    lines = source_text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise SlideSourceError("missing frontmatter block (no opening '---')")

    try:
        end_idx = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        raise SlideSourceError("missing frontmatter block closing '---'") from None

    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    return yaml_text, body


def parse_frontmatter(source_text: str) -> tuple[Frontmatter, str]:
    """Return (Frontmatter, body_markdown). Raises `SlideSourceError` on any issue."""
    yaml_text, body = split_frontmatter(source_text)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise SlideSourceError(f"frontmatter is not valid YAML: {e}") from e

    if data is None:
        raise SlideSourceError("frontmatter is empty")
    if not isinstance(data, dict):
        raise SlideSourceError(f"frontmatter must be a YAML mapping, got {type(data).__name__}")

    initial = data.get("initial_scroll_position")
    if initial is None:
        raise SlideSourceError("frontmatter field 'initial_scroll_position' is required")
    if not isinstance(initial, int) or isinstance(initial, bool):
        raise SlideSourceError(
            f"frontmatter field 'initial_scroll_position' must be an integer, got {type(initial).__name__}"
        )
    if initial < 0:
        raise SlideSourceError("frontmatter field 'initial_scroll_position' must be >= 0")

    title: str | None = None
    if "title" in data:
        raw_title = data["title"]
        if not isinstance(raw_title, str):
            raise SlideSourceError(f"frontmatter field 'title' must be a string, got {type(raw_title).__name__}")
        if not raw_title.strip():
            raise SlideSourceError("frontmatter field 'title' must be a non-empty string")
        title = raw_title.strip()

    font_scale: float = 1.0
    if "font_scale" in data:
        raw_scale = data["font_scale"]
        if not isinstance(raw_scale, (int, float)) or isinstance(raw_scale, bool):
            raise SlideSourceError(f"frontmatter field 'font_scale' must be a number, got {type(raw_scale).__name__}")
        if raw_scale <= 0:
            raise SlideSourceError(f"frontmatter field 'font_scale' must be > 0, got {raw_scale}")
        font_scale = float(raw_scale)

    return Frontmatter(initial_scroll_position=initial, title=title, font_scale=font_scale), body


# ---------------------------------------------------------------------------
# StaticIR
# ---------------------------------------------------------------------------
class StaticIR(SlideIR, frozen=True):
    """Parsed representation of a static slide source file.

    ``title`` is ``None`` when the frontmatter omits it — H1 extraction
    is a rendering concern handled by the renderer.
    """

    SUFFIX: ClassVar[str] = ".static.md"
    DESCRIPTION: ClassVar[str] = "Static Markdown slide"

    @classmethod
    def source_schema(cls) -> dict:
        return {
            "title": "Static slide source format",
            "description": (
                "A Markdown file with YAML frontmatter, separated by --- delimiters. "
                "The file starts with a --- line, followed by YAML fields, "
                "a closing --- line, then the Markdown body."
            ),
            "format": "markdown-frontmatter",
            "frontmatter": {
                "type": "object",
                "properties": {
                    "initial_scroll_position": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Scroll position the slide starts at on first visit.",
                    },
                    "title": {
                        "type": "string",
                        "description": (
                            "Slide title. If omitted, the renderer extracts the first H1 from the Markdown body."
                        ),
                    },
                    "font_scale": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "default": 1.0,
                        "description": "Multiplier for the slide's base font size.",
                    },
                },
                "required": ["initial_scroll_position"],
            },
            "body": {
                "type": "string",
                "format": "markdown",
                "description": "Markdown content after the closing --- delimiter.",
            },
        }

    title: str | None
    body: str
    initial_scroll_position: int
    font_scale: float = 1.0

    @model_validator(mode="after")
    def _validate(self) -> StaticIR:
        if self.initial_scroll_position < 0:
            raise ValueError(f"initial_scroll_position must be >= 0, got {self.initial_scroll_position}")
        if self.font_scale <= 0:
            raise ValueError(f"font_scale must be > 0, got {self.font_scale}")
        return self

    @classmethod
    def from_file(cls, source_path: Path) -> Self:
        try:
            raw = source_path.read_text()
        except FileNotFoundError as e:
            raise SlideSourceError(f"slide source not found: {source_path}") from e
        except OSError as e:
            raise SlideSourceError(f"could not read slide source {source_path}: {e}") from e

        frontmatter, body = parse_frontmatter(raw)

        return cls(
            title=frontmatter.title,
            body=body,
            initial_scroll_position=frontmatter.initial_scroll_position,
            font_scale=frontmatter.font_scale,
        )
