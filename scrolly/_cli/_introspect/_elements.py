"""``scrolly introspect elements`` — fully-resolved per-slide element tree."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect._common import run_introspect_command
from scrolly.slide.introspect import element_tree_to_json


@click.command(name="elements")
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
def elements_command(deck_path: Path, slide_ids: tuple[str, ...], output_path: Path | None) -> None:
    """Fully-resolved element tree per slide.

    Defaults are filled in, ``*_file`` fields are inlined, asset paths
    are absolute. Animated properties surface as their keyframe lists;
    static properties surface as their values.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=slide_ids,
        output_path=output_path,
        to_json_fn=element_tree_to_json,
    )
