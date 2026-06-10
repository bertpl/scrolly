"""Tests for the ``scrolly validate`` CLI command."""

from __future__ import annotations

from click.testing import CliRunner

from scrolly._cli.cli import cli
from tests.python.conftest import PROJECT_ROOT

EXAMPLES_DIR = PROJECT_ROOT / "examples"

runner = CliRunner()


def test_validate_regression_deck():
    deck_file = EXAMPLES_DIR / "_regression" / "deck.deck.json"
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 0
    assert "Valid" in result.output
    assert "19 slides" in result.output
    assert "19 edges" in result.output


def test_validate_minimal_deck(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text('{ title: "Hi", elements: [{ markdown: "# Hi", position: [0, 0], width: 100, height: "auto" }] }')
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
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
    deck_file.write_text('{ slides: [{ id: "gone", position: [0, 0], source: "nonexistent.slide.json" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 1


def test_validate_invalid_slide_content_exits_1(tmp_path):
    slide = tmp_path / "bad.slide.json"
    slide.write_text("not valid json5 at all {{{")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "bad", position: [0, 0], source: "bad.slide.json" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 1


def test_validate_strict_reports_out_of_range_keyframes(tmp_path):
    slide = tmp_path / "slides" / "s.slide.json"
    slide.parent.mkdir(parents=True)
    slide.write_text("""{
  title: "T",
  scroll_range: 100,
  elements: [{ html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
    opacity: { keyframes: [[0, 1], [200, 0]] } }],
}""")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "s", position: [0, 0], source: "slides/s.slide.json" }], edges: [] }')
    result = runner.invoke(cli, ["validate", "--strict", str(deck_file)])
    assert result.exit_code == 0
    assert "warning" in result.output


def test_validate_without_strict_no_warnings(tmp_path):
    slide = tmp_path / "slides" / "s.slide.json"
    slide.parent.mkdir(parents=True)
    slide.write_text("""{
  title: "T",
  scroll_range: 100,
  elements: [{ html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
    opacity: { keyframes: [[0, 1], [200, 0]] } }],
}""")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "s", position: [0, 0], source: "slides/s.slide.json" }], edges: [] }')
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 0
    assert "warning" not in result.output
