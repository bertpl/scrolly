"""Tests for the ``scrolly schema`` CLI command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli

runner = CliRunner()


def test_schema_no_arg_lists_all_types():
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0
    assert "deck" in result.output
    assert "static" in result.output
    assert "scrollimation" in result.output
    assert "storyboard" in result.output


def test_schema_no_arg_shows_suffixes():
    result = runner.invoke(cli, ["schema"])
    assert ".deck.json" in result.output
    assert ".static.md" in result.output
    assert ".scrollimation.json" in result.output
    assert ".storyboard.json" in result.output


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


def test_schema_scrollimation_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "scrollimation"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert "scroll_range" in schema["properties"]
    assert "elements" in schema["properties"]


def test_schema_storyboard_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "storyboard"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert "scenes" in schema["properties"]
    assert "scene_distance" in schema["properties"]


def test_schema_static_has_frontmatter_format():
    result = runner.invoke(cli, ["schema", "static"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["format"] == "markdown-frontmatter"
    assert "initial_scroll_position" in schema["frontmatter"]["properties"]
    assert "initial_scroll_position" in schema["frontmatter"]["required"]


def test_schema_static_documents_body():
    result = runner.invoke(cli, ["schema", "static"])
    schema = json.loads(result.output)
    assert schema["body"]["format"] == "markdown"


def test_schema_unknown_type_exits_1():
    result = runner.invoke(cli, ["schema", "bogus"])
    assert result.exit_code == 1
    assert "unknown type" in result.output
