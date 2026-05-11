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
    assert "15 slides" in result.output
    assert "18 edges" in result.output


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


def test_validate_strict_reports_out_of_range_keyframes(tmp_path):
    slide = tmp_path / "slides" / "s.scrollimation.json"
    slide.parent.mkdir(parents=True)
    slide.write_text("""{
  title: "T",
  scroll_range: 100,
  elements: [{ html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
    opacity: { keyframes: [[0, 1], [200, 0]] } }],
}""")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ slides: [{ id: "s", position: [0, 0], source: "slides/s.scrollimation.json" }], edges: [] }'
    )
    result = runner.invoke(cli, ["validate", "--strict", str(deck_file)])
    assert result.exit_code == 0
    assert "warning" in result.output


def test_validate_without_strict_no_warnings(tmp_path):
    slide = tmp_path / "slides" / "s.scrollimation.json"
    slide.parent.mkdir(parents=True)
    slide.write_text("""{
  title: "T",
  scroll_range: 100,
  elements: [{ html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
    opacity: { keyframes: [[0, 1], [200, 0]] } }],
}""")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ slides: [{ id: "s", position: [0, 0], source: "slides/s.scrollimation.json" }], edges: [] }'
    )
    result = runner.invoke(cli, ["validate", str(deck_file)])
    assert result.exit_code == 0
    assert "warning" not in result.output
