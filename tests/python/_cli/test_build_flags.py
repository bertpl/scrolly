"""Tests for `scrolly build` flag surfacing: the hidden `--no-minification`
debug flag and the `--reencode-bitmaps` quality/off flag."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from scrolly import __version__
from scrolly._cli.ai_help import build_ai_help
from scrolly._cli.cli import cli
from tests.python.conftest import inflate_compressed_page


def _write_minimal_deck(tmp_path: Path) -> Path:
    """Write a one-slide deck into ``tmp_path`` and return the deck file path."""
    (tmp_path / "only.slide.json").write_text(
        '{ title: "x", elements: [{ markdown: "# x", position: [0, 0], width: 100, height: "auto" }] }'
    )
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
    return deck_file


def test_no_minification_absent_from_build_help() -> None:
    # --- act --------------------------
    result = CliRunner().invoke(cli, ["build", "--help"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert "--no-minification" not in result.output


def test_no_minification_absent_from_ai_help() -> None:
    # --- act / assert -----------------
    assert "--no-minification" not in build_ai_help(cli, __version__)


def test_no_minification_flag_restores_readable_assets(tmp_path: Path) -> None:
    # --- arrange ----------------------
    deck_file = _write_minimal_deck(tmp_path)
    out = tmp_path / "dist"

    # --- act --------------------------
    result = CliRunner().invoke(cli, ["build", str(deck_file), "--out", str(out), "--no-minification"])

    # --- assert -----------------------
    assert result.exit_code == 0, result.output
    html = inflate_compressed_page((out / "index.html").read_text())
    assert "// ----" in html  # JS section banners
    assert ".canvas {" in html  # unminified CSS keeps the space before the brace


def test_reencode_bitmaps_visible_in_build_help() -> None:
    # --- act --------------------------
    result = CliRunner().invoke(cli, ["build", "--help"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert "--reencode-bitmaps" in result.output


def test_reencode_explicit_quality_with_no_inline_errors(tmp_path: Path) -> None:
    # --- arrange ----------------------
    deck_file = _write_minimal_deck(tmp_path)
    out = tmp_path / "dist"

    # --- act --------------------------
    result = CliRunner().invoke(
        cli, ["build", str(deck_file), "--out", str(out), "--no-inline", "--reencode-bitmaps", "90"]
    )

    # --- assert -----------------------
    # A plain Click usage error (exit code 2), not a numbered catalog code.
    assert result.exit_code == 2
    assert "requires inlining" in result.output


@pytest.mark.parametrize("extra_args", [[], ["--reencode-bitmaps", "off"]])
def test_reencode_no_inline_without_explicit_quality_is_ok(tmp_path: Path, extra_args: list[str]) -> None:
    # --- arrange ----------------------
    # The default quality silently disables under --no-inline; an explicit
    # `off` is likewise a no-op. Neither is an error.
    deck_file = _write_minimal_deck(tmp_path)
    out = tmp_path / "dist"

    # --- act --------------------------
    result = CliRunner().invoke(cli, ["build", str(deck_file), "--out", str(out), "--no-inline", *extra_args])

    # --- assert -----------------------
    assert result.exit_code == 0, result.output
