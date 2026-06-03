"""Tests for ``scrolly --help-for-ai-tools`` (the single-document CLI reference)."""

from __future__ import annotations

import json
import re

from click.testing import CliRunner

from scrolly import __version__
from scrolly._cli.ai_help import build_ai_help
from scrolly._cli.cli import cli
from scrolly.errors import registered_codes
from scrolly.slide import element_source_types

runner = CliRunner()


def _doc() -> str:
    """Build the reference document straight from the CLI group."""
    return build_ai_help(cli, __version__)


# --- flag plumbing ----------------------------------
def test_flag_exits_zero_and_emits_document():
    # --- act --------------------------
    result = runner.invoke(cli, ["--help-for-ai-tools"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert result.output.startswith(f"# scrolly {__version__}")


def test_flag_needs_no_subcommand_or_deck():
    # --- act --------------------------
    result = runner.invoke(cli, ["--help-for-ai-tools"])

    # --- assert -----------------------
    # the eager flag short-circuits before the group asks for a subcommand
    assert result.exit_code == 0
    assert "missing command" not in result.output.lower()


# --- coverage ---------------------------------------
def test_covers_every_element_type():
    # --- arrange / act ----------------
    doc = _doc()

    # --- assert -----------------------
    for key in element_source_types():
        assert f"### `{key}`" in doc


def test_covers_every_error_code():
    # --- arrange / act ----------------
    doc = _doc()

    # --- assert -----------------------
    for code in registered_codes():
        assert f"### {code} " in doc


def test_includes_full_command_tree():
    # --- arrange / act ----------------
    doc = _doc()

    # --- assert -----------------------
    for path in ("scrolly", "scrolly build", "scrolly schema element", "scrolly introspect slides"):
        assert f"### `{path}`" in doc


def test_includes_both_file_schemas():
    # --- arrange / act ----------------
    doc = _doc()

    # --- assert -----------------------
    assert "### `deck`" in doc
    assert "### `slide`" in doc


# --- structure --------------------------------------
def test_every_json_block_parses():
    # --- arrange / act ----------------
    blocks = re.findall(r"```json\n(.*?)\n```", _doc(), re.DOTALL)

    # --- assert -----------------------
    assert blocks
    for block in blocks:
        json.loads(block)


def test_error_subsections_are_demoted_under_the_section():
    # --- arrange / act ----------------
    doc = _doc()

    # --- assert -----------------------
    # catalog bodies' own `## Cause` headings are demoted so they nest under
    # `## Error codes` rather than competing with the top-level sections
    assert "#### Cause" in doc
    assert "\n## Cause" not in doc
