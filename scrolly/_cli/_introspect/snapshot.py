"""``scrolly introspect snapshot`` — element substrate properties at given scrolls."""

from __future__ import annotations

from pathlib import Path

import click

from scrolly._cli._introspect.common import run_snapshot_command


@click.command(name="snapshot")
@click.argument("deck_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--slide",
    "slide_id",
    required=True,
    help="Slide id to snapshot. Mandatory and single-valued — scroll positions are slide-local.",
)
@click.option(
    "--scroll",
    "scrolls",
    type=float,
    required=True,
    multiple=True,
    help="Scroll position(s) to snapshot at. Mandatory; repeat for multiple scrolls.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def snapshot_command(
    deck_path: Path,
    slide_id: str,
    scrolls: tuple[float, ...],
    output_path: Path | None,
) -> None:
    """Resolve every element's substrate properties at the given scroll position(s).

    For each ``--scroll N`` the seven substrate properties — ``position``,
    ``width``, ``height``, ``anchor``, ``opacity``, ``scale``, ``angle`` —
    are interpolated to numeric values per element. A ``visible`` flag
    (``opacity > 0``) is derived alongside. Type-specific content
    (image path, markdown text, iframe HTML) is omitted since it
    doesn't change with scroll.

    Scroll positions are validated against the slide's ``scroll_range``:
    negative scrolls or scrolls beyond a numeric ``scroll_range`` reject
    the whole invocation (those scrolls are never physically reachable).
    For ``scroll_range: "auto"`` slides only the lower bound is enforced
    build-side.

    Output format may change before scrolly v1.0 — pin a version when
    caching the schema.
    """
    run_snapshot_command(
        deck_path,
        slide_id=slide_id,
        scrolls=scrolls,
        output_path=output_path,
    )
