"""Tests for ``scrolly introspect dom``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli.cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_dom_returns_per_element_html_and_css() -> None:
    """Each element entry carries ``html`` + ``scoped_css`` + identity fields."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "dom", str(REGRESSION_DECK), "--slide", "reference"])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    el = payload["slides"]["reference"]["elements"][0]
    assert set(el.keys()) == {"index", "name", "type", "html", "scoped_css"}
    assert el["type"] == "MarkdownElement"
    assert "<h1>" in el["html"]


def test_dom_filter_restricts_to_named_slides() -> None:
    """``--slide intro`` returns only that slide's per-element output."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "dom", str(REGRESSION_DECK), "--slide", "title"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    assert set(payload["slides"].keys()) == {"title"}


def test_dom_unfiltered_returns_every_slide() -> None:
    """Without ``--slide``, every slide's elements are returned."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "dom", str(REGRESSION_DECK)])

    # --- assert -----------------------
    payload = json.loads(result.output)
    assert len(payload["slides"]) == 23


def test_dom_unknown_slide_exits_with_error() -> None:
    """Unknown slide id exits non-zero with a clear error."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "dom", str(REGRESSION_DECK), "--slide", "ghost"])

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "ghost" in result.output or "unknown slide id" in result.output


def test_dom_omits_deck_level_chrome() -> None:
    """Per-element HTML doesn't include the slide wrapper, canvas runtime, or edges."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "dom", str(REGRESSION_DECK), "--slide", "reference"])

    # --- assert -----------------------
    payload = json.loads(result.output)
    html = payload["slides"]["reference"]["elements"][0]["html"]
    # Per-element html is just the element fragment, no slide-type wrapper.
    assert not html.startswith('<div class="slide-type-')
    # No deck-level chrome strings.
    assert "canvas-edges" not in html
    assert "navigation" not in html
