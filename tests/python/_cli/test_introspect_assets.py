"""Tests for ``scrolly introspect assets``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_assets_returns_referenced_assets() -> None:
    """Regression deck uses several images; the asset table is non-empty."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "assets", str(REGRESSION_DECK)])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "assets" in payload
    assert len(payload["assets"]) > 0


def test_assets_entry_fields() -> None:
    """Every asset entry carries the documented metadata fields."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "assets", str(REGRESSION_DECK)])

    # --- assert -----------------------
    payload = json.loads(result.output)
    entry = payload["assets"][0]
    assert set(entry.keys()) == {"path", "name", "size_bytes", "exists", "mime", "referenced_by"}
    assert entry["exists"] is True
    assert entry["size_bytes"] >= 0
    assert entry["mime"] is not None
    assert len(entry["referenced_by"]) >= 1


def test_assets_filter_scopes_to_named_slide() -> None:
    """``--slide <id>`` restricts the asset walk to elements within that slide."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result_filtered = runner.invoke(
        cli,
        ["introspect", "assets", str(REGRESSION_DECK), "--slide", "capability"],
    )
    result_all = runner.invoke(cli, ["introspect", "assets", str(REGRESSION_DECK)])

    # --- assert -----------------------
    filtered = json.loads(result_filtered.output)
    full = json.loads(result_all.output)
    # Filtered set must be a subset of the full set.
    full_paths = {a["path"] for a in full["assets"]}
    filtered_paths = {a["path"] for a in filtered["assets"]}
    assert filtered_paths.issubset(full_paths)
    # Every "referenced_by" in the filtered output mentions only the named slide.
    for asset in filtered["assets"]:
        assert asset["referenced_by"] == ["capability"]


def test_assets_unknown_slide_exits_with_error() -> None:
    """``--slide ghost`` exits non-zero with a clear error."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "assets", str(REGRESSION_DECK), "--slide", "ghost"])

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "ghost" in result.output or "unknown slide id" in result.output
