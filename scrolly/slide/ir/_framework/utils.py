"""Shared parsing utilities for JSON5-based slide IR models."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypeVar

import json5
from pydantic import BaseModel, ValidationError

from scrolly._shared.paths import resolve_reference
from scrolly.errors import SlideSourceError

T = TypeVar("T", bound=BaseModel)

_FILE_FIELD_MAP: dict[str, str] = {
    "markdown_file": "markdown",
    "html_file": "html",
    "mermaid_file": "mermaid",
    "iframe_html_file": "iframe_html",
}

# ``*_file`` fields whose target is parsed as JSON5 (an element array)
# rather than inlined as text. Includes resolve nested references
# against the included file's own directory and rebase child asset
# paths so they keep resolving against the including file.
_JSON5_FILE_FIELD_MAP: dict[str, str] = {
    "container_file": "container",
}


def parse_json5_ir(source_path: Path, ir_cls: type[T], label: str) -> T:
    """Read a JSON5 file and validate against a pydantic model class.

    ``label`` is used in error messages (e.g. ``"slide"``).
    """
    raw = parse_json5_source(source_path, label)
    return validate_json5_ir(raw, source_path.parent, source_path, ir_cls, label)


def parse_json5_source(source_path: Path, label: str) -> dict:
    """Read a JSON5 file and return its raw object (the pre-validation half of ``parse_json5_ir``)."""
    try:
        text = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SlideSourceError(code="E505", message=f"{label} source not found: {source_path}") from None

    try:
        raw = json5.loads(text)
    except ValueError as exc:
        raise SlideSourceError(
            code="E001",
            message=f"{label} source is not valid JSON5: {source_path}: {exc}",
        ) from None

    if not isinstance(raw, dict):
        raise SlideSourceError(
            code="E002",
            message=f"{label} source must be a JSON object, got {type(raw).__name__}: {source_path}",
        )
    return raw


def validate_json5_ir(raw: dict, source_dir: Path, source_path: Path, ir_cls: type[T], label: str) -> T:
    """Resolve ``*_file`` fields against ``source_dir`` and validate ``raw`` against ``ir_cls``.

    The post-parse half of ``parse_json5_ir``, split out so a
    template-slide stub can validate its *rendered* object with the
    template file's directory as the reference base.
    """
    try:
        _resolve_file_fields(raw, source_dir)
    except FileNotFoundError as exc:
        raise SlideSourceError(code="E505", message=f"{label} file field error: {source_path}: {exc}") from None
    except ValueError as exc:
        raise SlideSourceError(code="E012", message=f"{label} file field error: {source_path}: {exc}") from None

    try:
        return ir_cls.model_validate(raw)
    except ValidationError as exc:
        raise SlideSourceError(code="E299", message=f"{label} validation failed: {source_path}: {exc}") from None


def _resolve_file_fields(obj: dict | list, source_dir: Path, include_stack: tuple[Path, ...] = ()) -> None:
    """Recursively resolve ``*_file`` fields to inline content in place.

    Text fields (``_FILE_FIELD_MAP``) inline the target's text. JSON5
    fields (``_JSON5_FILE_FIELD_MAP``) parse the target as a JSON5
    element array, resolve *its* file references against the included
    file's directory, and rebase child asset paths onto ``source_dir``.
    ``include_stack`` carries the chain of included files for cycle
    detection (E507).
    """
    if isinstance(obj, dict):
        for file_key, inline_key in _FILE_FIELD_MAP.items():
            if file_key in obj:
                if inline_key in obj:
                    raise ValueError(f"cannot specify both '{inline_key}' and '{file_key}'")
                file_path = resolve_reference(obj.pop(file_key), source_dir, what=file_key)
                try:
                    obj[inline_key] = file_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    raise FileNotFoundError(f"{file_key} not found: {file_path}") from None
        for file_key, inline_key in _JSON5_FILE_FIELD_MAP.items():
            if file_key in obj:
                if inline_key in obj:
                    raise ValueError(f"cannot specify both '{inline_key}' and '{file_key}'")
                obj[inline_key] = _load_json5_include(obj.pop(file_key), file_key, source_dir, include_stack)
        for value in obj.values():
            if isinstance(value, (dict, list)):
                _resolve_file_fields(value, source_dir, include_stack)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _resolve_file_fields(item, source_dir, include_stack)


def _load_json5_include(authored: str, file_key: str, source_dir: Path, include_stack: tuple[Path, ...]) -> list:
    """Load a JSON5 element-array include for ``file_key`` and return the resolved list.

    The included array's own ``*_file`` references resolve against the
    included file's directory; its asset paths are rebased so they keep
    resolving against ``source_dir`` afterwards.
    """
    file_path = resolve_reference(authored, source_dir, what=file_key)
    normalized = file_path.resolve()
    if normalized in include_stack:
        chain = " -> ".join(str(p) for p in (*include_stack, normalized))
        raise SlideSourceError(code="E507", message=f"{file_key} include cycle: {chain}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"{file_key} not found: {file_path}") from None
    try:
        parsed = json5.loads(text)
    except ValueError as exc:
        raise SlideSourceError(
            code="E001", message=f"{file_key} target is not valid JSON5: {file_path}: {exc}"
        ) from None
    if not isinstance(parsed, list):
        raise SlideSourceError(
            code="E002",
            message=f"{file_key} target must be a JSON5 array of elements, got {type(parsed).__name__}: {file_path}",
        )
    include_dir = file_path.parent
    _resolve_file_fields(parsed, include_dir, (*include_stack, normalized))
    _rebase_asset_paths(parsed, include_dir, source_dir)
    return parsed


def _rebase_asset_paths(obj: dict | list, from_dir: Path, to_dir: Path) -> None:
    """Rewrite relative asset paths authored against ``from_dir`` to resolve against ``to_dir``.

    Applied to included element arrays so their ``image`` /
    ``image_sequence`` paths keep pointing at the same files once the
    array is spliced into a source that resolves assets against its own
    directory. Nested includes compose: each level rebases to its
    parent, and the chain unwinds to the root source.
    """
    if from_dir.resolve() == to_dir.resolve():
        return
    prefix = Path(os.path.relpath(from_dir, to_dir))
    if isinstance(obj, dict):
        if isinstance(obj.get("image"), str):
            obj["image"] = str(prefix / obj["image"])
        if isinstance(obj.get("image_sequence"), list):
            obj["image_sequence"] = [str(prefix / p) if isinstance(p, str) and p else p for p in obj["image_sequence"]]
        for value in obj.values():
            if isinstance(value, (dict, list)):
                _rebase_asset_paths(value, from_dir, to_dir)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _rebase_asset_paths(item, from_dir, to_dir)


def resolve_asset_paths(
    elements: list,
    source_dir: Path,
) -> list:
    """Resolve relative image paths to absolute for any ``ImageElement`` / ``ImageSequenceElement``.

    Returns a new list (frozen models require copies).
    """
    # Function-local import to avoid a circular import at module load: the
    # concrete element types are defined in a sibling module of this one.
    from scrolly.slide.ir._framework.element import ContainerElement, ImageElement, ImageSequenceElement

    resolved = []
    for item in elements:
        if isinstance(item, ImageElement):
            abs_path = resolve_reference(item.image, source_dir, what="image").resolve()
            item = item.model_copy(update={"image": abs_path})
        elif isinstance(item, ImageSequenceElement):
            abs_paths = [
                resolve_reference(p, source_dir, what="image_sequence").resolve() if p is not None else None
                for p in item.image_sequence
            ]
            item = item.model_copy(update={"image_sequence": abs_paths})
        elif isinstance(item, ContainerElement):
            children = resolve_asset_paths(item.container, source_dir)
            if children != list(item.container):
                item = item.model_copy(update={"container": children})
        resolved.append(item)
    return resolved
