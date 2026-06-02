import json
import sys
from pathlib import Path

import click
from rich.console import Console

from scrolly import __version__
from scrolly._cli._errors import errors_command
from scrolly._cli._introspect import introspect
from scrolly._cli._schema import schema
from scrolly.errors import ScrollyError, ValidationError
from scrolly.pipeline import build_deck, load_deck
from scrolly.pipeline.lint import lint_deck

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
@click.option("--strict", is_flag=True, help="Enable additional lint checks (e.g. out-of-range keyframes).")
@click.option(
    "--simplified-zoom-control",
    is_flag=True,
    help="Use the legacy single-icon zoom-out control instead of the default deck mini-map.",
)
@click.option(
    "--no-compress",
    is_flag=True,
    help="Disable gzip compression of inlined assets.",
)
@click.option(
    "--offline",
    is_flag=True,
    help=(
        "Skip the mermaid CDN download and use the wheel-bundled mermaid for "
        "byte-reproducibility. SCROLLY_OFFLINE=1 in the environment is equivalent."
    ),
)
def build(
    deck_path: Path,
    out_dir: Path,
    force: bool,
    no_inline: bool,
    strict: bool,
    simplified_zoom_control: bool,
    no_compress: bool,
    offline: bool,
) -> None:
    """Build a deck into a self-contained HTML presentation."""
    try:
        deck = build_deck(
            deck_path,
            out_dir,
            force=force,
            inline=not no_inline,
            simplified_zoom_control=simplified_zoom_control,
            compress=not no_compress,
            offline=offline,
        )
    except ScrollyError as e:
        _err_console.print(f"[red]error:[/red] {e}")
        sys.exit(1)

    if strict:
        _report_diagnostics(deck)

    click.echo(f"Built '{deck.title or '(untitled)'}': {len(deck.slides)} slides, {len(deck.edges)} edges → {out_dir}")


@cli.command()
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--strict", is_flag=True, help="Enable additional lint checks (e.g. out-of-range keyframes).")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help='Emit machine-readable JSON instead of text: {"ok": bool, "errors": [...]}.',
)
def validate(deck_path: Path, strict: bool, as_json: bool) -> None:
    """Validate a deck and all its slide sources without building."""
    try:
        deck, _ = load_deck(deck_path)
    except ScrollyError as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "errors": [_error_to_dict(e)]}, indent=2))
        else:
            _err_console.print(f"[red]error:[/red] {e}")
        sys.exit(1)

    if strict:
        _report_diagnostics(deck)

    if as_json:
        click.echo(json.dumps({"ok": True, "errors": []}, indent=2))
    else:
        click.echo(f"Valid: {len(deck.slides)} slides, {len(deck.edges)} edges")


def _error_to_dict(err: ScrollyError) -> dict:
    """Serialise a ``ScrollyError`` for JSON output."""
    if isinstance(err, ValidationError):
        return {
            "code": err.code,
            "message": err.message,
            "file": err.file,
            "line": err.line,
            "field": err.field,
            "suggestion": err.suggestion,
        }
    return {"code": None, "message": str(err)}


def _report_diagnostics(deck) -> None:
    """Run lint checks and print any diagnostics to stderr."""
    diagnostics = lint_deck(deck)
    for d in diagnostics:
        _err_console.print(f"[yellow]{d.level}:[/yellow] {d.location}: {d.message}")


_INIT_DECK = """\
{
  title: "My Deck",
  slides: [
    { id: "intro", position: [0, 0], source: "slides/intro.slide.json" },
  ],
  edges: [],
}
"""

_INIT_SLIDE = """\
{
  title: "My Deck",
  elements: [
    { markdown: "# My Deck\\n\\nWelcome to your new presentation." },
  ],
}
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
    (slides_dir / "intro.slide.json").write_text(_INIT_SLIDE)

    click.echo(f"Created deck in {dir_path}")


cli.add_command(errors_command)
cli.add_command(introspect)
cli.add_command(schema)
