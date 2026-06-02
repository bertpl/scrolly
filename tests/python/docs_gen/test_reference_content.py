"""Tests for the auto-generated reference content renderers."""

from __future__ import annotations

import json5
import pytest
import reference_content as rc

from scrolly.errors import registered_codes
from scrolly.slide import element_source_types


# --- element pages ----------------------------------
def test_element_keys_cover_every_element_type():
    # --- act / assert -----------------
    assert set(rc.element_keys()) == set(element_source_types())


@pytest.mark.parametrize("key", sorted(element_source_types()))
def test_element_page_has_fields_and_example(key):
    # --- act --------------------------
    page = rc.element_page(key)

    # --- assert -----------------------
    assert page.startswith(f"# `{key}` element")
    assert "## Fields" in page
    # The content field for the element appears in the field table.
    assert f"`{key}`" in page or key in page
    assert "## Example" in page
    assert "```json5" in page


@pytest.mark.parametrize("key", sorted(element_source_types()))
def test_element_snippet_is_valid_for_its_type(key):
    # --- arrange ----------------------
    # Extract the fenced snippet from the rendered page.
    page = rc.element_page(key)
    snippet = page.split("```json5\n", 1)[1].split("```", 1)[0]

    # --- act --------------------------
    parsed = json5.loads(snippet)
    element = element_source_types()[key].model_validate(parsed)

    # --- assert -----------------------
    assert element.SOURCE_KEY == key


def test_element_index_lists_all_and_documents_common_fields():
    # --- act --------------------------
    page = rc.element_index_page()

    # --- assert -----------------------
    for key in element_source_types():
        assert f"[`{key}`]({key}.md)" in page
    assert "## Common fields" in page
    # A representative shared field is documented.
    assert "`position`" in page


def test_element_table_escapes_pipes_in_literal_types():
    # markdown's text_align is a Literal union; its pipes must be escaped
    # so the Markdown table stays intact.
    # --- act / assert -----------------
    page = rc.element_page("markdown")
    assert "`text_align`" in page
    assert "\\|" in page


# --- file schemas -----------------------------------
def test_file_schema_keys():
    # --- act / assert -----------------
    assert rc.file_schema_keys() == ["deck", "slide"]


@pytest.mark.parametrize("key", ["deck", "slide"])
def test_file_schema_page_has_fields_and_example(key):
    # --- act --------------------------
    page = rc.file_schema_page(key)

    # --- assert -----------------------
    assert page.startswith(f"# `{key}` source file")
    assert "## Fields" in page
    assert "## Example" in page
    assert "```json5" in page


def test_file_schema_deck_table_lists_top_level_fields():
    # --- act --------------------------
    page = rc.file_schema_page("deck")

    # --- assert -----------------------
    for field in ("`title`", "`slides`", "`edges`"):
        assert field in page


def test_file_schema_slide_table_lists_elements_and_links_out():
    # --- act --------------------------
    page = rc.file_schema_page("slide")

    # --- assert -----------------------
    assert "`elements`" in page
    assert "`scroll_range`" in page
    assert "../elements/index.md" in page


def test_file_index_lists_both_formats():
    # --- act --------------------------
    page = rc.file_index_page()

    # --- assert -----------------------
    assert "[`deck`](deck.md)" in page
    assert "[`slide`](slide.md)" in page


def test_slide_snippet_validates_against_slide_ir():
    # --- arrange ----------------------
    from scrolly.slide.ir import SlideIR

    page = rc.file_schema_page("slide")
    snippet = page.split("```json5\n", 1)[1].split("```", 1)[0]

    # --- act --------------------------
    slide = SlideIR.model_validate(json5.loads(snippet))

    # --- assert -----------------------
    assert slide.title == "Intro"
    assert slide.elements[0].markdown == "# Hello\n\nWelcome to the deck."


def test_deck_snippet_parses_with_required_keys():
    # --- arrange ----------------------
    page = rc.file_schema_page("deck")
    snippet = page.split("```json5\n", 1)[1].split("```", 1)[0]

    # --- act --------------------------
    parsed = json5.loads(snippet)

    # --- assert -----------------------
    assert "slides" in parsed
    assert parsed["slides"][0]["source"].endswith(".slide.json")


# --- error pages ------------------------------------
def test_error_codes_match_registry():
    # --- act / assert -----------------
    assert rc.error_codes() == sorted(registered_codes())


def test_error_page_is_the_catalog_entry():
    # --- act --------------------------
    page = rc.error_page("E202")

    # --- assert -----------------------
    assert page.startswith("# E202")
    assert "## Cause" in page


def test_error_index_links_every_code():
    # --- act --------------------------
    page = rc.error_index_page()

    # --- assert -----------------------
    for code in registered_codes():
        assert f"[{code}]({code}.md)" in page


# --- literate-nav SUMMARY ---------------------------
def test_reference_summary_wires_cli_elements_and_errors():
    # --- act --------------------------
    summary = rc.reference_summary()

    # --- assert -----------------------
    assert "- [CLI](cli.md)" in summary
    assert "- File schemas:" in summary
    assert "    - [deck](files/deck.md)" in summary
    assert "- Element schemas:" in summary
    assert "    - [markdown](elements/markdown.md)" in summary
    assert "- Error codes:" in summary
    assert "    - [E202](errors/E202.md)" in summary
