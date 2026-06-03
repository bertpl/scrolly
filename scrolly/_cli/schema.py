"""``scrolly schema`` — show source-file and slide-element schemas from the CLI.

A Click group with two parallel subcommands, mirroring the
subcommand-group structure of ``scrolly introspect``:

* ``scrolly schema``                      — combined index of file and element schemas.
* ``scrolly schema file``                 — index of source-file schemas (deck, slide).
* ``scrolly schema file <type>``          — JSON Schema for a source-file type.
* ``scrolly schema file --list-types``    — bare file-type names, one per line.
* ``scrolly schema element``              — index of element schemas.
* ``scrolly schema element <type>``       — JSON Schema for an element type.
* ``scrolly schema element --list-types`` — bare element keys, one per line.

``schema`` shows static *type* definitions; ``introspect`` inspects a
specific *resolved deck instance* — different surfaces, kept distinct.
"""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console

_err_console = Console(stderr=True, highlight=False)

# Width of the name / suffix columns in the human-readable index, matching
# the alignment used by ``scrolly errors``.
_NAME_COL = 17
_SUFFIX_COL = 24


# ==================================================================================================
#  schema group
# ==================================================================================================
@click.group(name="schema", invoke_without_command=True)
@click.pass_context
def schema(ctx: click.Context) -> None:
    """Show source-file and slide-element schemas.

    \b
    scrolly schema                  → combined index (file + element schemas)
    scrolly schema file [<type>]    → source-file schemas (deck, slide)
    scrolly schema element [<type>] → slide-element schemas (markdown, image, …)

    Append --list-types to either subcommand for bare names (agent / scripting).
    Shows static type definitions; use `scrolly introspect` for a resolved deck.
    """
    if ctx.invoked_subcommand is None:
        _print_file_index()
        click.echo()
        _print_element_index()


# ==================================================================================================
#  Subcommands
# ==================================================================================================
@schema.command(name="file")
@click.argument("type_name", required=False)
@click.option(
    "--list-types",
    "list_types",
    is_flag=True,
    help="Print bare file-type names one per line (no descriptions) for scripting use.",
)
def schema_file(type_name: str | None, list_types: bool) -> None:
    """Source-file schemas (deck, slide).

    \b
    scrolly schema file              → formatted index of file types
    scrolly schema file <type>       → JSON Schema for <type>
    scrolly schema file --list-types → bare type names, one per line (agent / scripting)
    """
    names = file_type_names()

    if list_types:
        for name in names:
            click.echo(name)
        return

    if type_name is None:
        _print_file_index()
        return

    schema_text = file_schema_json(type_name)
    if schema_text is None:
        _err_console.print(f"[red]error:[/red] unknown file type '{type_name}' (known: {', '.join(names)})")
        sys.exit(1)
    click.echo(schema_text)


@schema.command(name="element")
@click.argument("type_name", required=False)
@click.option(
    "--list-types",
    "list_types",
    is_flag=True,
    help="Print bare element keys one per line (no descriptions) for scripting use.",
)
def schema_element(type_name: str | None, list_types: bool) -> None:
    """Slide-element schemas (markdown, image, …).

    \b
    scrolly schema element              → formatted index of element types
    scrolly schema element <type>       → JSON Schema for <type>
    scrolly schema element --list-types → bare element keys, one per line (agent / scripting)
    """
    from scrolly.slide import element_source_types

    elements = element_source_types()

    if list_types:
        for key in elements:
            click.echo(key)
        return

    if type_name is None:
        _print_element_index()
        return

    schema_text = element_schema_json(type_name)
    if schema_text is None:
        _err_console.print(f"[red]error:[/red] unknown element type '{type_name}' (known: {', '.join(elements)})")
        sys.exit(1)
    click.echo(schema_text)


# ==================================================================================================
#  Schema lookup + index rendering
# ==================================================================================================
def file_type_names() -> list[str]:
    """Return the sorted source-file type names (deck + registered slide types)."""
    from scrolly.slide import registered_ir_types

    return sorted(["deck", *registered_ir_types()])


def _file_schema(type_name: str) -> dict | None:
    """Return the JSON Schema for a source-file type, or ``None`` if unknown."""
    from scrolly.deck import deck_source_schema
    from scrolly.slide import registered_ir_types

    if type_name == "deck":
        return deck_source_schema()
    ir_types = registered_ir_types()
    if type_name in ir_types:
        return ir_types[type_name].source_schema()
    return None


def file_schema_json(type_name: str) -> str | None:
    """Render a source-file type's JSON Schema as indented JSON text, or ``None`` if unknown."""
    schema_dict = _file_schema(type_name)
    return None if schema_dict is None else json.dumps(schema_dict, indent=2)


def element_schema_json(type_name: str) -> str | None:
    """Render an element type's JSON Schema as indented JSON text, or ``None`` if unknown."""
    from scrolly.slide import element_source_types

    elements = element_source_types()
    if type_name not in elements:
        return None
    return json.dumps(elements[type_name].source_schema(), indent=2)


def _print_file_index() -> None:
    """Print the human-readable index of source-file schemas."""
    from scrolly.slide import registered_ir_types

    click.echo("File schemas (source files):\n")
    click.echo(f"  {'deck':<{_NAME_COL}}{'.deck.json':<{_SUFFIX_COL}}Deck structure (slides + edges)")
    for name, cls in sorted(registered_ir_types().items()):
        click.echo(f"  {name:<{_NAME_COL}}{cls.SUFFIX:<{_SUFFIX_COL}}{cls.DESCRIPTION}")


def _print_element_index() -> None:
    """Print the human-readable index of slide-element schemas."""
    from scrolly.slide import element_source_types

    click.echo("Element schemas (slide elements):\n")
    for key, cls in element_source_types().items():
        click.echo(f"  {key:<{_NAME_COL}}{cls.DESCRIPTION}")
