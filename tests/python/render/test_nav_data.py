from pathlib import Path

from scrolly.deck.model import Deck, Edge, Endpoint, Position, Side, Slide, SlideGroup
from scrolly.render.nav_data import build_nav_data
from scrolly.slide.html import SlideHTML


def _slide(id_: str, x: int, y: int) -> Slide:
    return Slide(id=id_, position=Position(x, y), source=Path(f"/{id_}.static.md"))


def _chunks_for(*ids: str) -> dict[str, SlideHTML]:
    return {id_: SlideHTML(title=id_.title(), html="") for id_ in ids}


def test_empty_deck_has_no_initial_slide():
    data = build_nav_data(Deck(title=None, slides=(), edges=()), {})
    assert data == {"initial_slide": None, "fan_spacing_factor": 0.1, "slides": {}, "edges": [], "groups": []}


def test_initial_slide_is_the_first_declared():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
    )
    assert build_nav_data(deck, _chunks_for("a", "b"))["initial_slide"] == "a"


def test_position_is_captured_as_xy_list():
    deck = Deck(title=None, slides=(_slide("a", 3, 5),), edges=())
    assert build_nav_data(deck, _chunks_for("a"))["slides"]["a"]["position"] == [3, 5]


def test_title_per_slide_comes_from_chunk():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
    )
    chunks = {
        "a": SlideHTML(title="Alpha", html=""),
        "b": SlideHTML(title="Bravo", html=""),
    }
    data = build_nav_data(deck, chunks)
    assert data["slides"]["a"]["title"] == "Alpha"
    assert data["slides"]["b"]["title"] == "Bravo"


def test_content_driven_chunk_emits_null_scroll_range():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    chunks = {"a": SlideHTML(title="A", html="")}  # scroll_range defaults to None
    data = build_nav_data(deck, chunks)
    assert data["slides"]["a"]["scroll_range"] is None
    assert data["slides"]["a"]["scroll_speed"] == 1.0
    assert data["slides"]["a"]["initial_scroll_position"] == 0
    assert data["slides"]["a"]["reverse"] is False


def test_fixed_timeline_chunk_emits_int_scroll_range():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    chunks = {
        "a": SlideHTML(
            title="A",
            html="",
            scroll_range=1000,
            scroll_speed=2.0,
            initial_scroll_position=50,
        )
    }
    data = build_nav_data(deck, chunks)
    assert data["slides"]["a"]["scroll_range"] == 1000
    assert data["slides"]["a"]["scroll_speed"] == 2.0
    assert data["slides"]["a"]["initial_scroll_position"] == 50
    assert data["slides"]["a"]["reverse"] is False


def test_reverse_chunk_emits_reverse_true():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    chunks = {"a": SlideHTML(title="A", html="", scroll_range=1000, reverse=True)}
    data = build_nav_data(deck, chunks)
    assert data["slides"]["a"]["reverse"] is True


def test_undirected_edge_appears_on_both_endpoints_with_fan_composition():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    data = build_nav_data(deck, _chunks_for("a", "b"))
    # Single-edge sides → fan_index 0 of size 1 (canvas.js derives offset).
    assert data["slides"]["a"]["edges"] == {
        "right": [{"target": "b", "fan_index": 0, "fan_size": 1}],
    }
    assert data["slides"]["b"]["edges"] == {
        "left": [{"target": "a", "fan_index": 0, "fan_size": 1}],
    }


def test_multiple_edges_on_the_same_side_collect_in_axis_order():
    # a's right side has two edges; both targets at the same y are tied on
    # the primary sort key, secondary (x) breaks the tie: b at (1,0), c at (2,0).
    # (The fan_offset value itself is verified in test_fan.py; here we only
    # check the per-edge fan composition that travels via nav_data.)
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0), _slide("c", 2, 0)),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("c", Side.LEFT)),
        ),
    )
    data = build_nav_data(deck, _chunks_for("a", "b", "c"))
    entries = data["slides"]["a"]["edges"]["right"]
    assert [e["target"] for e in entries] == ["b", "c"]
    assert [e["fan_index"] for e in entries] == [0, 1]
    assert all(e["fan_size"] == 2 for e in entries)


