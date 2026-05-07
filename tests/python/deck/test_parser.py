import pytest

from scrolly.deck.model import Position, Side
from scrolly.deck.parser import parse_deck
from scrolly.errors import DeckParseError
from tests.python.conftest import PROJECT_ROOT

FIXTURES = PROJECT_ROOT / "tests" / "python" / "fixtures" / "decks"


def test_parse_minimal_valid_deck():
    deck = parse_deck(FIXTURES / "valid" / "minimal.deck.json")
    assert deck.title == "Minimal"
    assert len(deck.slides) == 1
    assert deck.slides[0].id == "only"
    assert deck.slides[0].position == Position(0, 0)
    assert deck.slides[0].source.name == "only.static.md"
    assert deck.edges == ()


def test_parse_l_shape_deck():
    deck = parse_deck(FIXTURES / "valid" / "l-shape.deck.json")
    assert deck.title == "L-shape"
    assert len(deck.slides) == 3
    assert len(deck.edges) == 2
    # First edge has explicit sides.
    assert deck.edges[0].a.slide_id == "intro"
    assert deck.edges[0].a.side is Side.RIGHT
    assert deck.edges[0].b.slide_id == "details"
    assert deck.edges[0].b.side is Side.LEFT
    # Second edge has no sides — they'll be inferred later.
    assert deck.edges[1].a.side is None
    assert deck.edges[1].b.side is None


def test_slide_source_resolved_relative_to_deck_dir():
    deck = parse_deck(FIXTURES / "valid" / "minimal.deck.json")
    expected_parent = (FIXTURES / "valid" / "slides").resolve()
    assert deck.slides[0].source.parent == expected_parent


def test_parse_error_on_malformed_json(tmp_path):
    f = tmp_path / "bad.deck.json"
    f.write_text("{ slides: [ unclosed")
    with pytest.raises(DeckParseError):
        parse_deck(f)


def test_parse_error_on_top_level_not_object(tmp_path):
    f = tmp_path / "top.deck.json"
    f.write_text("[]")
    with pytest.raises(DeckParseError, match="must be a JSON5 object"):
        parse_deck(f)


def test_parse_error_on_missing_slides_field(tmp_path):
    f = tmp_path / "no-slides.deck.json"
    f.write_text("{ title: 'no slides' }")
    with pytest.raises(DeckParseError, match="missing required field 'slides'"):
        parse_deck(f)


def test_parse_error_on_bad_position_shape(tmp_path):
    f = tmp_path / "bad-pos.deck.json"
    f.write_text("{ slides: [{ id: 'a', position: [0], source: 'x.static.md' }], edges: [] }")
    with pytest.raises(DeckParseError, match="'position' must be"):
        parse_deck(f)


def test_parse_error_on_boolean_position(tmp_path):
    f = tmp_path / "bool-pos.deck.json"
    f.write_text("{ slides: [{ id: 'a', position: [true, 0], source: 'x.static.md' }], edges: [] }")
    with pytest.raises(DeckParseError, match="must be integers"):
        parse_deck(f)


def test_parse_error_on_unknown_side(tmp_path):
    f = tmp_path / "bad-edge.deck.json"
    f.write_text(
        """
        {
          slides: [
            { id: 'a', position: [0, 0], source: 'a.static.md' },
            { id: 'b', position: [1, 0], source: 'b.static.md' },
          ],
          edges: [
            ['a|sideways', 'b'],
          ],
        }
        """
    )
    with pytest.raises(DeckParseError, match="is not one of"):
        parse_deck(f)


def test_parse_error_on_empty_slide_id(tmp_path):
    f = tmp_path / "empty-id.deck.json"
    f.write_text(
        """
        {
          slides: [{ id: 'a', position: [0, 0], source: 'a.static.md' }],
          edges: [['|right', 'a']],
        }
        """
    )
    with pytest.raises(DeckParseError, match="empty slide id"):
        parse_deck(f)


