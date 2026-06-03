#!/usr/bin/env python3
"""Regenerate the step-element ghost stacks in slide-1 through slide-4.

Each of the six step elements in a slide renders the *full* row stack
in normal block flow with `visibility: hidden` on every row except its
own. The vertical pitch is then a function of the actual rendered
content rather than a hand-baked `padding-top: Nem` ladder, so if any
row's text wraps to multiple lines the visible rows in every other
step element shift identically and stay aligned.

The script rewrites the region between the BEGIN/END sentinel comments
in each slide file (see `SENTINEL_BEGIN` / `SENTINEL_END` below).
Everything outside the sentinels is preserved verbatim, so hand-edits
to the rest of the slide (banner, gitgraph, label, ...) are safe.

Run: `python _gen/build_step_elements.py` (from anywhere — output paths
are resolved relative to this file).
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
DECK_ROOT = HERE.parent
SLIDES_DIR = DECK_ROOT / "slides"

# Visual stack reads top → bottom: step-N visually highest, step-1
# visually lowest. Step-1 appears first; step-N appears last. Each
# list is ordered step-1 → step-N (i.e. visual bottom → top). Slides
# have different step counts and therefore different total timing
# windows — `hold_end` / `fade_out_end` are per-slide so each can
# extend independently without disturbing its neighbor.
SLIDE_1_STEPS: list[str] = [
    "create branch 1",
    "create branch 2",
    "create branch 3",
    "create branch 4",
    "create&nbsp;<code>.git/machete</code>&nbsp;file",
    "<code>git machete github create-pr</code>",
]
SLIDE_1_HOLD_END = 1750
SLIDE_1_FADE_OUT_END = 2300
SLIDE_1_POSITION_Y = 90

SLIDE_2_STEPS: list[str] = [
    "main gets a new commit",
    "<code>git machete traverse</code>",
    "rebase part 1",
    "rebased commit, new hash",
    "original commit, still part of branch 2",
    "rebase part 2",
    "rebase part 3",
    "rebase part 4",
    "4 original commits now fully orphaned",
]
SLIDE_2_HOLD_END = 2350
SLIDE_2_FADE_OUT_END = 2900
SLIDE_2_POSITION_Y = 90

SLIDE_3_STEPS: list[str] = [
    "add tests",
    "copilot fixes",
    "tweaks",
    "downstream branches don't see new upstream commits",
    "<code>git machete traverse</code>",
    "rebase&nbsp;<code>feat/part-2</code>",
    "rebase&nbsp;<code>feat/part-3</code>",
    "rebase&nbsp;<code>feat/part-4</code>",
]
SLIDE_3_HOLD_END = 2150
SLIDE_3_FADE_OUT_END = 2700
SLIDE_3_POSITION_Y = 90

SLIDE_4_STEPS: list[str] = [
    "<code>feat/part-1</code>&nbsp;merged",
    "PR2 retargeted to&nbsp;<code>main</code>",
    "<code>git machete slide-out feat/part-1</code>",
    "<code>git machete traverse</code>",
]
SLIDE_4_HOLD_END = 1350
SLIDE_4_FADE_OUT_END = 1900
SLIDE_4_POSITION_Y = 80

# Inner-wrapper styles. Each row is rendered as a flex container with
# an explicit `min-height` so the row's box size is geometric, not a
# function of which fonts the inline content happens to use. The
# `<code>` row would otherwise produce a slightly (or, in some
# viewport / font combinations, dramatically) taller line-box than its
# sans-serif neighbors and break the visible pitch — a layout
# primitive that owns vertical pitch independently of font metrics
# would be the engine-level version of this same workaround.
# `line-height` on the
# wrapper governs intra-line spacing when a row's text wraps to
# multiple lines; the row then grows past `min-height` naturally and
# every ghost stack picks up the same extra height.
FONT_SIZE_EM = 1.3
# `LINE_HEIGHT` governs wrap pitch (between two visible lines inside one
# wrapped row); `ROW_MIN_HEIGHT_EM` governs inter-row pitch (between
# adjacent rows, when neither wraps). Independent on purpose — a wider
# inter-row pitch reads as "these are distinct steps", while a tighter
# wrap pitch reads as "this is one statement that happens to span two
# visible lines".
LINE_HEIGHT = 1.0         # × FONT_SIZE_EM = 1.30 root-em wrap pitch
ROW_MIN_HEIGHT_EM = 2.25  # × FONT_SIZE_EM = 2.925 root-em inter-row pitch

# Per-element substrate properties. Bottom-left anchored: the *bottom*
# of the step stack stays pinned near the slide's lower edge, so as
# more steps fade in the stack grows visually upward from a fixed
# baseline — natural for the bottom-up reveal order all slides use.
# `POSITION_X` is shared across slides; the y-coordinate is per-slide
# (`SLIDE_N_POSITION_Y` alongside each step list) so each slide can
# choose how high or low its step stack sits relative to whatever
# else lives on that slide.
POSITION_X = 60
ANCHOR = "[0, 100]"
WIDTH = 40
HEIGHT = "auto"

# Per-step appearance timing: step-N starts fading in at
# `400 + 200·N` and finishes 100 later; all steps hold to `hold_end`
# and fade to 0 by `fade_out_end`. These per-slide windows are
# defined alongside each slide's step list above.

SENTINEL_BEGIN = "// === BEGIN GENERATED: step elements ==="
SENTINEL_END = "// === END GENERATED ==="


# ==================================================================================================
#  Element rendering
# ==================================================================================================
def _build_html(step_num: int, steps: list[str]) -> list[str]:
    """Build the inner HTML body for one step element, as source segments.

    The body is a single wrapper div containing one child div per
    row in the visual stack (top → bottom: step-N, step-(N-1), …,
    step-1). All rows except the one this element owns get
    `visibility: hidden` so they occupy layout space without
    rendering — that's what gives every step element an identical
    wrap-aware block-flow layout.

    Args:
        step_num: 1-indexed step number this element owns.
        steps: Ordered list of step strings (step-1 → step-N).

    Returns:
        The markup split into segments — wrapper-open, one per row,
        wrapper-close — so the caller can lay them out one per source
        line via JSON5 `\\`-continuation. Concatenated, the segments
        are exactly the rendered HTML (no extra whitespace).
    """
    # --- compute which row is visible -----------
    visible_index = len(steps) - step_num  # 0-indexed from top of stack

    # --- build the row markup -------------------
    row_style_base = (
        f"display:flex;align-items:center;min-height:{ROW_MIN_HEIGHT_EM}em"
    )
    rows: list[str] = []
    for i, text in enumerate(reversed(steps)):
        if i == visible_index:
            rows.append(f'<div style="{row_style_base}">{text}</div>')
        else:
            rows.append(
                f'<div style="{row_style_base};visibility:hidden">{text}</div>'
            )

    # --- wrap with font + line-height -----------
    wrapper_style = f"font-size:{FONT_SIZE_EM}em;line-height:{LINE_HEIGHT}"
    return [f'<div style="{wrapper_style}">', *rows, "</div>"]


def _opacity_keyframes(step_num: int, hold_end: int, fade_out_end: int) -> str:
    """Return the JSON5 keyframes array for step `step_num`'s opacity."""
    fade_in_start = 400 + step_num * 200
    fade_in_end = fade_in_start + 100
    return (
        f"[[{fade_in_start}, 0], [{fade_in_end}, 1], "
        f"[{hold_end}, 1], [{fade_out_end}, 0]]"
    )


