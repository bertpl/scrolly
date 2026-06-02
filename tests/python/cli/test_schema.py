"""Tests for the ``scrolly schema`` command group."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli

runner = CliRunner()


# --- combined index ---------------------------------
def test_schema_no_arg_shows_both_sections():
    # --- act --------------------------
    result = runner.invoke(cli, ["schema"])

    # --- assert -----------------------
    assert result.exit_code == 0
    assert "File schemas" in result.output
    assert "Element schemas" in result.output
    assert "deck" in result.output
    assert "slide" in result.output
    assert "markdown" in result.output


# --- file subcommand --------------------------------
def test_schema_file_index_shows_suffixes():
    result = runner.invoke(cli, ["schema", "file"])
    assert result.exit_code == 0
    assert ".deck.json" in result.output
    assert ".slide.json" in result.output


def test_schema_file_deck_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "file", "deck"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["type"] == "object"
    assert "slides" in schema["properties"]
    assert "slides" in schema["required"]


def test_schema_file_deck_documents_edges():
    result = runner.invoke(cli, ["schema", "file", "deck"])
    schema = json.loads(result.output)
    edge_items = schema["properties"]["edges"]["items"]
    assert "slide_id" in edge_items["description"]


def test_schema_file_slide_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "file", "slide"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert "elements" in schema["properties"]
    assert "scroll_range" in schema["properties"]
    assert "font_scale" in schema["properties"]


def test_schema_file_unknown_type_exits_1():
    result = runner.invoke(cli, ["schema", "file", "bogus"])
    assert result.exit_code == 1
    assert "unknown file type" in result.output


def test_schema_file_list_types_is_bare_and_sorted():
    # --- act --------------------------
    result = runner.invoke(cli, ["schema", "file", "--list-types"])

    # --- assert -----------------------
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line]
    for line in lines:
        assert line == line.strip()
        assert " " not in line
    assert lines == sorted(lines)
    assert "deck" in lines
    assert "slide" in lines


# --- element subcommand -----------------------------
def test_schema_element_index_lists_all_keys():
    # --- act --------------------------
    result = runner.invoke(cli, ["schema", "element"])

    # --- assert -----------------------
    assert result.exit_code == 0
    for key in ("html", "iframe", "image", "image_sequence", "markdown", "mermaid"):
        assert key in result.output


def test_schema_element_markdown_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "element", "markdown"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["title"] == "MarkdownElement"
    assert "markdown" in schema["properties"]


def test_schema_element_image_sequence_outputs_valid_json():
    result = runner.invoke(cli, ["schema", "element", "image_sequence"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert "image_sequence" in schema["properties"]
    assert "frame_distance" in schema["properties"]


def test_schema_element_unknown_type_exits_1():
    result = runner.invoke(cli, ["schema", "element", "bogus"])
    assert result.exit_code == 1
    assert "unknown element type" in result.output


def test_schema_element_list_types_is_bare_and_sorted():
    # --- act --------------------------
    result = runner.invoke(cli, ["schema", "element", "--list-types"])

    # --- assert -----------------------
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line]
    for line in lines:
        assert line == line.strip()
        assert " " not in line
    assert lines == sorted(lines)
    assert lines == ["html", "iframe", "image", "image_sequence", "markdown", "mermaid"]


# --- breaking change: old flat form no longer works -
def test_schema_old_flat_type_arg_is_rejected():
    # `scrolly schema deck` used to print the deck schema; it now reads as
    # an unknown subcommand (deck/slide moved under `schema file`).
    result = runner.invoke(cli, ["schema", "deck"])
    assert result.exit_code != 0