def test_parse_edge_with_only_one_side_specified(tmp_path):
    f = tmp_path / "mixed.deck.json"
    f.write_text(
        """
        {
          slides: [
            { id: 'a', position: [0, 0], source: 'a.static.md' },
            { id: 'b', position: [1, 0], source: 'b.static.md' },
          ],
          edges: [['a|right', 'b']],
        }
        """
    )
    deck = parse_deck(f)
    assert deck.edges[0].a.side is Side.RIGHT
    assert deck.edges[0].b.side is None


# ── Group parsing ────────────────────────────────────────────────


def test_parse_grouped_deck():
    deck = parse_deck(FIXTURES / "valid" / "grouped.deck.json")
    assert len(deck.slides) == 4
    assert len(deck.groups) == 1
    assert deck.groups[0].label == "Architecture"
    assert deck.groups[0].slide_ids == ("arch-1", "arch-2")
    assert deck.groups[0].color is None


def test_grouped_slides_flattened_in_order():
    deck = parse_deck(FIXTURES / "valid" / "grouped.deck.json")
    ids = [s.id for s in deck.slides]
    assert ids == ["intro", "arch-1", "arch-2", "outro"]


def test_ungrouped_deck_has_empty_groups():
    deck = parse_deck(FIXTURES / "valid" / "minimal.deck.json")
    assert deck.groups == ()


@pytest.mark.parametrize("color,expected", [
    ("#abc", "#abc"),
    ("#AABBCC", "#AABBCC"),
    ("#f5cba7", "#f5cba7"),
])
def test_parse_group_color(tmp_path, color, expected):
    # --- arrange ----------------------------
    f = tmp_path / "color.deck.json"
    f.write_text(f"""{{
      slides: [{{
        group: "G", color: "{color}",
        slides: [{{ id: "a", position: [0, 0], source: "a.static.md" }}],
      }}],
    }}""")
    (tmp_path / "a.static.md").write_text("---\ninitial_scroll_position: 0\n---\n# A\n")

    # --- act --------------------------------
    deck = parse_deck(f)

    # --- assert -----------------------------
    assert deck.groups[0].color == expected


@pytest.mark.parametrize("color", [
    "abc",
    "#ab",
    "#abcde",
    "#GGHHII",
    "red",
    "rgb(0,0,0)",
])
def test_parse_error_on_invalid_group_color(tmp_path, color):
    # --- arrange ----------------------------
    f = tmp_path / "bad-color.deck.json"
    f.write_text(f"""{{
      slides: [{{
        group: "G", color: "{color}",
        slides: [{{ id: "a", position: [0, 0], source: "a.static.md" }}],
      }}],
    }}""")

    # --- act / assert -----------------------
    with pytest.raises(DeckParseError, match="#RGB or #RRGGBB"):
        parse_deck(f)


def test_parse_error_on_nested_groups(tmp_path):
    f = tmp_path / "nested.deck.json"
    f.write_text("""
    {
      slides: [
        {
          group: "Outer",
          slides: [
            { group: "Inner", slides: [{ id: "a", position: [0, 0], source: "a.static.md" }] },
          ],
        },
      ],
    }
    """)
    with pytest.raises(DeckParseError, match="nested groups"):
        parse_deck(f)


def test_parse_error_on_empty_group_label(tmp_path):
    f = tmp_path / "empty-label.deck.json"
    f.write_text("""
    {
      slides: [
        {
          group: "",
          slides: [{ id: "a", position: [0, 0], source: "a.static.md" }],
        },
      ],
    }
    """)
    with pytest.raises(DeckParseError, match="non-empty string"):
        parse_deck(f)


def test_parse_error_on_group_without_slides(tmp_path):
    f = tmp_path / "no-inner.deck.json"
    f.write_text("""
    {
      slides: [
        { group: "Empty", },
      ],
    }
    """)
    with pytest.raises(DeckParseError, match="'slides' list"):
        parse_deck(f)
