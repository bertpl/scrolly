"""Tests for ``scrolly introspect timeline``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli
from tests.python.conftest import PROJECT_ROOT

WORKED_EXAMPLE = PROJECT_ROOT / "examples" / "worked-example" / "deck.deck.json"


def test_timeline_element_carries_animated_properties_and_intervals() -> None:
    """Per-element entry has both sections; animated_properties holds only animated ones."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(WORKED_EXAMPLE), "--slide", "parallax"])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    bg = payload["slides"]["parallax"]["elements"][0]
    assert "animated_properties" in bg
    assert "visibility_intervals" in bg
    # bg has animated position
    assert "position" in bg["animated_properties"]
    # Static properties (e.g. opacity = 1.0 on bg) should NOT appear in animated_properties
    assert "opacity" not in bg["animated_properties"]


def test_timeline_filter_restricts_to_slide() -> None:
    """``--slide intro`` returns only that slide."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(WORKED_EXAMPLE), "--slide", "intro"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    assert set(payload["slides"].keys()) == {"intro"}


def test_timeline_unknown_slide_exits_with_error() -> None:
    """Unknown slide id exits non-zero."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "timeline", str(WORKED_EXAMPLE), "--slide", "ghost"])

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "ghost" in result.output or "unknown slide id" in result.output