def _step_element(
    step_num: int,
    steps: list[str],
    hold_end: int,
    fade_out_end: int,
    position_y: int,
) -> str:
    """Render one step element as a JSON5 object literal.

    The output is indented to match the surrounding `elements: [`
    block (4-space indent) and ends with a trailing comma so it
    composes with the rest of the array.

    Args:
        step_num: 1-indexed step number.
        steps: Ordered list of step strings (step-1 → step-N).
        hold_end: Scroll position up to which the step stays at
            full opacity after fade-in.
        fade_out_end: Scroll position by which the step has fully
            faded out.
        position_y: Slide-coordinate y-position the bottom-left
            anchor pins to (paired with the shared `POSITION_X`).

    Returns:
        The JSON5 source text for one element, without a trailing
        newline.
    """
    # JSON5 strings escape internal double quotes as `\"`; each markup
    # segment (wrapper-open, one per row, wrapper-close) goes on its own
    # source line, joined by `\`-continuation so the parsed value carries
    # no literal newline or indentation — readable source, identical output.
    segments = [seg.replace('"', r"\"") for seg in _build_html(step_num, steps)]
    html_field = '      html: "' + "\\\n".join(segments) + '",'
    keyframes = _opacity_keyframes(step_num, hold_end, fade_out_end)
    return (
        f"    {{\n"
        f'      name: "step-{step_num}",\n'
        f"{html_field}\n"
        f"      position: [{POSITION_X}, {position_y}], anchor: {ANCHOR},\n"
        f'      width: {WIDTH}, height: "{HEIGHT}",\n'
        f"      opacity: {{ keyframes: {keyframes} }},\n"
        f"    }},"
    )


