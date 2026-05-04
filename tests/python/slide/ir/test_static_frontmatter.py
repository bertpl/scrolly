import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir.static import (
    Frontmatter,
    parse_frontmatter,
    split_frontmatter,
)


def test_split_extracts_yaml_and_body():
    src = "---\ninitial_scroll_position: 0\n---\n# body\n\ntext"
    yaml_text, body = split_frontmatter(src)
    assert "initial_scroll_position: 0" in yaml_text
    assert body.startswith("# body")


def test_parse_returns_frontmatter_and_body():
    src = "---\ninitial_scroll_position: 0\n---\n# body"
    fm, body = parse_frontmatter(src)
    assert isinstance(fm, Frontmatter)
    assert fm.initial_scroll_position == 0
    assert fm.title is None
    assert body == "# body"


def test_parse_with_explicit_title():
    src = "---\ninitial_scroll_position: 0\ntitle: My Slide\n---\n# Body H1"
    fm, _ = parse_frontmatter(src)
    assert fm.title == "My Slide"


def test_parse_with_quoted_title():
    src = '---\ninitial_scroll_position: 0\ntitle: "With: colons"\n---\n'
    fm, _ = parse_frontmatter(src)
    assert fm.title == "With: colons"


def test_title_strips_surrounding_whitespace():
    src = "---\ninitial_scroll_position: 0\ntitle: '  spaced  '\n---\n"
    fm, _ = parse_frontmatter(src)
    assert fm.title == "spaced"


def test_non_string_title_rejected():
    src = "---\ninitial_scroll_position: 0\ntitle: 42\n---\n"
    with pytest.raises(SlideSourceError, match="'title' must be a string"):
        parse_frontmatter(src)


def test_empty_title_rejected():
    src = "---\ninitial_scroll_position: 0\ntitle: ''\n---\n"
    with pytest.raises(SlideSourceError, match="'title' must be a non-empty string"):
        parse_frontmatter(src)


def test_missing_opening_delimiter_raises():
    with pytest.raises(SlideSourceError, match="opening"):
        parse_frontmatter("# just markdown")


def test_missing_closing_delimiter_raises():
    with pytest.raises(SlideSourceError, match="closing"):
        parse_frontmatter("---\ninitial_scroll_position: 0")


def test_missing_initial_scroll_position_raises():
    with pytest.raises(SlideSourceError, match="'initial_scroll_position' is required"):
        parse_frontmatter("---\nfoo: bar\n---\n")


def test_negative_initial_scroll_position_rejected():
    with pytest.raises(SlideSourceError, match=">= 0"):
        parse_frontmatter("---\ninitial_scroll_position: -1\n---\n")


def test_boolean_initial_scroll_position_rejected():
    with pytest.raises(SlideSourceError, match="must be an integer"):
        parse_frontmatter("---\ninitial_scroll_position: true\n---\n")


def test_frontmatter_must_be_mapping():
    with pytest.raises(SlideSourceError, match="mapping"):
        parse_frontmatter("---\n- just\n- a\n- list\n---\n")


def test_empty_frontmatter_rejected():
    with pytest.raises(SlideSourceError, match="empty"):
        parse_frontmatter("---\n---\n")


def test_font_scale_defaults_to_one_when_absent():
    src = "---\ninitial_scroll_position: 0\n---\n"
    fm, _ = parse_frontmatter(src)
    assert fm.font_scale == 1.0


def test_font_scale_float_accepted():
    src = "---\ninitial_scroll_position: 0\nfont_scale: 1.5\n---\n"
    fm, _ = parse_frontmatter(src)
    assert fm.font_scale == 1.5


def test_font_scale_int_normalized_to_float():
    # YAML `2` parses as int; the parser stores it as float for type uniformity.
    src = "---\ninitial_scroll_position: 0\nfont_scale: 2\n---\n"
    fm, _ = parse_frontmatter(src)
    assert fm.font_scale == 2.0
    assert isinstance(fm.font_scale, float)


def test_font_scale_zero_rejected():
    src = "---\ninitial_scroll_position: 0\nfont_scale: 0\n---\n"
    with pytest.raises(SlideSourceError, match="'font_scale' must be > 0"):
        parse_frontmatter(src)


def test_font_scale_negative_rejected():
    src = "---\ninitial_scroll_position: 0\nfont_scale: -0.5\n---\n"
    with pytest.raises(SlideSourceError, match="'font_scale' must be > 0"):
        parse_frontmatter(src)


def test_font_scale_string_rejected():
    src = "---\ninitial_scroll_position: 0\nfont_scale: '1.2'\n---\n"
    with pytest.raises(SlideSourceError, match="'font_scale' must be a number"):
        parse_frontmatter(src)


def test_font_scale_boolean_rejected():
    # bool is a subclass of int in Python — must be excluded explicitly.
    src = "---\ninitial_scroll_position: 0\nfont_scale: true\n---\n"
    with pytest.raises(SlideSourceError, match="'font_scale' must be a number"):
        parse_frontmatter(src)
