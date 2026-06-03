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
from collections.abc import Callable
from pathlib import Path

import click

from scrolly._cli.console import error_exit
from scrolly.deck.model import Deck
from scrolly.errors import ScrollyError
from scrolly.pipeline import load_deck
from scrolly.slide.ir import SlideIR

ToJsonFn = Callable[[Deck, dict[str, SlideIR], tuple[str, ...] | None], dict]


def _load_deck_or_exit(deck_path: Path) -> tuple[Deck, dict[str, SlideIR]]:
    """Load and validate a deck, or print the error to stderr and exit non-zero."""
    try:
        return load_deck(deck_path)
    except ScrollyError as e:
        error_exit(str(e))


def _emit_json(payload: dict, output_path: Path | None) -> None:
    """Write an indented JSON payload to ``output_path``, or stdout when ``None``."""
    rendered = json.dumps(payload, indent=2)
    if output_path is not None:
        output_path.write_text(rendered, encoding="utf-8")
    else:
        click.echo(rendered)


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
    deck, slide_irs = _load_deck_or_exit(deck_path)

    if slide_ids:
        known = {s.id for s in deck.slides}
        unknown = [sid for sid in slide_ids if sid not in known]
        if unknown:
            error_exit(f"unknown slide id(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}")

    payload = to_json_fn(deck, slide_irs, slide_ids or None)
    _emit_json(payload, output_path)


def run_snapshot_command(
    deck_path: Path,
    slide_id: str,
    scrolls: tuple[float, ...],
    output_path: Path | None,
) -> None:
    """Run the snapshot subcommand: load → validate slide_id + scrolls → snapshot → output.

    Snapshot differs from the other introspect commands in two ways:
    ``--slide`` is mandatory and single-valued (scroll positions are
    slide-local, so multi-slide queries are ambiguous), and ``--scroll N``
    is mandatory and repeatable. This helper enforces both invariants
    plus the per-slide scroll-range validation: any ``--scroll`` outside
    ``[0, scroll_range]`` for numeric ``scroll_range``, or below 0 for
    ``"auto"`` slides, rejects the whole invocation with a clear message
    rather than silently clamping or extrapolating beyond what the
    browser can physically reach.

    Args:
        deck_path: Path to the ``.deck.json`` file.
        slide_id: Slide to snapshot (mandatory, single).
        scrolls: Tuple of scroll positions (mandatory, non-empty).
        output_path: Optional file destination; ``None`` writes to stdout.

    Raises:
        SystemExit: Non-zero exit on validation gate failure, unknown
            ``slide_id``, or any out-of-range scroll value.
    """
    from scrolly.slide.introspect import snapshot_to_json

    deck, slide_irs = _load_deck_or_exit(deck_path)

    known = {s.id for s in deck.slides}
    if slide_id not in known:
        error_exit(f"unknown slide id: '{slide_id}'. Known: {', '.join(sorted(known))}")

    ir = slide_irs[slide_id]
    scroll_range = ir.scroll_range
    invalid: list[tuple[float, str]] = []
    for scroll in scrolls:
        if scroll < 0:
            invalid.append((scroll, "negative scroll values are never reachable"))
        elif isinstance(scroll_range, (int, float)) and scroll > scroll_range:
            invalid.append((scroll, f"exceeds slide's scroll_range ({scroll_range})"))
    if invalid:
        lines = "\n".join(f"  scroll={s}: {reason}" for s, reason in invalid)
        error_exit(f"--scroll out-of-range for slide '{slide_id}':\n{lines}")

    payload = snapshot_to_json(deck, slide_irs, slide_id, scrolls)
    _emit_json(payload, output_path)
