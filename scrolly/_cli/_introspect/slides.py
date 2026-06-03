"""``scrolly introspect slides`` — deck topology view."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect.common import run_introspect_command
from scrolly.deck.introspect import slides_to_json


@click.command(name="slides")
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def slides_command(deck_path: Path, output_path: Path | None) -> None:
    """Deck topology — slides, edges, groups, geometry.

    Returns a deck-wide overview: every slide with its grid coord, title,
    resolved scroll_range, element + snap counts; every edge with
    fully-specified sides; every group with members and color.

    No ``--slide`` filter — the value of this view is the relationships
    between slides, which filtering would destroy.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=(),
        output_path=output_path,
        to_json_fn=slides_to_json,
    )
