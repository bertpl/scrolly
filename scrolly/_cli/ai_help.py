"""Builds the ``scrolly --help-for-ai-tools`` document.

One markdown document covering the entire CLI surface in a single read —
the command tree, every source-file and element schema, and every error
code — so an LLM agent gets the whole picture without round-tripping
through ``scrolly schema`` / ``scrolly errors`` per type and code. It is
a pure aggregator: every section is the output the individual commands
already produce, merged under markdown headers, never re-rendered.
"""

from __future__ import annotations

from collections.abc import Iterator

import click

from scrolly._cli.schema import element_schema_json, file_schema_json, file_type_names
from scrolly.errors import registered_codes
from scrolly.errors._catalog import load_body
from scrolly.slide import element_source_types


# ==================================================================================================
#  Document assembly
# ==================================================================================================
def build_ai_help(root_command: click.Command, version: str) -> str:
    """Render the whole CLI reference as one self-contained markdown document.

    Args:
        root_command: The top-level ``scrolly`` Click group, walked for the command tree.
        version: The scrolly version string, shown in the document header.

    Returns:
        A single markdown document: header, command tree, file schemas,
        element schemas, and error codes — heading levels nested so the
        whole document forms one consistent hierarchy.
    """
    sections = [
        _header(version),
        _commands_section(root_command),
        _file_schemas_section(),
        _content_from_files_section(),
        _element_schemas_section(),
        _error_codes_section(),
    ]
    return "\n\n".join(sections) + "\n"


def _header(version: str) -> str:
    """Render the document title and one-paragraph orientation."""
    return (
        f"# scrolly {version} — CLI reference for AI tools\n\n"
        "The complete scrolly command-line surface in one document: every command, "
        "every source-file and element schema, and every error code. Generated from "
        "the installed scrolly, so it matches this version exactly."
    )


# ==================================================================================================
#  Sections
# ==================================================================================================
def _commands_section(root_command: click.Command) -> str:
    """Render every command's help text, walking the full command tree."""
    blocks = ["## Commands"]
    for path, help_text in _walk_commands(root_command, "scrolly", None):
        blocks.append(f"### `{path}`\n\n```\n{help_text.rstrip()}\n```")
    return "\n\n".join(blocks)


def _file_schemas_section() -> str:
    """Render the JSON Schema for every source-file type (deck, slide)."""
    blocks = ["## File schemas"]
    for name in file_type_names():
        blocks.append(f"### `{name}`\n\n```json\n{file_schema_json(name)}\n```")
    return "\n\n".join(blocks)


def _content_from_files_section() -> str:
    """Render the one-paragraph rule for the ``*_file`` content fields."""
    return (
        "## Content from files\n\n"
        "Text-content element fields can be authored from external files: "
        "`markdown_file`, `html_file`, `mermaid_file`, and `iframe_html_file` "
        "each name a file whose text is read and inlined at parse time, "
        "replacing the corresponding inline field (`markdown`, `html`, "
        "`mermaid`, `iframe_html`). Paths resolve relative to the slide "
        "source file. Author exactly one form per element — specifying both "
        "the inline field and its `*_file` form is an error (E012); a "
        "missing file is an error (E505). Use the file form to keep large "
        "content out of slide sources."
    )


def _element_schemas_section() -> str:
    """Render the JSON Schema for every slide-element type."""
    blocks = ["## Element schemas"]
    for key in element_source_types():
        blocks.append(f"### `{key}`\n\n```json\n{element_schema_json(key)}\n```")
    return "\n\n".join(blocks)


def _error_codes_section() -> str:
    """Render the catalog entry for every registered error code.

    Each catalog body is verbatim markdown starting at its own ``# E…``
    heading; demoting by two levels nests every entry under this section.
    """
    blocks = ["## Error codes"]
    for code in sorted(registered_codes()):
        blocks.append(_demote_headings(load_body(code).rstrip(), 2))
    return "\n\n".join(blocks)


# ==================================================================================================
#  Helpers
# ==================================================================================================
def _walk_commands(
    command: click.Command, info_name: str, parent_ctx: click.Context | None
) -> Iterator[tuple[str, str]]:
    """Yield ``(command_path, help_text)`` for a command and all its subcommands, depth-first."""
    ctx = click.Context(command, info_name=info_name, parent=parent_ctx)
    yield ctx.command_path, command.get_help(ctx)
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            sub = command.get_command(ctx, name)
            if sub is None or sub.hidden:
                continue
            yield from _walk_commands(sub, name, ctx)


def _demote_headings(markdown: str, levels: int) -> str:
    """Deepen every ATX heading by ``levels`` ``#``, leaving fenced code blocks untouched."""
    out = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("#"):
            line = "#" * levels + line
        out.append(line)
    return "\n".join(out)
