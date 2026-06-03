"""Parse a JSON5 deck file into a `RawDeck`.

Purely syntactic: checks file schema (required fields, types) and returns a
`RawDeck` whose edges may still have omitted sides. Semantic checks (unique
ids, edges reference real slides, one-slide-per-cell, diagonal-inference
rejection) live in `validator.py` and `inference.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import json5

from scrolly.deck.model import Position, RawDeck, RawEdge, RawEndpoint, Side, Slide, SlideGroup
from scrolly.errors import DeckParseError


def parse_deck(deck_path: Path) -> RawDeck:
    """Load and parse a JSON5 deck file.

    Slide source paths are resolved relative to the deck file's directory.
    """
    try:
        raw = json5.loads(deck_path.read_text())
    except ValueError as e:
        raise DeckParseError(code="E001", message=f"{deck_path}: could not parse JSON5: {e}") from e

    if not isinstance(raw, dict):
        raise DeckParseError(
            code="E002",
            message=f"{deck_path}: deck file must be a JSON5 object, got {type(raw).__name__}",
        )

    title = raw.get("title")
    if title is not None and not isinstance(title, str):
        raise DeckParseError(code="E004", message=f"{deck_path}: field 'title' must be a string if present")

    slides_raw = _require_list(raw, "slides", deck_path)
    slides, groups = _parse_slides_and_groups(slides_raw, deck_path)

    edges_raw = raw.get("edges", [])
    if not isinstance(edges_raw, list):
        raise DeckParseError(code="E005", message=f"{deck_path}: field 'edges' must be a list if present")
    edges = tuple(_parse_edge(e, idx) for idx, e in enumerate(edges_raw))

    return RawDeck(title=title, slides=slides, edges=edges, groups=groups)


def _parse_slides_and_groups(slides_raw: list, deck_path: Path) -> tuple[tuple[Slide, ...], tuple[SlideGroup, ...]]:
    deck_dir = deck_path.parent
    slides: list[Slide] = []
    groups: list[SlideGroup] = []
    flat_idx = 0

    for top_idx, item in enumerate(slides_raw):
        ctx = f"slides[{top_idx}]"
        if not isinstance(item, dict):
            raise DeckParseError(code="E006", message=f"{ctx}: must be an object, got {type(item).__name__}")

        if "group" in item:
            label = item["group"]
            if not isinstance(label, str) or not label.strip():
                raise DeckParseError(code="E004", message=f"{ctx}: 'group' must be a non-empty string")
            label = label.strip()

            if "slides" not in item or not isinstance(item["slides"], list):
                raise DeckParseError(code="E005", message=f"{ctx}: group must have a 'slides' list")

            group_slide_ids: list[str] = []
            for inner_idx, inner in enumerate(item["slides"]):
                inner_ctx = f"slides[{top_idx}].slides[{inner_idx}]"
                if isinstance(inner, dict) and "group" in inner:
                    raise DeckParseError(code="E010", message=f"{inner_ctx}: nested groups are not allowed")
                slide = _parse_slide(inner, deck_dir, flat_idx, inner_ctx)
                slides.append(slide)
                group_slide_ids.append(slide.id)
                flat_idx += 1

            color = _parse_group_hex_color(item, ctx, "color")
            label_color = _parse_group_hex_color(item, ctx, "label_color")
            groups.append(
                SlideGroup(
                    label=label,
                    slide_ids=tuple(group_slide_ids),
                    color=color,
                    label_color=label_color,
                )
            )
        else:
            slide = _parse_slide(item, deck_dir, flat_idx, ctx)
            slides.append(slide)
            flat_idx += 1

    return tuple(slides), tuple(groups)


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _parse_group_hex_color(raw: dict, ctx: str, key: str) -> str | None:
    """Parse and validate an optional hex color field from a group object.

    Args:
        raw: The raw group object.
        ctx: Error-context prefix (e.g. ``slides[2]``).
        key: Which field to read — ``color`` (background) or ``label_color``
            (label override).

    Returns:
        The validated ``#RGB`` / ``#RRGGBB`` string, or ``None`` if the field
        is absent.

    Raises:
        DeckParseError: If present but not a string (E004) or not a valid hex
            color (E009).
    """
    if key not in raw:
        return None
    value = raw[key]
    if not isinstance(value, str):
        raise DeckParseError(code="E004", message=f"{ctx}: '{key}' must be a string, got {type(value).__name__}")
    if not _HEX_COLOR_RE.match(value):
        raise DeckParseError(code="E009", message=f"{ctx}: '{key}' must be #RGB or #RRGGBB, got '{value}'")
    return value


def _require_list(d: dict, key: str, deck_path: Path) -> list:
    if key not in d:
        raise DeckParseError(code="E003", message=f"{deck_path}: missing required field '{key}'")
    v = d[key]
    if not isinstance(v, list):
        raise DeckParseError(
            code="E005",
            message=f"{deck_path}: field '{key}' must be a list, got {type(v).__name__}",
        )
    return v


def _parse_slide(raw: Any, deck_dir: Path, idx: int, ctx: str | None = None) -> Slide:
    if ctx is None:
        ctx = f"slides[{idx}]"
    if not isinstance(raw, dict):
        raise DeckParseError(code="E006", message=f"{ctx}: must be an object, got {type(raw).__name__}")

    slide_id = _require_str(raw, "id", ctx)
    position = _parse_position(raw, ctx)
    source_raw = _require_str(raw, "source", ctx)

    source = (deck_dir / source_raw).resolve()
    return Slide(id=slide_id, position=position, source=source)


def _parse_position(raw_slide: dict, ctx: str) -> Position:
    if "position" not in raw_slide:
        raise DeckParseError(code="E003", message=f"{ctx}: missing required field 'position'")
    raw_pos = raw_slide["position"]
    if not isinstance(raw_pos, list) or len(raw_pos) != 2:
        raise DeckParseError(code="E007", message=f"{ctx}: 'position' must be a two-element array [x, y]")
    x, y = raw_pos
    if not _is_int(x) or not _is_int(y):
        raise DeckParseError(code="E008", message=f"{ctx}: 'position' entries must be integers")
    return Position(x=x, y=y)


def _require_str(d: dict, key: str, ctx: str) -> str:
    if key not in d:
        raise DeckParseError(code="E003", message=f"{ctx}: missing required field '{key}'")
    v = d[key]
    if not isinstance(v, str):
        raise DeckParseError(
            code="E004",
            message=f"{ctx}: field '{key}' must be a string, got {type(v).__name__}",
        )
    return v


def _is_int(v: Any) -> bool:
    # bool is a subclass of int in Python — exclude it.
    return isinstance(v, int) and not isinstance(v, bool)


def _parse_edge(raw: Any, idx: int) -> RawEdge:
    ctx = f"edges[{idx}]"
    if not isinstance(raw, list):
        raise DeckParseError(
            code="E005",
            message=f"{ctx}: must be a two-element array, got {type(raw).__name__}",
        )
    if len(raw) != 2:
        raise DeckParseError(code="E007", message=f"{ctx}: must be a two-element array, got {len(raw)} elements")

    return RawEdge(
        a=_parse_endpoint(raw[0], f"{ctx}[0]"),
        b=_parse_endpoint(raw[1], f"{ctx}[1]"),
    )


def _parse_endpoint(raw: Any, ctx: str) -> RawEndpoint:
    if not isinstance(raw, str):
        raise DeckParseError(code="E004", message=f"{ctx}: endpoint must be a string, got {type(raw).__name__}")

    parts = raw.split("|", 1)
    slide_id = parts[0].strip()
    if not slide_id:
        raise DeckParseError(code="E011", message=f"{ctx}: endpoint has empty slide id")

    if len(parts) == 1:
        return RawEndpoint(slide_id=slide_id, side=None)

    side_str = parts[1].strip()
    try:
        side = Side(side_str)
    except ValueError:
        valid = ", ".join(s.value for s in Side)
        raise DeckParseError(code="E011", message=f"{ctx}: side '{side_str}' is not one of ({valid})") from None

    return RawEndpoint(slide_id=slide_id, side=side)
