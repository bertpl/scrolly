"""Tests for the ``scrolly init`` CLI command."""

from __future__ import annotations

import json5
from click.testing import CliRunner

from scrolly._cli._cli import cli

runner = CliRunner()


def test_init_creates_deck_and_slide(tmp_path):
    target = tmp_path / "my-deck"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0
    assert (target / "deck.deck.json").exists()
    assert (target / "slides" / "intro.static.md").exists()


def test_init_deck_is_valid_json5(tmp_path):
    target = tmp_path / "my-deck"
    runner.invoke(cli, ["init", str(target)])
    raw = json5.loads((target / "deck.deck.json").read_text())
    assert "slides" in raw
    assert len(raw["slides"]) == 1
    assert raw["slides"][0]["id"] == "intro"


def test_init_slide_has_frontmatter(tmp_path):
    target = tmp_path / "my-deck"
    runner.invoke(cli, ["init", str(target)])
    text = (target / "slides" / "intro.static.md").read_text()
    assert text.startswith("---\n")
    assert "initial_scroll_position" in text


def test_init_output_passes_validate(tmp_path):
    target = tmp_path / "my-deck"
    runner.invoke(cli, ["init", str(target)])
    result = runner.invoke(cli, ["validate", str(target / "deck.deck.json")])
    assert result.exit_code == 0
    assert "Valid" in result.output


def test_init_refuses_non_empty_directory(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "something.txt").write_text("occupied")
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 1
    assert "not empty" in result.output


def test_init_creates_parent_directories(tmp_path):
    target = tmp_path / "deep" / "nested" / "deck"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0
    assert (target / "deck.deck.json").exists()
