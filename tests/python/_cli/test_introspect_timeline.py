"""Tests for ``scrolly introspect timeline``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli.cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_timeline_element_carries_animated_properties_and_intervals() -> None:
    """Per-element entry has both sections; animated_properties holds only animated ones."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(REGRESSION_DECK), "--slide", "contributions"])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # elements[1] is the timeline image with animated `anchor` + `position`;
    # width/height/opacity are static.
    el = payload["slides"]["contributions"]["elements"][1]
    assert "animated_properties" in el
    assert "visibility_intervals" in el
    # anchor is animated on the timeline image.
    assert "anchor" in el["animated_properties"]
    # Static properties (e.g. width, opacity) should NOT appear in animated_properties.
    assert "width" not in el["animated_properties"]
    assert "opacity" not in el["animated_properties"]


def test_timeline_filter_restricts_to_slide() -> None:
    """``--slide intro`` returns only that slide."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(REGRESSION_DECK), "--slide", "title"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    assert set(payload["slides"].keys()) == {"title"}


def test_timeline_unknown_slide_exits_with_error() -> None:
    """Unknown slide id exits non-zero."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(REGRESSION_DECK), "--slide", "ghost"])

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "ghost" in result.output or "unknown slide id" in result.output
