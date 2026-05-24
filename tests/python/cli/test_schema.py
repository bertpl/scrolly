"""Tests for the ``scrolly schema`` CLI command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli

runner = CliRunner()


def test_schema_no_arg_lists_types():
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0
    assert "deck" in result.output
    assert "slide" in result.output


def test_schema_no_arg_shows_suffixes():
    result = runner.invoke(cli, ["schema"])
    assert ".deck.json" in result.output
    assert ".slide.json" in result.output


def test_schema_deck_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "deck"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["type"] == "object"
    assert "slides" in schema["properties"]
    assert "slides" in schema["required"]


def test_schema_deck_documents_edges():
    result = runner.invoke(cli, ["schema", "deck"])
    schema = json.loads(result.output)
    assert "edges" in schema["properties"]
    edge_items = schema["properties"]["edges"]["items"]
    assert "slide_id" in edge_items["description"]


def test_schema_slide_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "slide"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert "elements" in schema["properties"]
    assert "scroll_range" in schema["properties"]
    assert "font_scale" in schema["properties"]


def test_schema_unknown_type_exits_1():
    result = runner.invoke(cli, ["schema", "bogus"])
    assert result.exit_code == 1
    assert "unknown type" in result.output
