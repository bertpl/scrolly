"""CLI entry point for the animation engine.

Subcommands (driven by ``scripts/make_animation.sh``):

- ``deck-path``  — print the deck directory the recipe targets (lets the
  shell build it without parsing JSON5).
- ``capture``    — stage 1: screenshot raw frames to the work dir.
- ``composite``  — stage 2: paint overlays + assemble the animation.
- ``all``        — capture then composite.

Run as ``python -m animation_engine <subcommand>`` with ``docs/_gen`` on
``PYTHONPATH``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .plan import build_frame_plan
from .recipe import load_recipe


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to a stage.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    args = _build_parser().parse_args(argv)
    recipe = load_recipe(args.recipe)

    if args.command == "deck-path":
        print(recipe.deck)
        return 0

    plan = build_frame_plan(recipe)
    work = Path(args.work)
    frames_dir = work / "frames"

    if args.command in ("capture", "all"):
        from .capture import run_capture

        n = run_capture(recipe, plan, Path(args.deck_html), frames_dir)
        print(f"captured {n} frames to {frames_dir}")
    if args.command in ("composite", "all"):
        from .composite import run_composite

        out = run_composite(recipe, plan, frames_dir, work)
        print(f"wrote {out}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="animation_engine", description="Recipe-driven deck animation engine.")
    sub = parser.add_subparsers(dest="command", required=True)

    deck = sub.add_parser("deck-path", help="print the deck directory the recipe targets")
    deck.add_argument("--recipe", required=True)

    cap = sub.add_parser("capture", help="stage 1: screenshot raw frames")
    cap.add_argument("--recipe", required=True)
    cap.add_argument("--deck-html", required=True, help="path to the built deck's index.html")
    cap.add_argument("--work", required=True, help="work directory (frame cache lives here)")

    comp = sub.add_parser("composite", help="stage 2: paint overlays + assemble")
    comp.add_argument("--recipe", required=True)
    comp.add_argument("--work", required=True)

    full = sub.add_parser("all", help="capture then composite")
    full.add_argument("--recipe", required=True)
    full.add_argument("--deck-html", required=True)
    full.add_argument("--work", required=True)

    return parser


if __name__ == "__main__":
    sys.exit(main())
