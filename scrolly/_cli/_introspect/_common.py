"""Shared machinery for the ``scrolly introspect`` subcommands.

Every subcommand goes through ``run_introspect_command``, which:

1. Loads the deck through the shared validation gate (``load_deck``).
2. On error, prints to stderr and exits non-zero with no JSON.
3. If ``slide_ids`` is non-empty, validates each id against the
   resolved slide list and exits with a clear message on unknown ids.
4. Calls the supplied ``to_json_fn`` to produce the payload.
5. Writes to ``output_path`` if given, otherwise stdout.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import click
from rich.console import Console

from scrolly.deck.model import Deck
from scrolly.errors import ScrollyError
from scrolly.pipeline import load_deck
from scrolly.slide.ir import SlideIR

_err_console = Console(stderr=True, highlight=False)

ToJsonFn = Callable[[Deck, dict[str, SlideIR], tuple[str, ...] | None], dict]


def run_introspect_command(
    deck_path: Path,
    slide_ids: tuple[str, ...],
    output_path: Path | None,
    *,
    to_json_fn: ToJsonFn,
) -> None:
    """Run an introspect subcommand end-to-end: load → filter → serialize → output.

    Args:
        deck_path: Path to the ``.deck.json`` file.
        slide_ids: Tuple of slide ids to filter to; empty tuple = no filter.
        output_path: Optional file destination; ``None`` writes to stdout.
        to_json_fn: Domain helper that produces the JSON-ready dict.

    Raises:
        SystemExit: Non-zero exit on validation gate failure or unknown
            ``--slide`` ids; the error message goes to stderr.
    """
    try:
        deck, slide_irs = load_deck(deck_path)
    except ScrollyError as e:
        _err_console.print(f"[red]error:[/red] {e}")
        sys.exit(1)

    if slide_ids:
        known = {s.id for s in deck.slides}
        unknown = [sid for sid in slide_ids if sid not in known]
        if unknown:
            _err_console.print(
                f"[red]error:[/red] unknown slide id(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}"
            )
            sys.exit(1)

    payload = to_json_fn(deck, slide_irs, slide_ids or None)
    rendered = json.dumps(payload, indent=2)

    if output_path is not None:
        output_path.write_text(rendered, encoding="utf-8")
    else:
        click.echo(rendered)
