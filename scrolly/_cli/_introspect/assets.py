"""``scrolly introspect assets`` — per-asset metadata + slide references."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect.common import run_introspect_command
from scrolly.pipeline.introspect import assets_to_json


@click.command(name="assets")
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--slide",
    "slide_ids",
    multiple=True,
    help="Restrict the asset walk to elements within the named slide(s). Repeatable.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def assets_command(deck_path: Path, slide_ids: tuple[str, ...], output_path: Path | None) -> None:
    """Asset table — declared assets, per-slide references, byte sizes, mime types.

    Walks the resolved slide IRs for ``ImageElement`` / ``ImageSequenceElement``
    references. Each entry reports absolute path, name, size, mime, exists
    flag, and the slides that reference it.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_introspect_command(
        deck_path,
        slide_ids=slide_ids,
        output_path=output_path,
        to_json_fn=assets_to_json,
    )
