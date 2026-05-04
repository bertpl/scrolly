import json
import sys
from pathlib import Path

import click
from rich.console import Console

from scrolly import __version__
from scrolly.errors import ScrollyError
from scrolly.pipeline import build_deck, validate_deck_sources

_err_console = Console(stderr=True, highlight=False)


@click.group()
@click.version_option(__version__, prog_name="scrolly")
def cli() -> None:
    """scrolly — compile a JSON5 deck into a self-contained 2D-canvas HTML presentation."""


@cli.command()
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory.",
)
@click.option("--force", is_flag=True, help="Overwrite a non-empty output directory.")
@click.option("--no-inline", is_flag=True, help="Write assets as separate files instead of inlining.")
def build(deck_path: Path, out_dir: Path, force: bool, no_inline: bool) -> None:
    """Build a deck into a self-contained HTML presentation."""
    try:
        deck = build_deck(deck_path, out_dir, force=force, inline=not no_inline)
    except ScrollyError as e:
        _err_console.print(f"[red]error:[/red] {e}")
        sys.exit(1)

    click.echo(f"Built '{deck.title or '(untitled)'}': {len(deck.slides)} slides, {len(deck.edges)} edges → {out_dir}")


@cli.command()
@click.argument("type_name", required=False)
def schema(type_name: str | None) -> None:
    """Show source file schemas. Lists types when called without an argument."""
    from scrolly.deck import deck_source_schema
    from scrolly.slide import registered_ir_types

    ir_types = registered_ir_types()

    if type_name is None:
        click.echo("Available schemas:\n")
        click.echo(f"  {'deck':<17}{'.deck.json':<24}Deck structure (slides + edges)")
        for name in sorted(ir_types):
            cls = ir_types[name]
            click.echo(f"  {name:<17}{cls.SUFFIX:<24}{cls.DESCRIPTION}")
        return

    if type_name == "deck":
        click.echo(json.dumps(deck_source_schema(), indent=2))
        return

    if type_name not in ir_types:
        known = ", ".join(sorted(["deck", *ir_types]))
        _err_console.print(f"[red]error:[/red] unknown type '{type_name}' (known: {known})")
        sys.exit(1)

    click.echo(json.dumps(ir_types[type_name].source_schema(), indent=2))


@cli.command()
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate(deck_path: Path) -> None:
    """Validate a deck and all its slide sources without building."""
    try:
        deck = validate_deck_sources(deck_path)
    except ScrollyError as e:
        _err_console.print(f"[red]error:[/red] {e}")
        sys.exit(1)

    click.echo(f"Valid: {len(deck.slides)} slides, {len(deck.edges)} edges")


_INIT_DECK = """\
{
  title: "My Deck",
  slides: [
    { id: "intro", position: [0, 0], source: "slides/intro.static.md" },
  ],
  edges: [],
}
"""

_INIT_SLIDE = """\
---
initial_scroll_position: 0
---

# My Deck

Welcome to your new presentation.
"""


@cli.command()
@click.argument("dir_path", type=click.Path(path_type=Path))
def init(dir_path: Path) -> None:
    """Scaffold a minimal deck in DIR_PATH."""
    if dir_path.exists() and any(dir_path.iterdir()):
        _err_console.print(f"[red]error:[/red] directory is not empty: {dir_path}")
        sys.exit(1)

    slides_dir = dir_path / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    (dir_path / "deck.deck.json").write_text(_INIT_DECK)
    (slides_dir / "intro.static.md").write_text(_INIT_SLIDE)

    click.echo(f"Created deck in {dir_path}")
