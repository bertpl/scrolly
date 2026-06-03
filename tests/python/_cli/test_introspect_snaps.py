"""Tests for ``scrolly introspect snaps``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli.cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_snaps_returns_per_slide_split() -> None:
    """Output carries author + derived + merged sections per slide."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "snaps", str(REGRESSION_DECK), "--slide", "cast"])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    entry = payload["slides"]["cast"]
    assert {"author_snap_positions", "derived_snap_positions", "merged"} <= set(entry.keys())


def test_snaps_derived_carries_structured_source() -> None:
    """Each derived entry's ``source`` names the element + frame index."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "snaps", str(REGRESSION_DECK), "--slide", "cast"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    derived = payload["slides"]["cast"]["derived_snap_positions"]
    assert len(derived) > 0
    for entry in derived:
        assert "value" in entry
        source = entry["source"]
        assert {"element_index", "element_name", "frame_index"} <= set(source.keys())


def test_snaps_merged_is_sorted_and_includes_both_sources() -> None:
    """``merged`` is the sorted union of author + derived values."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "snaps", str(REGRESSION_DECK), "--slide", "cast"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    entry = payload["slides"]["cast"]
    merged = entry["merged"]
    assert merged == sorted(merged)
    derived_values = {d["value"] for d in entry["derived_snap_positions"]}
    author_values = set(entry["author_snap_positions"])
    assert (derived_values | author_values) == set(merged)
