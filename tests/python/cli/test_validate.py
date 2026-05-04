"""Tests for the ``scrolly validate`` CLI command."""

from __future__ import annotations

from click.testing import CliRunner

from scrolly._cli._cli import cli
from tests.python.conftest import PROJECT_ROOT

EXAMPLES_DIR = PROJECT_ROOT / "examples"

runner = CliRunner()


def test_validate_worked_example():
    deck_file = EXAMPLES_DIR / "worked-example" / "deck.deck.json"
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 0
    assert "Valid" in result.output
    assert "9 slides" in result.output
    assert "12 edges" in result.output


def test_validate_minimal_deck(tmp_path):
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# Hi\n")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 0
    assert "1 slides" in result.output


def test_validate_malformed_json_exits_1(tmp_path):
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text("not json at all {{{")
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 1
    assert "error" in result.output


def test_validate_missing_slide_source_exits_1(tmp_path):
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "gone", position: [0, 0], source: "nonexistent.static.md" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 1


def test_validate_invalid_slide_content_exits_1(tmp_path):
    slide = tmp_path / "bad.static.md"
    slide.write_text("no frontmatter")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "bad", position: [0, 0], source: "bad.static.md" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 1
