"""``scrolly introspect dom`` — rendered HTML + scoped CSS per element."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect.common import run_introspect_command
from scrolly.slide.introspect import dom_to_json


@click.command(name="dom")
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--slide",
    "slide_ids",
    multiple=True,
    help=(
        "Restrict output to the named slide id(s). Repeatable. Default = all slides — "
        "but unfiltered output can be hundreds of KB; the filter is almost mandatory in practice."
    ),
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def dom_command(deck_path: Path, slide_ids: tuple[str, ...], output_path: Path | None) -> None:
    """Rendered HTML + scoped CSS per element, sans deck-level chrome.

    Answers "what does my config actually become" by running each
    slide's element renderers and surfacing the per-element pieces —
    HTML fragment and CSS rules — directly. No canvas runtime, no
    scrollbar, no edge geometry, no inter-slide chrome.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=slide_ids,
        output_path=output_path,
        to_json_fn=dom_to_json,
    )
