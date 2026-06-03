"""Tests for the ``scrolly errors`` CLI command (three-form pattern)."""

from __future__ import annotations

from click.testing import CliRunner

from scrolly._cli.cli import cli


def test_errors_index_lists_all_codes() -> None:
    """``scrolly errors`` prints every registered code with its summary."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["errors"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert "E001" in result.output
    assert "JSON5 syntax error" in result.output  # E001's summary
    assert "E701" in result.output  # last band


def test_errors_specific_code_prints_catalog_body() -> None:
    """``scrolly errors E001`` prints the catalog markdown body."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["errors", "E001"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert "E001" in result.output
    assert "## Cause" in result.output
    assert "## How to fix" in result.output


def test_errors_unknown_code_exits_nonzero() -> None:
    """``scrolly errors E9999`` exits non-zero with an error message."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["errors", "E9999"])

    # --- assert -----------------------
    assert result.exit_code != 0
    assert "unknown error code" in result.output


def test_errors_list_codes_emits_one_per_line() -> None:
    """``scrolly errors --list-codes`` prints each code on its own line, no extras."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["errors", "--list-codes"])

    # --- assert -----------------------
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line]
    assert all(line.startswith("E") for line in lines)
    assert "E001" in lines
    assert "E701" in lines
    # Every line should be a bare code, nothing else.
    for line in lines:
        assert line == line.strip()
        assert " " not in line
