"""Guard the Python↔JS contract: the keys ``canvas.js`` reads must match
what the Python emitters produce.

``canvas.js`` consumes three Python-emitted structures whose source it
never sees — the embedded ``#scrolly-deck`` JSON (``build_nav_data``), the
``#scrolly-meta`` block (``_build_meta``), and the payload manifest
(``PayloadBundler.manifest_and_stream``). The Vitest suite builds
*synthetic* inputs "the way Python would", so nothing else asserts
the two sides agree. These tests pin the emitted key-sets against the
contract the JS reader depends on, so a Python-side rename / add / drop
trips CI here.

When one of these fails, update **both** the Python emitter and the
matching ``canvas.js`` reader (and the documented shape) in lockstep —
the test is a tripwire for silent drift, not a spec to edit blindly.
"""

from __future__ import annotations

import json
from pathlib import Path

from scrolly.deck.model import Deck, Edge, Endpoint, Position, Side, Slide, SlideGroup
from scrolly.pipeline._bundler import PayloadBundler
from scrolly.render.assembler import _build_meta
from scrolly.render.nav_data import build_nav_data
from scrolly.slide.html import SlideHTML

# --- expected key-sets (the contract canvas.js reads) -----------------------
# #scrolly-deck — read by canvas.js's `deck` / `s` / edge / group consumers.
_NAV_TOP = {"initial_slide", "fan_spacing_factor", "slides", "edges", "groups"}
_NAV_SLIDE = {
    "title",
    "position",
    "scroll_range",
    "scroll_speed",
    "initial_scroll_position",
    "snap_positions",
    "reverse",
    "edges",
}
_NAV_SIDE_EDGE = {"target", "fan_index", "fan_size"}
_NAV_FLAT_EDGE = {
    "a_slide",
    "a_side",
    "a_fan_index",
    "a_fan_size",
    "b_slide",
    "b_side",
    "b_fan_index",
    "b_fan_size",
}
_NAV_GROUP_REQUIRED = {"label", "slide_ids", "label_color"}
_NAV_GROUP_OPTIONAL = {"color"}  # emitted only when the group sets a color

# #scrolly-meta — read by the help-modal `populate()` in canvas.js.
_META_TOP = {"version", "author", "pypi_url", "stats"}
_META_STATS = {"slides", "edges", "payloads", "mermaid_version", "file_size"}
_META_PAYLOADS = {"total", "unique", "compressed", "bytes_saved"}

# payload manifest — read by `mapBundleAssignments()` in canvas.js.
_MANIFEST_TOP = {"payloads", "targets"}
_MANIFEST_PAYLOAD_REQUIRED = {"mode", "length"}
_MANIFEST_PAYLOAD_OPTIONAL = {"mime"}  # blob payloads only
_MANIFEST_TARGET = {"id", "attr", "payload"}


def _assert_keys(actual: dict, *, required: set[str], optional: set[str] = frozenset(), where: str) -> None:
    """Assert ``actual``'s keys sit within ``required | optional`` and cover ``required``."""
    keys = set(actual)
    unexpected = keys - (required | optional)
    missing = required - keys
    assert not unexpected, f"{where}: unexpected key(s) {unexpected} — Python emits a field canvas.js does not read"
    assert not missing, f"{where}: missing key(s) {missing} — Python dropped a field canvas.js reads"


def _contract_deck() -> tuple[Deck, dict[str, SlideHTML]]:
    """A small deck exercising every contract surface: an edge and a colored group."""
    a = Slide(id="a", position=Position(0, 0), source=Path("/a.slide.json"))
    b = Slide(id="b", position=Position(1, 0), source=Path("/b.slide.json"))
    deck = Deck(
        title="contract",
        slides=(a, b),
        edges=(Edge(Endpoint("a", Side.RIGHT), Endpoint("b", Side.LEFT)),),
        groups=(SlideGroup(label="G", slide_ids=("a", "b"), color="#abcdef"),),
    )
    chunks = {
        "a": SlideHTML(title="A", html="", scroll_range=1000, snap_positions=(0, 500)),
        "b": SlideHTML(title="B", html=""),
    }
    return deck, chunks


# ==================================================================================================
#  #scrolly-deck — build_nav_data
# ==================================================================================================
def test_nav_data_top_level_keys() -> None:
    # --- arrange / act ----------------
    data = build_nav_data(*_contract_deck())

    # --- assert -----------------------
    assert set(data) == _NAV_TOP


def test_nav_data_per_slide_keys() -> None:
    # --- arrange / act ----------------
    data = build_nav_data(*_contract_deck())

    # --- assert -----------------------
    for sid, entry in data["slides"].items():
        _assert_keys(entry, required=_NAV_SLIDE, where=f"slide '{sid}'")


def test_nav_data_edge_keys() -> None:
    # --- arrange / act ----------------
    data = build_nav_data(*_contract_deck())

    # --- assert -----------------------
    for sid, entry in data["slides"].items():
        for side, edges in entry["edges"].items():
            for edge in edges:
                _assert_keys(edge, required=_NAV_SIDE_EDGE, where=f"slide '{sid}' side '{side}'")
    assert data["edges"], "fixture should declare at least one edge"
    for edge in data["edges"]:
        _assert_keys(edge, required=_NAV_FLAT_EDGE, where="flat edge")


def test_nav_data_group_keys() -> None:
    # --- arrange / act ----------------
    data = build_nav_data(*_contract_deck())

    # --- assert -----------------------
    assert data["groups"], "fixture should declare a group"
    for group in data["groups"]:
        _assert_keys(group, required=_NAV_GROUP_REQUIRED, optional=_NAV_GROUP_OPTIONAL, where="group")
    assert "color" in data["groups"][0], "colored fixture group must carry the optional 'color' key"


# ==================================================================================================
#  #scrolly-meta — _build_meta
# ==================================================================================================
def test_meta_keys() -> None:
    # --- arrange / act ----------------
    meta = _build_meta(*_contract_deck())

    # --- assert -----------------------
    assert set(meta) == _META_TOP
    _assert_keys(meta["stats"], required=_META_STATS, where="meta.stats")
    _assert_keys(meta["stats"]["payloads"], required=_META_PAYLOADS, where="meta.stats.payloads")


# ==================================================================================================
#  payload manifest — PayloadBundler.manifest_and_stream
# ==================================================================================================
def test_manifest_keys() -> None:
    # --- arrange ----------------------
    bundler = PayloadBundler()
    text = b"<p>" + b"a" * 1000 + b"</p>"
    blob = b"\x89PNG\r\n" + b"\x00" * 1000
    bundler.add(payload=text, mode="text", attr="srcdoc", baseline_len=len(text))
    bundler.add(payload=blob, mode="blob", attr="src", mime="image/png", baseline_len=len(blob))

    # --- act --------------------------
    manifest = json.loads(bundler.manifest_and_stream()[0])

    # --- assert -----------------------
    assert set(manifest) == _MANIFEST_TOP
    for payload in manifest["payloads"]:
        _assert_keys(
            payload, required=_MANIFEST_PAYLOAD_REQUIRED, optional=_MANIFEST_PAYLOAD_OPTIONAL, where="manifest payload"
        )
    for target in manifest["targets"]:
        _assert_keys(target, required=_MANIFEST_TARGET, where="manifest target")
    by_mode = {payload["mode"]: payload for payload in manifest["payloads"]}
    assert "mime" not in by_mode["text"], "text payloads must omit mime"
    assert by_mode["blob"]["mime"] == "image/png", "blob payloads must carry mime"
