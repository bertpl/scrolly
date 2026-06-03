"""``scrolly introspect snaps`` — per-slide snap positions (author + derived)."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect.common import run_introspect_command
from scrolly.slide.introspect import snaps_to_json


@click.command(name="snaps")
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--slide",
    "slide_ids",
    multiple=True,
    help="Restrict output to the named slide id(s). Repeatable. Default = all slides.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def snaps_command(deck_path: Path, slide_ids: tuple[str, ...], output_path: Path | None) -> None:
    """Per-slide snap positions: author-supplied + element-derived (image_sequence hold-centers).

    Author entries come from each slide's ``snap_positions`` field;
    derived entries come from ``ImageSequenceElement`` hold-centers
    (one per frame). The ``merged`` list is the deduplicated + sorted
    union — what the canvas runtime actually uses.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=slide_ids,
        output_path=output_path,
        to_json_fn=snaps_to_json,
    )
