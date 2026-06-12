import json
import sys
from pathlib import Path

import click

from scrolly import __version__
from scrolly._cli._introspect import introspect
from scrolly._cli.console import err_console, error_exit, print_error
from scrolly._cli.errors import errors_command
from scrolly._cli.schema import schema
from scrolly.deck import Deck
from scrolly.errors import ScrollyError, ValidationError
from scrolly.pipeline import build_deck, load_deck
from scrolly.pipeline.lint import lint_deck


class ReencodeQuality(click.ParamType):
    """Click type for ``--reencode-bitmaps``: an integer quality, or ``off``.

    ``off`` parses to ``None`` (the full kill switch); any other value must
    be an integer in ``[0, 100]``, passed through to each codec's native
    quality scale.
    """

    name = "quality|off"

    def convert(self, value: object, param: click.Parameter | None, ctx: click.Context | None) -> int | None:
        """Parse to ``None`` (``off``) or a validated ``0..100`` integer."""
        if value is None or isinstance(value, int):
            return value
        if value == "off":
            return None
        try:
            quality = int(value)
        except ValueError:
            self.fail(f"{value!r} is not 'off' or an integer 0-100", param, ctx)
        if not 0 <= quality <= 100:
            self.fail(f"quality {quality} is out of range 0-100", param, ctx)
        return quality


def _resolve_reencode_quality(quality: int | None, *, no_inline: bool) -> int | None:
    """Resolve the effective re-encode quality, enforcing the inline requirement.

    Re-encoding runs only inside the inlining path. An *explicit*
    ``--reencode-bitmaps <quality>`` combined with ``--no-inline`` is a
    usage error; the *default* quality under ``--no-inline`` instead
    silently disables re-encoding, so turning the default on never
    invalidates a pre-existing ``--no-inline`` invocation.

    Raises:
        click.UsageError: When an explicit quality meets ``--no-inline``.
    """
    if not no_inline:
        return quality
    source = click.get_current_context().get_parameter_source("reencode_quality")
    explicit = source is click.core.ParameterSource.COMMANDLINE
    if explicit and quality is not None:
        raise click.UsageError(
            "--reencode-bitmaps requires inlining; it cannot be combined with "
            "--no-inline. Pass '--reencode-bitmaps off' or drop --no-inline."
        )
    return None


def _emit_ai_help(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Eager ``--help-for-ai-tools`` callback: print the full CLI reference and exit."""
    if not value or ctx.resilient_parsing:
        return
    from scrolly._cli.ai_help import build_ai_help

    click.echo(build_ai_help(ctx.find_root().command, __version__))
    ctx.exit()


@click.group()
@click.version_option(__version__, prog_name="scrolly")
@click.option(
    "--help-for-ai-tools",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_emit_ai_help,
    help="Print the entire CLI reference (commands, schemas, error codes) as one markdown document for AI agents.",
)
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
@click.option(
    "--out-file",
    "out_file",
    default="index.html",
    show_default=True,
    help="Name of the output HTML file inside the output directory.",
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
    help="Disable gzip compression of the output document and its inlined assets.",
)
@click.option(
    "--offline",
    is_flag=True,
    help=(
        "Skip the mermaid CDN download and use the wheel-bundled mermaid for "
        "byte-reproducibility. SCROLLY_OFFLINE=1 in the environment is equivalent."
    ),
)
@click.option(
    "--reencode-bitmaps",
    "reencode_quality",
    type=ReencodeQuality(),
    default=95,
    show_default=True,
    metavar="QUALITY|off",
    help="Re-encode raster images (jpeg/png/gif/webp/avif) to the smallest of "
    "WebP/AVIF candidates at the given quality, shipping the original when it "
    "wins. Never enlarges a deck; SVG is never touched. Use 'off' to disable.",
)
@click.option(
    "--allow-path",
    "allow_paths",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Extra directory authored file references may resolve into; repeatable. "
    "By default every referenced file must live inside the deck directory.",
)
@click.option(
    "--no-minification",
    is_flag=True,
    hidden=True,
    help="Debug only: ship the canvas JS and CSS as readable source, comments included.",
)
def build(
    deck_path: Path,
    out_dir: Path,
    out_file: str,
    force: bool,
    no_inline: bool,
    strict: bool,
    simplified_zoom_control: bool,
    no_compress: bool,
    offline: bool,
    reencode_quality: int | None,
    allow_paths: tuple[Path, ...],
    no_minification: bool,
) -> None:
    """Build a deck into a self-contained HTML presentation."""
    reencode_quality = _resolve_reencode_quality(reencode_quality, no_inline=no_inline)
    try:
        deck = build_deck(
            deck_path,
            out_dir,
            force=force,
            inline=not no_inline,
            simplified_zoom_control=simplified_zoom_control,
            compress=not no_compress,
            offline=offline,
            out_file=out_file,
            minify=not no_minification,
            reencode_quality=reencode_quality,
            allow_paths=allow_paths,
        )
    except ScrollyError as e:
        error_exit(str(e))

    if strict:
        _report_diagnostics(deck)

    click.echo(
        f"Built '{deck.title or '(untitled)'}': {len(deck.slides)} slides, "
        f"{len(deck.edges)} edges → {out_dir / out_file}"
    )


@cli.command()
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--strict", is_flag=True, help="Enable additional lint checks (e.g. out-of-range keyframes).")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help='Emit machine-readable JSON instead of text: {"ok": bool, "errors": [...]}.',
)
@click.option(
    "--allow-path",
    "allow_paths",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Extra directory authored file references may resolve into; repeatable. "
    "By default every referenced file must live inside the deck directory.",
)
def validate(deck_path: Path, strict: bool, as_json: bool, allow_paths: tuple[Path, ...]) -> None:
    """Validate a deck and all its slide sources without building."""
    try:
        deck, _ = load_deck(deck_path, allow_paths=allow_paths)
    except ScrollyError as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "errors": [_error_to_dict(e)]}, indent=2))
        else:
            print_error(str(e))
        sys.exit(1)

    if strict:
        _report_diagnostics(deck)

    if as_json:
        click.echo(json.dumps({"ok": True, "errors": []}, indent=2))
    else:
        click.echo(f"Valid: {len(deck.slides)} slides, {len(deck.edges)} edges")


def _error_to_dict(err: ScrollyError) -> dict:
    """Serialize a ``ScrollyError`` for JSON output."""
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


def _report_diagnostics(deck: Deck) -> None:
    """Run lint checks and print any diagnostics to stderr."""
    diagnostics = lint_deck(deck)
    for d in diagnostics:
        err_console.print(f"[yellow]{d.level}:[/yellow] {d.location}: {d.message}")


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
  title: "Intro",
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
        error_exit(f"directory is not empty: {dir_path}")

    slides_dir = dir_path / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    (dir_path / "deck.deck.json").write_text(_INIT_DECK)
    (slides_dir / "intro.slide.json").write_text(_INIT_SLIDE)

    click.echo(f"Created deck in {dir_path}")


cli.add_command(errors_command)
cli.add_command(introspect)
cli.add_command(schema)
