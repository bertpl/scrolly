"""Generate the layered ``trojan-*.svg`` assets for the ``build-trojan`` slide.

The build-trojan slide demonstrates ``image_sequence`` ``incremental``
compositing: four transparent layers, each drawing one stage of the
autoconf-trojan assembly, stack up into a single left-to-right flow diagram
as the reader scrolls.

Each emitted SVG shares the same viewBox and draws only *its* stage's box
(plus the arrow feeding into it), leaving the rest transparent — so
incremental stacking accumulates them into the complete diagram.

Stdlib-only; deterministic output. Re-run after editing ``STAGES``.

Run from repo root:
    uv run python examples/_regression/_gen/build_trojan_layers.py
"""

from __future__ import annotations

from pathlib import Path

# Canvas + box geometry, in viewBox user units.
VIEW_W, VIEW_H = 920, 240
BOX_W, BOX_H = 180, 104
BOX_Y = (VIEW_H - BOX_H) / 2
GAP = (VIEW_W - 4 * BOX_W) / 5  # equal outer margins and inter-box gaps

# Four assembly stages: (title, subtitle, fill, stroke, text-color).
STAGES = [
    ("test files", "disguised payload bytes", "#f3e3e3", "#7a4c4c", "#5a2c2c"),
    ("build-to-host.m4", "decodes at ./configure", "#f3e3e3", "#7a4c4c", "#5a2c2c"),
    ("inject", "into the liblzma build", "#f3e3e3", "#7a4c4c", "#5a2c2c"),
    ("liblzma.so", "backdoored — IFUNC hook", "#c0392b", "#7a1f1f", "#ffffff"),
]


def _box_x(i: int) -> float:
    """Return the left-edge x of box ``i`` (0-based)."""
    return GAP + i * (BOX_W + GAP)


def _box_svg(i: int) -> str:
    """Render the rounded-rect box plus its two text labels for stage ``i``."""
    title, subtitle, fill, stroke, text = STAGES[i]
    cx = _box_x(i) + BOX_W / 2
    return (
        f'<rect x="{_box_x(i):.1f}" y="{BOX_Y:.1f}" width="{BOX_W}" height="{BOX_H}" '
        f'rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{cx:.1f}" y="{BOX_Y + 44:.1f}" text-anchor="middle" '
        f'font-family="-apple-system, sans-serif" font-size="21" font-weight="700" '
        f'fill="{text}">{title}</text>'
        f'<text x="{cx:.1f}" y="{BOX_Y + 70:.1f}" text-anchor="middle" '
        f'font-family="-apple-system, sans-serif" font-size="14" fill="{text}">{subtitle}</text>'
    )


def _arrow_svg(i: int) -> str:
    """Render the arrow feeding into box ``i`` from box ``i - 1``."""
    x_from = _box_x(i - 1) + BOX_W
    x_to = _box_x(i)
    y = VIEW_H / 2
    return (
        f'<line x1="{x_from:.1f}" y1="{y:.1f}" x2="{x_to - 9:.1f}" y2="{y:.1f}" '
        f'stroke="#7a4c4c" stroke-width="3"/>'
        f'<path d="M {x_to - 12:.1f} {y - 7:.1f} L {x_to:.1f} {y:.1f} '
        f'L {x_to - 12:.1f} {y + 7:.1f} Z" fill="#7a4c4c"/>'
    )


def _layer_svg(i: int) -> str:
    """Build the full transparent SVG for layer ``i`` (its box plus incoming arrow)."""
    body = (_arrow_svg(i) if i > 0 else "") + _box_svg(i)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}">{body}</svg>\n'


def main() -> None:
    """Emit ``trojan-1.svg`` … ``trojan-4.svg`` into the deck root."""
    out_dir = Path(__file__).resolve().parent.parent
    for i in range(len(STAGES)):
        path = out_dir / f"trojan-{i + 1}.svg"
        path.write_text(_layer_svg(i), encoding="utf-8")
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
