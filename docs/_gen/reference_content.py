"""Pure renderers for the auto-generated reference pages.

Turns the installed scrolly's own introspection surfaces — element
schemas (``scrolly schema element``) and the error catalog (``scrolly
errors``) — into Markdown pages. Kept free of any ``mkdocs`` import so
the rendering logic is unit-testable on its own; ``gen_reference.py`` is
the thin ``mkdocs-gen-files`` wrapper that writes what these return.
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

from scrolly.deck import deck_source_schema
from scrolly.errors import registered_codes
from scrolly.errors._catalog import load_body, load_summary
from scrolly.slide import element_source_types
from scrolly.slide.ir import SlideElement, SlideIR

_ELEMENT_SNIPPET_DIR = Path(__file__).resolve().parent / "element_snippets"
_FILE_SNIPPET_DIR = Path(__file__).resolve().parent / "file_snippets"

_ANIMATED_LABELS = {
    "AnimatedScalar": "number (animatable)",
    "AnimatedVec2": "[x, y] (animatable)",
    "AnimatedSizeDim": 'number | "auto" (animatable)',
}
_SCALAR_LABELS = {
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
    Path: "path",
    type(None): "null",
}


# ==================================================================================================
#  Field-table rendering
# ==================================================================================================
def _cell(text: str) -> str:
    """Collapse whitespace and escape pipes so ``text`` is safe in a Markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def _literal_value(value: object) -> str:
    """Render one ``Literal`` member as it would appear in source (quoted if a string)."""
    return f'"{value}"' if isinstance(value, str) else str(value)


def _type_label(annotation: object) -> str:
    """Return a human-readable type label for a Pydantic field annotation."""
    name = getattr(annotation, "__name__", None)
    if name in _ANIMATED_LABELS:
        return _ANIMATED_LABELS[name]

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        return " | ".join(_literal_value(a) for a in args)
    if origin in (types.UnionType, Union):
        non_none = [a for a in args if a is not type(None)]
        label = " | ".join(_type_label(a) for a in non_none)
        return f"{label} (optional)" if len(non_none) != len(args) else label
    if origin in (list, tuple):
        inner = " | ".join(_type_label(a) for a in args if a is not Ellipsis)
        return f"list of {inner}"

    return _SCALAR_LABELS.get(annotation, name or str(annotation))


def _default_label(value: object) -> str:
    """Render a JSON-friendly default value as inline code."""
    if value is None:
        return "`null`"
    return f"`{json.dumps(value)}`"


def _fields_table(cls: type[SlideElement], names: list[str]) -> str:
    """Render the named fields of ``cls`` as a Markdown table.

    Args:
        cls: Element source model to read fields from.
        names: Field names to include, in display order.

    Returns:
        A Markdown table with Field / Type / Default / Description columns.
    """
    schema = cls.source_schema()
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    rows = ["| Field | Type | Default | Description |", "|---|---|---|---|"]
    for name in names:
        prop = props.get(name, {})
        type_label = _cell(_type_label(cls.model_fields[name].annotation))
        default = "**required**" if name in required else _default_label(prop.get("default"))
        description = _cell(prop.get("description", ""))
        rows.append(f"| `{name}` | {type_label} | {default} | {description} |")
    return "\n".join(rows)


def _common_field_names() -> list[str]:
    """Return the positioning / animation field names shared by every element."""
    return list(SlideElement.model_fields)


def _schema_type_label(prop: dict) -> str:
    """Return a readable type label for a raw JSON-Schema property dict.

    Used for the file-schema (deck / slide) pages, whose schemas are plain
    dicts rather than Pydantic models. Arrays render as a bare ``array`` —
    their item shape is carried by the page's example snippet.
    """
    if "$ref" in prop:
        return prop["$ref"].rsplit("/", 1)[-1]
    for combinator in ("anyOf", "oneOf"):
        if combinator in prop:
            return " | ".join(_schema_type_label(sub) for sub in prop[combinator])
    if "const" in prop:
        return _literal_value(prop["const"])
    if "enum" in prop:
        return " | ".join(_literal_value(v) for v in prop["enum"])
    return prop.get("type", "object")


