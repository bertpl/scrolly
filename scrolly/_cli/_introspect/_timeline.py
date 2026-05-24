"""``scrolly introspect timeline`` — per-element scroll timeline."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect._common import run_introspect_command
from scrolly.slide.introspect import timeline_to_json


@click.command(name="timeline")
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
def timeline_command(deck_path: Path, slide_ids: tuple[str, ...], output_path: Path | None) -> None:
    """Per-element scroll timeline: animated keyframes + visibility intervals.

    ``animated_properties`` lists only the substrate properties that are
    actually animated (statics are omitted to avoid redundancy with
    ``introspect elements``). ``visibility_intervals`` reports scroll
    ranges where ``opacity > 0`` — half-open at the boundaries; the
    upper bound is ``null`` for ``scroll_range: "auto"`` slides where
    the browser determines the actual extent at runtime.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=slide_ids,
        output_path=output_path,
        to_json_fn=timeline_to_json,
    )
