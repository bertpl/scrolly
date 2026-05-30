"""Tests for the deck source schema."""

from __future__ import annotations

from scrolly.deck.schema import deck_source_schema


def test_deck_source_schema_is_valid_json_schema():
    schema = deck_source_schema()
    assert schema["type"] == "object"
    assert "$schema" in schema


def test_deck_source_schema_requires_slides():
    schema = deck_source_schema()
    assert "slides" in schema["required"]


def test_deck_source_schema_title_is_optional():
    schema = deck_source_schema()
    assert "title" not in schema.get("required", [])
    assert "title" in schema["properties"]


def test_deck_source_schema_slide_fields():
    schema = deck_source_schema()
    slide_schema = schema["properties"]["slides"]["items"]["oneOf"][0]
    slide_props = slide_schema["properties"]
    assert "id" in slide_props
    assert "position" in slide_props
    assert "source" in slide_props


def test_deck_source_schema_group_wrapper():
    schema = deck_source_schema()
    group_schema = schema["properties"]["slides"]["items"]["oneOf"][1]
    group_props = group_schema["properties"]
    assert "group" in group_props
    assert "slides" in group_props
    assert "color" in group_props
    assert "label_color" in group_props


def test_deck_source_schema_edge_format():
    schema = deck_source_schema()
    edge_items = schema["properties"]["edges"]["items"]
    assert edge_items["minItems"] == 2
    assert edge_items["maxItems"] == 2
