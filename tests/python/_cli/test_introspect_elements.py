"""Tests for ``scrolly introspect elements``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli.cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_elements_returns_resolved_tree_for_all_slides() -> None:
    """Unfiltered call returns every slide's element tree."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "elements", str(REGRESSION_DECK)])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["slides"]) == 17  # all regression deck slides present


def test_elements_filter_restricts_to_named_slides() -> None:
    """``--slide intro --slide setup`` returns only those two slides."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "elements", str(REGRESSION_DECK), "--slide", "title", "--slide", "reference"],
    )

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["slides"].keys()) == {"title", "reference"}


def test_elements_unknown_slide_exits_with_error() -> None:
    """``--slide ghost`` (no such slide) exits non-zero with a clear message."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "elements", str(REGRESSION_DECK), "--slide", "ghost"])

    # --- assert -----------------------
    assert result.exit_code == 1
    # Error message names the unknown id and lists known ids.
    assert "unknown slide id" in result.output or "ghost" in result.output


def test_elements_entries_carry_type_and_index() -> None:
    """Every element entry has ``type`` and ``index`` keys added on top of model_dump."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "elements", str(REGRESSION_DECK), "--slide", "reference"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    elements = payload["slides"]["reference"]["elements"]
    for el in elements:
        assert "type" in el and el["type"].endswith("Element")
        assert "index" in el and isinstance(el["index"], int)


def test_elements_animated_value_serializes_as_keyframes() -> None:
    """An animated property surfaces as ``{"keyframes": [...]}`` in the JSON view."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    # "capability" slide is documented in the regression deck as exercising animated
    # properties; the test verifies SOMETHING animated shows up as a keyframe dict
    # rather than asserting on specific values (which would couple the test to the
    # example deck's exact contents).
    result = runner.invoke(cli, ["introspect", "elements", str(REGRESSION_DECK), "--slide", "capability"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    elements = payload["slides"]["capability"]["elements"]

    def _has_keyframes(value: object) -> bool:
        return isinstance(value, dict) and "keyframes" in value

    found_any = False
    for el in elements:
        for key, value in el.items():
            if _has_keyframes(value):
                found_any = True
                break
    assert found_any, "expected at least one animated property in the parallax slide"
