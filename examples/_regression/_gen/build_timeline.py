"""Generate the vertical SVG timeline used by the `contributions` slide.

A ~600x2800 SVG visualizing the timeline of CVE-2024-3094 — the xz utils
backdoor, from Jan 2021 to March 29 2024. The slide containing this SVG
pans through it via animated ``anchor`` keyframes; reader scrolls = walk
through the timeline.

Stdlib-only; deterministic output. Re-run after editing ``EVENTS``.

Run from repo root:
    uv run python examples/_regression/_gen/build_timeline.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path


# --- layout constants -------------------------------
WIDTH = 600
HEIGHT = 2800
SPINE_X = 290
TOP_MARGIN = 120
BOTTOM_MARGIN = 100

# --- time axis: piecewise-linear -------------------
# Jan 2021 -> Jan 2024 maps linearly into the upper portion of the SVG;
# Jan 2024 -> Mar 29 2024 gets stretched into the lower portion so the
# four events clustered in that 3-month window (Feb 24, Mar 9, Mar 28,
# Mar 29) have enough vertical room not to overlap.
#
# Each (date, y) anchor below is a fixed mapping point; intermediate
# dates are linearly interpolated within their segment.
START = dt.date(2021, 1, 1)
END = dt.date(2024, 3, 30)
_TIME_ANCHORS: list[tuple[dt.date, float]] = [
    (dt.date(2021, 1, 1), 120.0),
    (dt.date(2024, 1, 1), 1850.0),  # 3 years -> upper ~63% of canvas
    (dt.date(2024, 3, 1), 2200.0),  # Feb 2024 events get room
    (dt.date(2024, 3, 28), 2500.0),  # Mar 9 fits between
    (dt.date(2024, 3, 29), 2620.0),  # 120 px gap for the 1-day Mar28→Mar29
    (dt.date(2024, 3, 30), 2700.0),
]

# Events along the timeline. side="L" places callout left of spine,
# side="R" places right. importance="major" gets a larger marker + font.
EVENTS: list[tuple[dt.date, list[str], str, str]] = [
    (dt.date(2021, 1, 15), ["Jia Tan begins contributing", "to xz utils"], "R", "minor"),
    (dt.date(2021, 7, 1), ["First patches accepted"], "L", "minor"),
    (dt.date(2022, 4, 22), ["First push on xz-devel:", '"add a co-maintainer"'], "L", "minor"),
    (dt.date(2022, 6, 27), ["Sustained pressure from", '"Jigar Kumar", "Dennis Ens"'], "R", "minor"),
    (dt.date(2023, 1, 7), ["Jia Tan gains commit access"], "R", "major"),
    (dt.date(2023, 3, 1), ["Becomes effective co-maintainer"], "L", "minor"),
    (dt.date(2023, 7, 1), ["Routine maintenance"], "L", "minor"),
    (dt.date(2024, 2, 24), ["xz 5.6.0 released —", "contains payload"], "R", "major"),
    (dt.date(2024, 3, 9), ["xz 5.6.1 —", '"valgrind fix"'], "L", "minor"),
    (dt.date(2024, 3, 28), ["Andres Freund notices", "500 ms SSH anomaly"], "R", "major"),
    (dt.date(2024, 3, 29), ["CVE-2024-3094 disclosed", "Packages pulled within hours"], "L", "major"),
]


def main() -> None:
    """Write the timeline SVG next to the slide files."""
    out_path = Path(__file__).parent.parent / "timeline.svg"
    svg = build_svg()
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path} ({len(svg)} bytes)")


def build_svg() -> str:
    """Build the complete SVG document as a string.

    Returns:
        Full SVG markup including header, defs, and all visual elements.
    """
    parts: list[str] = []
    parts.append(_header())
    parts.append(_gradient_defs())
    parts.append(_background())
    parts.append(_spine())
    parts.extend(_year_labels())
    parts.extend(_event_markers())
    parts.append(_footer())
    return "\n".join(parts)


def y_for(date: dt.date) -> float:
    """Map a date to a y coordinate on the timeline.

    Piecewise-linear between the anchors in ``_TIME_ANCHORS`` — lets
    us stretch the dense Feb–Mar 2024 window without affecting the
    compressed 2021–2023 portion.

    Args:
        date: Date within ``[START, END]``.

    Returns:
        y coordinate (px) in the SVG coordinate space.
    """
    for (d0, y0), (d1, y1) in zip(_TIME_ANCHORS, _TIME_ANCHORS[1:]):
        if d0 <= date <= d1:
            span_days = (d1 - d0).days
            elapsed = (date - d0).days
            return y0 + (elapsed / span_days) * (y1 - y0)
    # Fall through: clamp to nearest endpoint.
    if date < _TIME_ANCHORS[0][0]:
        return _TIME_ANCHORS[0][1]
    return _TIME_ANCHORS[-1][1]


def _header() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="Helvetica, Arial, sans-serif">'
    )


def _gradient_defs() -> str:
    """Vertical gradient on the spine: neutral -> warm -> red -> green.

    Uses ``gradientUnits="userSpaceOnUse"`` with absolute coordinates so
    the gradient renders reliably along a thin stroked line — the
    default ``objectBoundingBox`` units handle stroke bounding boxes
    inconsistently across renderers.
    """
    transitions = [
        (START, "#7a8a9a"),
        (dt.date(2022, 4, 22), "#7a8a9a"),
        (dt.date(2022, 6, 30), "#d68910"),
        (dt.date(2024, 2, 24), "#d68910"),
        (dt.date(2024, 3, 1), "#c0392b"),
        (dt.date(2024, 3, 29), "#c0392b"),
        (dt.date(2024, 3, 30), "#27ae60"),
        (END, "#27ae60"),
    ]
    y_top = y_for(START)
    y_bot = y_for(END)
    range_pixels = y_bot - y_top
    stops: list[str] = []
    for date, color in transitions:
        y = y_for(date)
        offset = (y - y_top) / range_pixels * 100
        stops.append(f'<stop offset="{offset:.2f}%" stop-color="{color}"/>')
    return (
        "<defs>"
        f'<linearGradient id="spineGrad" gradientUnits="userSpaceOnUse" '
        f'x1="{SPINE_X}" y1="{y_top}" x2="{SPINE_X}" y2="{y_bot}">'
        + "".join(stops)
        + "</linearGradient>"
        "</defs>"
    )


def _background() -> str:
    return f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f7f8fa"/>'


def _spine() -> str:
    """Vertical spine running through every event marker.

    Rendered as a thin rect (not a line) — the gradient applies via
    fill, which is more reliably handled by browsers than a stroked
    gradient on a long thin line.
    """
    y_top = y_for(START)
    y_bot = y_for(END)
    spine_width = 6
    return (
        f'<rect x="{SPINE_X - spine_width / 2}" y="{y_top}" '
        f'width="{spine_width}" height="{y_bot - y_top}" '
        f'rx="{spine_width / 2}" '
        'fill="url(#spineGrad)"/>'
    )


def _year_labels() -> list[str]:
    """Large year labels in the left margin at each January 1."""
    parts: list[str] = []
    for year in (2021, 2022, 2023, 2024):
        y = y_for(dt.date(year, 1, 1))
        parts.append(
            f'<text x="40" y="{y + 12}" font-size="36" font-weight="bold" '
            f'fill="#5a6675">{year}</text>'
        )
    return parts


def _event_markers() -> list[str]:
    """Per-event marker on the spine + date pill + label lines on chosen side."""
    parts: list[str] = []
    for date, lines, side, importance in EVENTS:
        y = y_for(date)
        radius = 14 if importance == "major" else 7
        marker_color = "#2c3e50" if importance == "major" else "#5a6675"
        font_size = 18 if importance == "major" else 14
        text_color = "#2c3e50" if importance == "major" else "#5a6675"

        # Marker on the spine
        parts.append(
            f'<circle cx="{SPINE_X}" cy="{y}" r="{radius}" '
            f'fill="white" stroke="{marker_color}" stroke-width="3"/>'
        )

        # Callout positioning
        if side == "L":
            text_x = SPINE_X - radius - 18
            anchor = "end"
        else:
            text_x = SPINE_X + radius + 18
            anchor = "start"

        # Date pill (small, above first label line)
        parts.append(
            f'<text x="{text_x}" y="{y - 10}" font-size="13" font-weight="bold" '
            f'fill="{marker_color}" text-anchor="{anchor}">{date.strftime("%b %-d, %Y")}</text>'
        )

        # Label lines (one or two per event)
        for i, line in enumerate(lines):
            line_y = y + 10 + i * (font_size + 4)
            parts.append(
                f'<text x="{text_x}" y="{line_y}" font-size="{font_size}" '
                f'fill="{text_color}" text-anchor="{anchor}">{_escape(line)}</text>'
            )
    return parts


def _escape(s: str) -> str:
    """Escape XML special characters in text content."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _footer() -> str:
    return "</svg>"


if __name__ == "__main__":
    main()
