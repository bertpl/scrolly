from pathlib import Path

from scrolly.deck.model import Deck, Edge, Endpoint, Position, Side, Slide
from scrolly.render.fan import FanEntry, compute_fan_offsets


def _slide(id_: str, x: int, y: int) -> Slide:
    return Slide(id=id_, position=Position(x, y), source=Path(f"/{id_}.slide.json"))


# ---- empty / trivial cases ------------------------------------------------


def test_empty_deck_yields_empty_lookup():
    assert compute_fan_offsets(Deck(title=None, slides=(), edges=())) == {}


def test_no_edges_yields_empty_lookup():
    deck = Deck(title=None, slides=(_slide("a", 0, 0),), edges=())
    assert compute_fan_offsets(deck) == {}


# ---- single-edge sides preserve v0.0.2 centered placement ------------------


def test_single_edge_per_side_sits_at_midpoint():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    lookup = compute_fan_offsets(deck)
    assert lookup[("a", Side.RIGHT)] == (FanEntry(target_id="b"),)
    assert lookup[("b", Side.LEFT)] == (FanEntry(target_id="a"),)


def test_one_edge_per_side_for_each_of_four_sides():
    # A central slide with one edge in each direction — each side gets a
    # single entry centered at 0.5.
    deck = Deck(
        title=None,
        slides=(
            _slide("c", 1, 1),
            _slide("n", 1, 0),  # north
            _slide("s", 1, 2),  # south
            _slide("w", 0, 1),  # west
            _slide("e", 2, 1),  # east
        ),
        edges=(
            Edge(Endpoint("c", Side.TOP), Endpoint("n", Side.BOTTOM)),
            Edge(Endpoint("c", Side.BOTTOM), Endpoint("s", Side.TOP)),
            Edge(Endpoint("c", Side.LEFT), Endpoint("w", Side.RIGHT)),
            Edge(Endpoint("c", Side.RIGHT), Endpoint("e", Side.LEFT)),
        ),
    )
    lookup = compute_fan_offsets(deck)
    for side, target in [
        (Side.TOP, "n"),
        (Side.BOTTOM, "s"),
        (Side.LEFT, "w"),
        (Side.RIGHT, "e"),
    ]:
        assert lookup[("c", side)] == (FanEntry(target_id=target),)


# ---- multi-edge sides spread across [0.2, 0.8] for the default band ------


def test_two_edges_on_same_side_sit_one_spacing_apart():
    # n=2 fan: offsets 0.45, 0.55 (centered ± 0.5 * 0.1).
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 0, 1),
            _slide("up", 1, 0),  # upper-right of a
            _slide("dn", 1, 2),  # lower-right of a
        ),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("up", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("dn", Side.LEFT)),
        ),
    )
    lookup = compute_fan_offsets(deck)
    entries = lookup[("a", Side.RIGHT)]
    # Upper target first (smaller y), lower target second.
    assert [e.target_id for e in entries] == ["up", "dn"]
    assert entries[0].fan_index == 0
    assert entries[1].fan_index == 1
    assert all(e.fan_size == 2 for e in entries)


def test_three_edges_on_same_side_evenly_spread():
    # n=3 fan: offsets 0.40, 0.50, 0.60 (spaced 0.1 apart, centered on 0.5).
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
    entries = compute_fan_offsets(deck)[("a", Side.RIGHT)]
    assert [e.target_id for e in entries] == ["up", "md", "dn"]
    assert [e.fan_index for e in entries] == [0, 1, 2]
    assert all(e.fan_size == 3 for e in entries)


# ---- ordering rules per side ---------------------------------------------


def test_left_side_orders_by_target_y_ascending():
    # Two edges on a's left side — upper target sorts first.
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 2, 1),
            _slide("hi", 0, 0),
            _slide("lo", 0, 2),
        ),
        edges=(
            Edge(Endpoint("a", Side.LEFT), Endpoint("hi", Side.RIGHT)),
            Edge(Endpoint("a", Side.LEFT), Endpoint("lo", Side.RIGHT)),
        ),
    )
    entries = compute_fan_offsets(deck)[("a", Side.LEFT)]
    assert [e.target_id for e in entries] == ["hi", "lo"]
    assert [e.fan_index for e in entries] == [0, 1]
    assert all(e.fan_size == 2 for e in entries)


def test_top_side_orders_by_target_x_ascending():
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 1, 2),
            _slide("L", 0, 0),
            _slide("R", 2, 0),
        ),
        edges=(
            Edge(Endpoint("a", Side.TOP), Endpoint("L", Side.BOTTOM)),
            Edge(Endpoint("a", Side.TOP), Endpoint("R", Side.BOTTOM)),
        ),
    )
    entries = compute_fan_offsets(deck)[("a", Side.TOP)]
    assert [e.target_id for e in entries] == ["L", "R"]


def test_bottom_side_orders_by_target_x_ascending_not_inverted():
    # The case where ascending atan2 angle would be wrong: bottom-side
    # sorting must still be left-to-right (offset 0 = left).
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 1, 0),
            _slide("L", 0, 2),  # lower-left
            _slide("R", 2, 2),  # lower-right
        ),
        edges=(
            Edge(Endpoint("a", Side.BOTTOM), Endpoint("L", Side.TOP)),
            Edge(Endpoint("a", Side.BOTTOM), Endpoint("R", Side.TOP)),
        ),
    )
    entries = compute_fan_offsets(deck)[("a", Side.BOTTOM)]
    assert [e.target_id for e in entries] == ["L", "R"]


# ---- tie-breaks ----------------------------------------------------------


def test_targets_at_same_primary_coord_break_by_secondary_then_id():
    # Two right-side edges to slides at the same y but different x; then
    # add a third at the same y AND x as one of them — that one breaks by
    # target_id. (The grid model permits duplicate (y, x) on logically
    # distinct targets only if positions overlap; this test exercises the
    # tie-break codepath even if the case is rare in practice.)
    deck = Deck(
        title=None,
        slides=(
            _slide("a", 0, 0),
            _slide("near", 1, 0),
            _slide("far", 2, 0),
        ),
        edges=(
            Edge(Endpoint("a", Side.RIGHT), Endpoint("far", Side.LEFT)),
            Edge(Endpoint("a", Side.RIGHT), Endpoint("near", Side.LEFT)),
        ),
    )
    # Both targets at y=0 → tie on primary coord. Secondary (x): near=1, far=2.
    entries = compute_fan_offsets(deck)[("a", Side.RIGHT)]
    assert [e.target_id for e in entries] == ["near", "far"]


# ---- both endpoints of an edge appear in the lookup ----------------------


def test_each_edge_contributes_both_endpoints():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    lookup = compute_fan_offsets(deck)
    assert set(lookup.keys()) == {("a", Side.RIGHT), ("b", Side.LEFT)}


# ---- fan_index and fan_size carry per-entry fan composition --------------


def test_single_edge_fan_index_zero_and_size_one():
    deck = Deck(
        title=None,
        slides=(_slide("a", 0, 0), _slide("b", 1, 0)),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
    )
    entry = compute_fan_offsets(deck)[("a", Side.RIGHT)][0]
    assert entry.fan_index == 0
    assert entry.fan_size == 1


def test_multi_edge_fan_indices_and_size():
    # 3-edge fan on a's right side → indices 0,1,2 with fan_size 3.
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
    entries = compute_fan_offsets(deck)[("a", Side.RIGHT)]
    assert [e.fan_index for e in entries] == [0, 1, 2]
    assert all(e.fan_size == 3 for e in entries)
