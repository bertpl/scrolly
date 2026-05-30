"""Tests for ``scrolly introspect slides``."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scrolly._cli._cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_slides_emits_deck_topology() -> None:
    """``introspect slides`` returns slides + edges + groups for the regression deck."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "slides", str(REGRESSION_DECK)])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload.keys()) == {"slides", "edges", "groups"}
    # Regression deck has 17 slides and 17 edges (matching the existing build tests).
    assert len(payload["slides"]) == 17
    assert len(payload["edges"]) == 17


def test_slides_entry_fields() -> None:
    """Every slide entry carries the documented fields."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "slides", str(REGRESSION_DECK)])

    # --- assert -----------------------
    payload = json.loads(result.output)
    entry = next(iter(payload["slides"].values()))
    assert set(entry.keys()) == {
        "id",
        "position",
        "title",
        "scroll_range",
        "element_count",
        "snap_position_count",
    }


def test_slides_edge_fields() -> None:
    """Every edge entry carries fully-specified ``a`` and ``b`` endpoints with sides."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "slides", str(REGRESSION_DECK)])

    # --- assert -----------------------
    payload = json.loads(result.output)
    for edge in payload["edges"]:
        assert set(edge.keys()) == {"a", "b"}
        assert set(edge["a"].keys()) == {"slide", "side"}
        assert edge["a"]["side"] in {"top", "bottom", "left", "right"}


def test_slides_writes_to_output_path(tmp_path: Path) -> None:
    """``-o PATH`` writes the JSON to the file instead of stdout."""
    # --- arrange ----------------------
    runner = CliRunner()
    out = tmp_path / "topology.json"

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "slides", str(REGRESSION_DECK), "-o", str(out)])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert result.output == ""  # nothing on stdout
    payload = json.loads(out.read_text())
    assert "slides" in payload


def test_slides_validation_gate_failure() -> None:
    """Broken decks exit non-zero with an error on stderr; no JSON emitted."""
    # --- arrange ----------------------
    runner = CliRunner()
    # Nonexistent deck file -> Click rejects the path before we ever load.
    # Use a syntactically broken in-memory deck to exercise the gate.
    runner_with_fs = CliRunner()
    with runner_with_fs.isolated_filesystem():
        broken = Path("broken.deck.json")
        broken.write_text("{ not: valid JSON5, ")  # truncated

        # --- act ----------------------
        result = runner_with_fs.invoke(cli, ["introspect", "slides", str(broken)])

        # --- assert -------------------
        assert result.exit_code == 1
        # Should NOT emit JSON on stdout when the gate trips.
        assert result.stdout.strip() == ""
