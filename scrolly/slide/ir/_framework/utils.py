"""Shared parsing utilities for JSON5-based slide IR models."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import json5
from pydantic import ValidationError

from scrolly.errors import SlideSourceError
from scrolly.slide.ir._framework.base import SlideIR

T = TypeVar("T", bound=SlideIR)

_FILE_FIELD_MAP: dict[str, str] = {
    "markdown_file": "markdown",
    "html_file": "html",
    "mermaid_file": "mermaid",
}


def parse_json5_ir(source_path: Path, ir_cls: type[T], label: str) -> T:
    """Read a JSON5 file and validate against a ``SlideIR`` subclass.

    ``label`` is used in error messages (e.g. ``"scrollimation"``).
    """
    try:
        text = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SlideSourceError(f"{label} source not found: {source_path}") from None

    try:
        raw = json5.loads(text)
    except ValueError as exc:
        raise SlideSourceError(f"{label} source is not valid JSON5: {source_path}: {exc}") from None

    if not isinstance(raw, dict):
        raise SlideSourceError(f"{label} source must be a JSON object, got {type(raw).__name__}: {source_path}")

    source_dir = source_path.parent
    try:
        _resolve_file_fields(raw, source_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise SlideSourceError(f"{label} file field error: {source_path}: {exc}") from None

    try:
        return ir_cls.model_validate(raw)
    except ValidationError as exc:
        raise SlideSourceError(f"{label} validation failed: {source_path}: {exc}") from None


def _resolve_file_fields(obj: dict | list, source_dir: Path) -> None:
    """Recursively resolve ``*_file`` fields to inline content in place."""
    if isinstance(obj, dict):
        for file_key, inline_key in _FILE_FIELD_MAP.items():
            if file_key in obj:
                if inline_key in obj:
                    raise ValueError(f"cannot specify both '{inline_key}' and '{file_key}'")
                file_path = source_dir / obj.pop(file_key)
                try:
                    obj[inline_key] = file_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    raise FileNotFoundError(f"{file_key} not found: {file_path}") from None
        for value in obj.values():
            if isinstance(value, (dict, list)):
                _resolve_file_fields(value, source_dir)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _resolve_file_fields(item, source_dir)


def resolve_asset_paths(
    elements: list,
    source_dir: Path,
) -> list:
    """Resolve relative image paths to absolute for any ``ImageElement`` /
    ``ImageSequenceElement`` instances.

    Returns a new list (frozen models require copies).
    """
    from scrolly.slide.ir._framework.element import ImageElement, ImageSequenceElement

    resolved = []
    for item in elements:
        if isinstance(item, ImageElement):
            abs_path = (source_dir / item.image).resolve()
            item = item.model_copy(update={"image": abs_path})
        elif isinstance(item, ImageSequenceElement):
            abs_paths = [(source_dir / p).resolve() for p in item.image_sequence]
            item = item.model_copy(update={"image_sequence": abs_paths})
        resolved.append(item)
    return resolved
