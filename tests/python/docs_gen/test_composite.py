"""Unit tests for the compositor's border + progress-bar chrome.

The chrome extends the canvas (it never overwrites captured frame content):
the progress bar is added under the frame, then the border around the whole.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")  # composite draws with Pillow (optional `capture` dep)

from animation_engine.composite import _add_chrome, _downscale, _frame_width  # noqa: E402
from animation_engine.recipe import Border, Gif, Output, ProgressBar, Recipe, Viewport  # noqa: E402
from PIL import Image  # noqa: E402


def _recipe(border: Border = Border(), progress_bar: ProgressBar = ProgressBar()) -> Recipe:
    """A Recipe carrying just the chrome config (other fields unused by `_add_chrome`)."""
    return Recipe(
        deck="d",
        viewport=Viewport(width=10, height=10, scale=1, output_scale=1),
        fps=1,
        output=Output(gif=Gif(path="o.gif")),
        steps=(),
        overlays=(),
        border=border,
        progress_bar=progress_bar,
    )


def _frame(w: int = 100, h: int = 60) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 255))


# ==================================================================================================
#  Supersample downscale
# ==================================================================================================
def test_downscale_resamples_by_output_over_capture() -> None:
    # --- act --------------------------
    out = _downscale(_frame(200, 100), scale=2, output_scale=1.0)

    # --- assert -----------------------
    assert out.size == (100, 50)  # 2x capture -> 1x delivery


def test_frame_width_reads_pixel_width(tmp_path) -> None:
    # --- arrange ----------------------
    path = tmp_path / "frame-00000.png"
    _frame(321, 240).save(path)

    # --- act / assert -----------------
    assert _frame_width(str(path)) == 321


# ==================================================================================================
#  Border + progress-bar chrome
# ==================================================================================================
def test_no_chrome_keeps_frame_size() -> None:
    # --- act --------------------------
    out = _add_chrome(_frame(100, 60), _recipe(), index=0, total=10)

    # --- assert -----------------------
    assert out.size == (100, 60)


def test_border_expands_all_sides_with_border_color() -> None:
    # --- act --------------------------
    out = _add_chrome(_frame(100, 60), _recipe(border=Border(width=4, color="#ff0000")), index=0, total=10)

    # --- assert -----------------------
    assert out.size == (108, 68)  # +2*4 on each axis
    assert out.getpixel((0, 0)) == (255, 0, 0, 255)  # corner is border color


def test_progress_bar_adds_bottom_strip_with_fill_and_track() -> None:
    # --- arrange ----------------------
    bar = ProgressBar(height=5, color="#00ff00", track_color="#0000ff")

    # --- act --------------------------
    out = _add_chrome(_frame(100, 60), _recipe(progress_bar=bar), index=4, total=10)

    # --- assert -----------------------
    assert out.size == (100, 65)  # +5 height only, width unchanged
    fill_w = round(100 * (4 + 1) / 10)  # 50
    assert out.getpixel((fill_w - 1, 62)) == (0, 255, 0, 255)  # elapsed -> fill color
    assert out.getpixel((fill_w + 1, 62)) == (0, 0, 255, 255)  # remainder -> track color


def test_last_frame_fills_bar_fully() -> None:
    # --- act --------------------------
    out = _add_chrome(
        _frame(100, 60),
        _recipe(progress_bar=ProgressBar(height=4, color="#00ff00", track_color="#0000ff")),
        index=9,
        total=10,
    )

    # --- assert -----------------------
    assert out.getpixel((99, 62)) == (0, 255, 0, 255)  # rightmost bar pixel filled


def test_bar_then_border_compose_order() -> None:
    # --- act --------------------------
    out = _add_chrome(
        _frame(100, 60),
        _recipe(
            border=Border(width=3, color="#111111"),
            progress_bar=ProgressBar(height=4, color="#222222", track_color="#333333"),
        ),
        index=0,
        total=10,
    )

    # --- assert -----------------------
    # 100x60 -> +bar(4) -> 100x64 -> +border(3) -> 106x70
    assert out.size == (106, 70)
    assert out.getpixel((0, 0)) == (17, 17, 17, 255)  # border (#111111) wraps the whole thing
