"""Tests for color utilities (luminance + legible-text-color picks)."""

from __future__ import annotations

import pytest

from scrolly.render.color import legible_text_color, relative_luminance


@pytest.mark.parametrize(
    "background",
    [
        "#ffffff",  # white
        "#dcdcdc",  # default group bg
        "#a8d8ea",  # light pastel
        "#9DBAD2",  # hero "Main Content" (lum 0.47 — black wins on contrast)
        "#9DD2BA",  # hero "Details" (lightest green)
        "#fff",  # short form
    ],
)
def test_legible_text_color_black_on_light_and_mid(background) -> None:
    # --- act / assert -----------------
    assert legible_text_color(background) == "#000000"


@pytest.mark.parametrize(
    "background",
    [
        "#000000",  # black
        "#4A6FA5",  # hero "Introduction" / title blue
        "#8B2F2F",  # regression "Backdoor"
        "#3E7D5A",  # dark green
        "#000",  # short form
    ],
)
def test_legible_text_color_white_on_dark(background) -> None:
    # --- act / assert -----------------
    assert legible_text_color(background) == "#ffffff"


def test_relative_luminance_bounds() -> None:
    # --- act / assert -----------------
    assert relative_luminance("#000000") == pytest.approx(0.0)
    assert relative_luminance("#ffffff") == pytest.approx(1.0)


def test_relative_luminance_short_and_long_form_agree() -> None:
    # --- act / assert -----------------
    assert relative_luminance("#fff") == pytest.approx(relative_luminance("#ffffff"))


@pytest.mark.parametrize("bad", ["abc", "#ab", "#abcde", "#GG0000"])
def test_invalid_hex_raises(bad) -> None:
    # --- act / assert -----------------
    with pytest.raises(ValueError, match="#RGB or #RRGGBB"):
        relative_luminance(bad)