def _generate_block(
    steps: list[str],
    hold_end: int,
    fade_out_end: int,
    position_y: int,
) -> str:
    """Render all N step elements as one JSON5 block (no surrounding lines)."""
    return "\n".join(
        _step_element(n, steps, hold_end, fade_out_end, position_y)
        for n in range(1, len(steps) + 1)
    )


# ==================================================================================================
#  Sentinel-based file patching
# ==================================================================================================
def _patch_slide(
    path: Path,
    steps: list[str],
    hold_end: int,
    fade_out_end: int,
    position_y: int,
) -> None:
    """Replace the region between BEGIN/END sentinels in a slide file.

    Reads `path`, locates the first occurrence of `SENTINEL_BEGIN`
    and the next occurrence of `SENTINEL_END` after it, and swaps
    everything between the two sentinel lines (exclusive of the
    sentinel lines themselves) for a freshly generated step block.
    The sentinel lines and the surrounding content are preserved
    byte-for-byte.

    Args:
        path: Path to the slide `.slide.json` file to patch.
        steps: Ordered list of step strings (step-1 → step-N).
        hold_end: Scroll position up to which each step stays at
            full opacity after fade-in.
        fade_out_end: Scroll position by which each step has fully
            faded out.
        position_y: Slide-coordinate y-position the bottom-left
            anchor pins to.

    Raises:
        SystemExit: If either sentinel is missing from the file.
    """
    text = path.read_text()
    if SENTINEL_BEGIN not in text or SENTINEL_END not in text:
        raise SystemExit(
            f"missing BEGIN/END sentinels in {path}; "
            f"add `{SENTINEL_BEGIN}` and `{SENTINEL_END}` lines around "
            f"the steps block before running this script."
        )
    begin = text.index(SENTINEL_BEGIN)
    end = text.index(SENTINEL_END, begin)
    begin_line_end = text.index("\n", begin) + 1
    end_line_start = text.rfind("\n", 0, end) + 1
    new_block = (
        _generate_block(steps, hold_end, fade_out_end, position_y) + "\n"
    )
    path.write_text(text[:begin_line_end] + new_block + text[end_line_start:])
    print(f"patched {path.relative_to(DECK_ROOT.parent.parent)}")


def main() -> None:
    """Regenerate the step blocks in slide-{1,2,3,4}.slide.json."""
    _patch_slide(
        SLIDES_DIR / "slide-1.slide.json",
        SLIDE_1_STEPS,
        SLIDE_1_HOLD_END,
        SLIDE_1_FADE_OUT_END,
        SLIDE_1_POSITION_Y,
    )
    _patch_slide(
        SLIDES_DIR / "slide-2.slide.json",
        SLIDE_2_STEPS,
        SLIDE_2_HOLD_END,
        SLIDE_2_FADE_OUT_END,
        SLIDE_2_POSITION_Y,
    )
    _patch_slide(
        SLIDES_DIR / "slide-3.slide.json",
        SLIDE_3_STEPS,
        SLIDE_3_HOLD_END,
        SLIDE_3_FADE_OUT_END,
        SLIDE_3_POSITION_Y,
    )
    _patch_slide(
        SLIDES_DIR / "slide-4.slide.json",
        SLIDE_4_STEPS,
        SLIDE_4_HOLD_END,
        SLIDE_4_FADE_OUT_END,
        SLIDE_4_POSITION_Y,
    )


if __name__ == "__main__":
    main()