def _schema_fields_table(schema: dict) -> str:
    """Render the top-level properties of a raw JSON Schema as a Markdown table."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    rows = ["| Field | Type | Default | Description |", "|---|---|---|---|"]
    for name, prop in props.items():
        type_label = _cell(_schema_type_label(prop))
        default = "**required**" if name in required else _default_label(prop.get("default"))
        description = _cell(prop.get("description", ""))
        rows.append(f"| `{name}` | {type_label} | {default} | {description} |")
    return "\n".join(rows)


# ==================================================================================================
#  Element pages
# ==================================================================================================
def element_keys() -> list[str]:
    """Return the element source keys, sorted (e.g. ``image_sequence``)."""
    return list(element_source_types())


def _snippet(directory: Path, key: str) -> str:
    """Return the hand-authored example snippet for a key from ``directory``."""
    return (directory / f"{key}.json5").read_text().strip()


def element_page(key: str) -> str:
    """Render the reference page for a single element type."""
    cls = element_source_types()[key]
    common = set(_common_field_names())
    specific = [name for name in cls.model_fields if name not in common]

    return "\n".join(
        [
            f"# `{key}` element",
            "",
            cls.DESCRIPTION,
            "",
            "## Fields",
            "",
            _fields_table(cls, specific),
            "",
            "Every element also shares the [common fields](index.md#common-fields) — "
            "position, size, anchor, opacity, scale, and angle.",
            "",
            "## Example",
            "",
            "```json5",
            _snippet(_ELEMENT_SNIPPET_DIR, key),
            "```",
            "",
        ]
    )


def element_index_page() -> str:
    """Render the element-schemas overview page (element table + common fields)."""
    rows = ["| Element | Description |", "|---|---|"]
    for key, cls in element_source_types().items():
        rows.append(f"| [`{key}`]({key}.md) | {_cell(cls.DESCRIPTION)} |")

    return "\n".join(
        [
            "# Element schemas",
            "",
            "Slides are built from positioned elements. Each element type is "
            "identified by its content field (e.g. `markdown:`); see its page "
            "for the full field list.",
            "",
            "\n".join(rows),
            "",
            "## Common fields",
            "",
            "Every element shares these positioning and animation fields:",
            "",
            _fields_table(SlideElement, _common_field_names()),
            "",
        ]
    )


# ==================================================================================================
#  File-schema pages (deck, slide)
# ==================================================================================================
_FILE_DESCRIPTIONS = {
    "deck": "The deck manifest: slides positioned on an integer grid, plus optional navigation edges.",
    "slide": "A single slide: a list of positioned, animatable elements plus its scroll behavior.",
}


def file_schema_keys() -> list[str]:
    """Return the source-file schema keys, in display order."""
    return ["deck", "slide"]


def _file_schema(key: str) -> dict:
    """Return the JSON Schema for a source-file type."""
    return deck_source_schema() if key == "deck" else SlideIR.source_schema()


def file_schema_page(key: str) -> str:
    """Render the reference page for a source-file type (deck or slide)."""
    parts = [
        f"# `{key}` source file",
        "",
        _FILE_DESCRIPTIONS[key],
        "",
        "## Fields",
        "",
        _schema_fields_table(_file_schema(key)),
        "",
    ]
    if key == "slide":
        parts += [
            "Each entry in `elements` is one of the element types — see [Element schemas](../elements/index.md).",
            "",
        ]
    parts += ["## Example", "", "```json5", _snippet(_FILE_SNIPPET_DIR, key), "```", ""]
    return "\n".join(parts)


def file_index_page() -> str:
    """Render the file-schemas overview page (deck / slide table)."""
    rows = ["| File | Description |", "|---|---|"]
    for key in file_schema_keys():
        rows.append(f"| [`{key}`]({key}.md) | {_cell(_FILE_DESCRIPTIONS[key])} |")

    return "\n".join(
        [
            "# File schemas",
            "",
            "A scrolly deck is a `.deck.json` manifest plus one `.slide.json` "
            "file per slide — the two source file formats below.",
            "",
            "\n".join(rows),
            "",
        ]
    )


# ==================================================================================================
#  Error-code pages
# ==================================================================================================
def error_codes() -> list[str]:
    """Return the registered error codes, sorted (e.g. ``E202``)."""
    return sorted(registered_codes())


def error_page(code: str) -> str:
    """Render the reference page for a single error code (the catalog entry verbatim)."""
    return load_body(code).strip() + "\n"


def error_index_page() -> str:
    """Render the error-codes overview page (code → summary table)."""
    rows = ["| Code | Summary |", "|---|---|"]
    for code in error_codes():
        rows.append(f"| [{code}]({code}.md) | {_cell(load_summary(code))} |")

    return "\n".join(
        [
            "# Error codes",
            "",
            "Validation and parse errors carry numbered codes (e.g. `[E202]`). "
            "Look up any code's cause, example, and fix below — or from the CLI "
            "with `scrolly errors <code>`.",
            "",
            "\n".join(rows),
            "",
        ]
    )


def reference_summary() -> str:
    """Render the literate-nav ``SUMMARY.md`` for the whole Reference section.

    A single nav file (consumed by literate-nav, not built as a page) that
    wires the static CLI page together with the generated element and
    error-code sub-sections.
    """
    lines = ["- [CLI](cli.md)", "- File schemas:", "    - [Overview](files/index.md)"]
    lines += [f"    - [{key}](files/{key}.md)" for key in file_schema_keys()]
    lines += ["- Element schemas:", "    - [Overview](elements/index.md)"]
    lines += [f"    - [{key}](elements/{key}.md)" for key in element_keys()]
    lines += ["- Error codes:", "    - [Overview](errors/index.md)"]
    lines += [f"    - [{code}](errors/{code}.md)" for code in error_codes()]
    return "\n".join(lines) + "\n"
