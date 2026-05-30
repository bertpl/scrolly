"""Color utilities for rendering: luminance and legible-text-color picks."""

from __future__ import annotations

import re

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse a ``#RGB`` or ``#RRGGBB`` string into 0-255 ``(r, g, b)`` bytes.

    Args:
        hex_color: A ``#RGB`` or ``#RRGGBB`` hex color string.

    Returns:
        The ``(r, g, b)`` byte triple.

    Raises:
        ValueError: If ``hex_color`` is not a ``#RGB`` or ``#RRGGBB`` color.
    """
    if not _HEX_COLOR_RE.match(hex_color):
        raise ValueError(f"not a #RGB or #RRGGBB color: {hex_color!r}")
    digits = hex_color[1:]
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _srgb_to_linear(channel: int) -> float:
    """Linearize one sRGB 0-255 channel to its 0-1 linear-light value."""
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute the WCAG relative luminance of a hex color.

    Args:
        hex_color: A ``#RGB`` or ``#RRGGBB`` hex color string.

    Returns:
        Relative luminance in ``[0, 1]`` (sRGB channels linearized and weighted
        per WCAG 2.x).
    """
    r, g, b = _hex_to_rgb(hex_color)
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def legible_text_color(background: str) -> str:
    """Pick black or white for the most legible text on a background color.

    Chooses whichever of black or white yields the higher WCAG contrast ratio
    against ``background``. The crossover sits at luminance ≈ 0.179, so light
    and mid-tone backgrounds get black and only genuinely dark ones get white.

    Args:
        background: A ``#RGB`` or ``#RRGGBB`` background color string.

    Returns:
        ``"#000000"`` or ``"#ffffff"``.
    """
    luminance = relative_luminance(background)
    contrast_black = (luminance + 0.05) / 0.05
    contrast_white = 1.05 / (luminance + 0.05)
    return "#000000" if contrast_black >= contrast_white else "#ffffff"
