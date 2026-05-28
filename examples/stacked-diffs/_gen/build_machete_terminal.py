#!/usr/bin/env python3
"""Regenerate the macOS-style terminal SVG for the stacked-diffs deck.

The deck uses a single SVG mock of a macOS terminal session showing
`cat .git/machete` and its tree-shaped output. The base SVG is produced
by charmbracelet/freeze (`brew install charmbracelet/tap/freeze`).
Freeze renders a dark dracula-themed window with traffic-light controls
and a rounded outer corner, but has no per-corner radius or chrome-color
knob; this script post-processes the freeze output to:

- Inject a darker chrome path (`#16171f`, height 24) with rounded top
  corners and sharp bottom corners, so the title-bar background
  contrasts with the body (`#282a36`, dracula default) and the bottom
  edge of the chrome is a clean straight line against the body.
- The chrome height (24) is chosen so freeze's traffic-light circles
  (cy=12, r=5.5) sit vertically centred within it.

Run: `python _gen/build_machete_terminal.py` (from the deck root, or
anywhere — output path is resolved relative to this file).

Requires: `freeze` on PATH.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent

# One entry per terminal screenshot to emit. Each terminal is rendered
# at the same line count (padded with trailing blank lines as needed)
# so freeze produces matching SVG dimensions and the deck can swap
# between them without the image-sequence box rescaling.
TERMINALS: list[tuple[str, str]] = [
    (
        "machete-terminal.svg",
        """\
$ cat .git/machete
main
  feat/part-1
    feat/part-2
      feat/part-3
        feat/part-4
""",
    ),
    (
        "machete-terminal-after-slide-out.svg",
        # After `git machete slide-out --delete feat/part-1`: feat/part-1
        # is gone from the tree, its children reparented onto `main`.
        # Trailing blank line pads to 6 lines so the rendered SVG height
        # matches the pre-slide-out snapshot. Trailing whitespace on the
        # deepest line pads to the same 19-character width as the
        # pre-slide-out's deepest line ("        feat/part-4"), so the
        # rendered SVG width matches too (freeze auto-fits to the
        # longest line).
        """\
$ cat .git/machete
main
  feat/part-2
    feat/part-3
      feat/part-4

""",
    ),
]

FREEZE_THEME = "dracula"
FREEZE_BORDER_RADIUS = 8
# Fixed render width (SVG user units / pixels). Wider than the deepest
# pre-slide-out line ("        feat/part-4", auto-fits to ~227) so
# both pre and post-slide-out terminals render at identical dimensions
# regardless of how deep their deepest line is.
FREEZE_WIDTH = 240

CHROME_HEIGHT = 24.0
CHROME_RADIUS = 8.0
CHROME_FILL = "#16171f"


def _run_freeze(input_path: Path, output_path: Path) -> None:
    """Render the terminal text to an SVG via the freeze CLI.

    Args:
        input_path: Plain-text file containing the literal terminal
            session (prompt + output) freeze should typeset.
        output_path: Destination .svg path freeze writes to.

    Raises:
        SystemExit: If the `freeze` binary is not on PATH.
        subprocess.CalledProcessError: If freeze itself exits non-zero.
    """
    if shutil.which("freeze") is None:
        raise SystemExit(
            "freeze CLI not found on PATH. "
            "Install with: brew install charmbracelet/tap/freeze"
        )
    subprocess.run(
        [
            "freeze",
            str(input_path),
            "--window",
            "--theme",
            FREEZE_THEME,
            "--border.radius",
            str(FREEZE_BORDER_RADIUS),
            "-W",
            str(FREEZE_WIDTH),
            "-o",
            str(output_path),
        ],
        check=True,
    )


def _chrome_path_d(width: float) -> str:
    """SVG path `d` for the chrome shape: rounded top, sharp bottom.

    Args:
        width: Width of the chrome rect in SVG user units (matches the
            freeze canvas width so the chrome spans edge-to-edge).

    Returns:
        The `d` attribute string describing a rect with `CHROME_RADIUS`-
        rounded top-left and top-right corners and unrounded bottom
        corners.
    """
    r = CHROME_RADIUS
    h = CHROME_HEIGHT
    return (
        f"M {r} 0 "
        f"L {width - r} 0 "
        f"A {r} {r} 0 0 1 {width} {r} "
        f"L {width} {h} "
        f"L 0 {h} "
        f"L 0 {r} "
        f"A {r} {r} 0 0 1 {r} 0 Z"
    )


_BG_RECT_RE = re.compile(
    r'<rect width="(?P<w>[\d.]+)" height="[\d.]+" fill="[^"]+" '
    r'rx="[\d.]+" ry="[\d.]+" x="[\d.]+px" y="[\d.]+px"/>'
)


def _patch_chrome(svg_text: str) -> str:
    """Inject the chrome path immediately after freeze's background rect.

    Args:
        svg_text: Raw SVG markup as written by freeze.

    Returns:
        The SVG with one new `<path>` element added between the
        background rect and the rest of the document.

    Raises:
        SystemExit: If freeze's background rect cannot be located by the
            expected regex (typically a sign that freeze's output schema
            shifted and the script needs updating).
    """
    match = _BG_RECT_RE.search(svg_text)
    if not match:
        raise SystemExit(
            "could not find freeze background rect — freeze output may "
            "have changed; update _BG_RECT_RE."
        )
    width = float(match.group("w"))
    chrome = f'<path d="{_chrome_path_d(width)}" fill="{CHROME_FILL}"/>'
    return svg_text[: match.end()] + "\n" + chrome + svg_text[match.end() :]


def main() -> None:
    """Render each terminal-mock SVG in `TERMINALS` and write to the deck."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        terminal_txt = tmp / "terminal.txt"
        freeze_svg = tmp / "terminal.svg"
        for filename, content in TERMINALS:
            terminal_txt.write_text(content)
            _run_freeze(terminal_txt, freeze_svg)
            patched = _patch_chrome(freeze_svg.read_text())
            out_svg = OUT_DIR / filename
            out_svg.write_text(patched)
            print(f"wrote {out_svg.relative_to(OUT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