def test_l_shape_produces_expected_graph():
    deck = Deck(
        title=None,
        slides=(_slide("intro", 0, 0), _slide("details", 1, 0), _slide("appendix", 1, 1)),
        edges=(
            Edge(Endpoint("intro", Side.RIGHT), Endpoint("details", Side.LEFT)),
            Edge(Endpoint("details", Side.BOTTOM), Endpoint("appendix", Side.TOP)),
        ),
    )
    data = build_nav_data(deck, _chunks_for("intro", "details", "appendix"))
    assert data["slides"]["intro"]["edges"] == {
        "right": [{"target": "details", "fan_index": 0, "fan_size": 1}],
    }
    assert data["slides"]["details"]["edges"] == {
        "left": [{"target": "intro", "fan_index": 0, "fan_size": 1}],
        "bottom": [{"target": "appendix", "fan_index": 0, "fan_size": 1}],
    }
    assert data["slides"]["appendix"]["edges"] == {
        "top": [{"target": "details", "fan_index": 0, "fan_size": 1}],
    }


def test_fan_spacing_factor_emitted_at_top_level():
    """Single source of truth: canvas.js reads the fan-spacing fraction
    from nav_data rather than carrying its own constant.
    """
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    data = build_nav_data(deck, _chunks_for("a"))
    # Value matches fan.py's FAN_SPACING_FACTOR constant.
    assert data["fan_spacing_factor"] == 0.1


def test_fan_offset_no_longer_in_per_edge_entries():
    """fan_offset is consumed by geometry.py directly from fan.py; runtime
    uses fan_index/fan_size to derive its own offset. No reason to ship
    fan_offset through nav_data anymore.
    """
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    data = build_nav_data(deck, _chunks_for("a", "b"))
    for entry in data["slides"]["a"]["edges"]["right"]:
        assert "fan_offset" not in entry


def test_snap_positions_default_empty():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    data = build_nav_data(deck, _chunks_for("a"))
    assert data["slides"]["a"]["snap_positions"] == []


def test_snap_positions_flow_through():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    chunks = {"a": SlideHTML(title="A", html="", scroll_range=200, snap_positions=(0, 100, 200))}
    data = build_nav_data(deck, chunks)
    assert data["slides"]["a"]["snap_positions"] == [0, 100, 200]


def test_multi_edge_fan_carries_index_and_size_per_entry():
    # A 3-edge fan: each entry carries its own fan_index (0, 1, 2),
    # all with fan_size = 3.
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 0, 2),
            _slide("up", 1, 0),
            _slide("md", 1, 2),
            _slide("dn", 1, 4),
        ),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("up", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("md", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("dn", Side.LEFT)),
        ),
    )
    entries = build_nav_data(deck, _chunks_for("a", "up", "md", "dn"))["slides"]["a"]["edges"]["right"]
    assert [e["fan_index"] for e in entries] == [0, 1, 2]
    assert [e["fan_size"] for e in entries] == [3, 3, 3]


# ---- flat edge topology array --------------------------------------------


def test_edges_array_empty_when_no_edges():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    data = build_nav_data(deck, _chunks_for("a"))
    assert data["edges"] == []


def test_edges_array_carries_topology_and_fan_composition():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    data = build_nav_data(deck, _chunks_for("a", "b"))
    assert len(data["edges"]) == 1
    e = data["edges"][0]
    assert e["a_slide"] == "a"
    assert e["a_side"] == "right"
    assert e["a_fan_index"] == 0
    assert e["a_fan_size"] == 1
    assert e["b_slide"] == "b"
    assert e["b_side"] == "left"
    assert e["b_fan_index"] == 0
    assert e["b_fan_size"] == 1


def test_edges_array_multi_edge_fan_carries_correct_indices():
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 0, 1),
            _slide("b", 1, 0),
            _slide("c", 1, 2),
        ),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("c", Side.LEFT)),
        ),
    )
    data = build_nav_data(deck, _chunks_for("a", "b", "c"))
    assert len(data["edges"]) == 2
    a_sides = [(e["a_fan_index"], e["a_fan_size"]) for e in data["edges"]]
    assert all(size == 2 for _, size in a_sides)


# ---- groups array ---------------------------------------------------------


def test_groups_array_empty_when_no_groups():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    data = build_nav_data(deck, _chunks_for("a"))
    assert data["groups"] == []


def test_groups_array_carries_label_and_slide_ids():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
        groups=(SlideGroup(label="My Group", slide_ids=("a", "b")),),
    )
    data = build_nav_data(deck, _chunks_for("a", "b"))
    assert len(data["groups"]) == 1
    g = data["groups"][0]
    assert g["label"] == "My Group"
    assert g["slide_ids"] == ["a", "b"]
    assert "color" not in g


def test_groups_array_includes_color_when_set():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(),
        groups=(SlideGroup(label="Colored", slide_ids=("a", "b"), color="#f5cba7"),),
    )
    data = build_nav_data(deck, _chunks_for("a", "b"))
    assert data["groups"][0]["color"] == "#f5cba7"
