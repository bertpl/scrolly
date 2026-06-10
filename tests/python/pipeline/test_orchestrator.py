from pathlib import Path

import pytest

from scrolly.errors import ScrollyError
from scrolly.pipeline.loader import load_deck
from scrolly.pipeline.orchestrator import build_deck
from tests.python.conftest import PROJECT_ROOT

EXAMPLES_DIR = PROJECT_ROOT / "examples"


def _markdown_slide(title: str, body: str) -> str:
    """Build a minimal ``.slide.json`` source for a single markdown element."""
    import json as _json

    return (
        "{\n"
        f"  title: {_json.dumps(title)},\n"
        "  elements: [\n"
        f'    {{ markdown: {_json.dumps(body)}, position: [0, 0], width: 100, height: "auto" }},\n'
        "  ],\n"
        "}\n"
    )


def _find_example_decks() -> list[Path]:
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*/deck.deck.json"))


@pytest.mark.parametrize("deck_file", _find_example_decks(), ids=lambda p: p.parent.name)
def test_example_deck_builds(deck_file, tmp_path):
    """Parametrized e2e smoke: every deck under examples/ must build cleanly."""
    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    index = out / "index.html"
    assert index.exists()
    # Inline mode (default): no separate CSS/JS files.
    assert not (out / "canvas.css").exists()
    assert not (out / "canvas.js").exists()

    html = index.read_text()
    # CSS and JS are inlined.
    assert "<style>" in html
    assert ".canvas {" in html

    for slide in deck.slides:
        assert f'data-id="{slide.id}"' in html

    assert html.count('class="navigation"') == 1
    # Exactly one zoom-out control (either the legacy icon or the default
    # mini-map variant — the latter also carries a second class). Match
    # the button-opening fragment so both variants count the same.
    assert html.count('<button type="button" class="zoom-out-control') == 1

    assert 'class="canvas-edges"' in html

    if deck.title:
        assert deck.title in html


def test_builds_a_minimal_in_memory_deck(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("Only", "# Only\n\nhello"))

    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ title: "tiny", slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }'
    )

    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    assert deck.title == "tiny"
    html = (out / "index.html").read_text()
    assert "<h1>Only</h1>" in html
    assert "<title>tiny</title>" in html
    assert 'data-id="only"' in html
    assert '"title": "Only"' in html


def test_builds_multi_slide_deck(tmp_path):
    (tmp_path / "a.slide.json").write_text(_markdown_slide("A", "# A"))
    (tmp_path / "b.slide.json").write_text(_markdown_slide("B", "# B"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        "{ slides: ["
        '{ id: "a", position: [0, 0], source: "a.slide.json" },'
        '{ id: "b", position: [1, 0], source: "b.slide.json" }'
        '], edges: [["a|right", "b|left"]] }'
    )

    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    assert len(deck.slides) == 2
    html = (out / "index.html").read_text()
    assert "<h1>A</h1>" in html
    assert "<h1>B</h1>" in html
    assert 'data-id="a"' in html
    assert 'data-id="b"' in html


def test_builds_negative_coordinate_deck(tmp_path):
    # Off-origin decks with negative row/column indices must build and carry
    # their negative positions through to the embedded nav-data unchanged.
    # The geometry that consumes them lives in canvas.js; the Python layer
    # (parser, validator, inference, assembler) must simply accept and pass
    # them along, with edge sides inferred from the relative positions.
    import json

    (tmp_path / "a.slide.json").write_text(_markdown_slide("A", "# A"))
    (tmp_path / "b.slide.json").write_text(_markdown_slide("B", "# B"))
    (tmp_path / "c.slide.json").write_text(_markdown_slide("C", "# C"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        "{ slides: ["
        '{ id: "a", position: [-1, -1], source: "a.slide.json" },'
        '{ id: "b", position: [0, -1], source: "b.slide.json" },'
        '{ id: "c", position: [0, 0], source: "c.slide.json" }'
        '], edges: [["a", "b"], ["b", "c"]] }'
    )

    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    # Positions survive parse + inference unchanged.
    assert {s.id: (s.position.x, s.position.y) for s in deck.slides} == {
        "a": (-1, -1),
        "b": (0, -1),
        "c": (0, 0),
    }

    html = (out / "index.html").read_text()
    # The slide container carries the raw (negative) cell coordinates.
    assert "--cell-x: -1; --cell-y: -1;" in html

    # nav-data carries the negative positions verbatim, and edge sides were
    # inferred from the relative negative positions (a → right → b; b is
    # above c, so b → bottom → c).
    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    data = json.loads(html[start:end].split(">", 1)[1])
    assert data["slides"]["a"]["position"] == [-1, -1]
    assert data["slides"]["b"]["position"] == [0, -1]
    assert data["slides"]["c"]["position"] == [0, 0]
    assert data["slides"]["a"]["edges"]["right"][0]["target"] == "b"
    assert data["slides"]["b"]["edges"]["bottom"][0]["target"] == "c"


def test_build_surfaces_unknown_slide_type(tmp_path):
    # Source filename uses an unregistered suffix; dispatch fails.
    slide = tmp_path / "only.totally-unknown.xyz"
    slide.write_text("anything")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ slides: [{ id: "only", position: [0, 0], source: "only.totally-unknown.xyz" }], edges: [] }'
    )

    with pytest.raises(ScrollyError):
        build_deck(deck_file, tmp_path / "out")


def test_build_refuses_to_clobber_without_force(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("x", "# x"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')

    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")

    with pytest.raises(ScrollyError, match="not empty"):
        build_deck(deck_file, out)


def test_regression_deck_reference_slide_is_content_driven(tmp_path):
    # The reference slide exercises content-driven scroll end-to-end:
    # its rendered chunk content reaches the HTML, and the embedded
    # nav-data marks scroll_range: null so canvas.js's ResizeObserver
    # path activates.
    deck_file = EXAMPLES_DIR / "_regression" / "deck.deck.json"
    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    assert any(s.id == "reference" for s in deck.slides)

    html = (out / "index.html").read_text()
    # A line of body content from the reference slide should land in the rendered HTML.
    assert "Every factual claim" in html
    # And the nav-data entry for reference carries a null scroll_range.
    import json

    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    data = json.loads(blob)
    assert data["slides"]["reference"]["scroll_range"] is None
    assert data["slides"]["reference"]["scroll_speed"] == 1.0


# ==================================================================================================
#  load_deck
# ==================================================================================================
def test_load_deck_on_regression_deck():
    deck_file = EXAMPLES_DIR / "_regression" / "deck.deck.json"
    deck, slide_irs = load_deck(deck_file)
    assert len(deck.slides) == 19
    assert len(deck.edges) == 19
    assert set(slide_irs.keys()) == {s.id for s in deck.slides}


def test_load_deck_on_minimal_deck(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("Only", "# Only"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
    deck, slide_irs = load_deck(deck_file)
    assert len(deck.slides) == 1
    assert list(slide_irs.keys()) == ["only"]


def test_load_deck_rejects_missing_slide(tmp_path):
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "gone", position: [0, 0], source: "nonexistent.slide.json" }], edges: [] }')
    with pytest.raises(ScrollyError):
        load_deck(deck_file)


def test_load_deck_rejects_invalid_slide_content(tmp_path):
    slide = tmp_path / "bad.slide.json"
    slide.write_text("this is not JSON5")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "bad", position: [0, 0], source: "bad.slide.json" }], edges: [] }')
    with pytest.raises(ScrollyError):
        load_deck(deck_file)


def test_build_force_overwrites_non_empty_out_dir(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("x", "# x"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')

    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")

    build_deck(deck_file, out, force=True)
    assert (out / "index.html").exists()


# ==================================================================================================
#  Compressed payload bundle (end-to-end)
# ==================================================================================================
def _deck_with_iframe(tmp_path: Path) -> Path:
    """Write a one-slide deck whose only element is a sizable iframe payload."""
    slide_src = tmp_path / "only.slide.json"
    iframe_html = "<!doctype html><p>some compressible iframe content</p>" * 30
    import json as _json

    slide_src.write_text(
        '{\n  title: "T", scroll_range: 100,\n  elements: [\n'
        f"    {{ iframe_html: {_json.dumps(iframe_html)}, position: [10, 10], width: 80, height: 80 }},\n"
        "  ],\n}\n"
    )
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
    return deck_file


def test_compressed_bundle_emits_single_script_tag(tmp_path):
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out)

    html = (out / "index.html").read_text()
    assert html.count('id="scrolly-compressed-payload"') == 1
    # The compressed iframe carries a target marker, no inline srcdoc.
    assert "data-scrolly-target=" in html
    assert "srcdoc=" not in html


def test_compressed_bundle_roundtrips_byte_for_byte(tmp_path):
    import base64
    import gzip
    import json as _json
    import re

    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out)

    html = (out / "index.html").read_text()
    match = re.search(
        r'<script type="application/json" id="scrolly-compressed-payload">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    bundle = _json.loads(match.group(1))

    raw = gzip.decompress(base64.b64decode(bundle["blob"]))
    offset = 0
    for entry in bundle["payloads"]:
        chunk = raw[offset : offset + entry["length"]]
        offset += entry["length"]
        if entry["mode"] == "text":
            # Text payload should decode to the source iframe HTML.
            assert chunk.decode("utf-8").startswith("<!doctype html>")
    assert offset == len(raw)


_BUNDLE_TAG = '<script type="application/json" id="scrolly-compressed-payload">'


def test_no_compress_skips_bundle_script(tmp_path):
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out, compress=False)

    html = (out / "index.html").read_text()
    assert _BUNDLE_TAG not in html
    assert "<iframe srcdoc=" in html
    assert "<iframe data-scrolly-target" not in html


def test_inline_false_skips_bundle_script(tmp_path):
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out, inline=False)

    html = (out / "index.html").read_text()
    assert _BUNDLE_TAG not in html
    assert "<iframe data-scrolly-target" not in html


def test_markdown_only_deck_emits_no_bundle_script(tmp_path):
    # A markdown-only deck has no compressible payloads, so the bundler
    # has nothing to register and the script tag is not emitted.
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("A", "# A\n\nsome body text"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')

    out = tmp_path / "dist"
    build_deck(deck_file, out)

    html = (out / "index.html").read_text()
    assert _BUNDLE_TAG not in html


def _extract_meta_payloads(out: Path) -> dict:
    """Pull stats.payloads from the help-screen meta JSON in the rendered HTML."""
    import json as _json
    import re

    html = (out / "index.html").read_text()
    match = re.search(
        r'<script type="application/json" id="scrolly-meta">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return _json.loads(match.group(1))["stats"]["payloads"]


def test_meta_payloads_with_compression(tmp_path):
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out)  # compress=True (default)

    payloads = _extract_meta_payloads(out)
    assert payloads["total"] == {".html": 1}
    assert payloads["unique"] == {".html": 1}
    assert payloads["compressed"] is True
    assert payloads["bytes_saved"] > 0


def test_meta_payloads_no_compress_still_counts_iframes(tmp_path):
    # Always-on bundler means iframe counts surface in the help screen
    # even when no compression is emitted.
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out, compress=False)

    payloads = _extract_meta_payloads(out)
    assert payloads["total"] == {".html": 1}
    assert payloads["unique"] == {".html": 1}
    assert payloads["compressed"] is False
    assert payloads["bytes_saved"] == 0


def test_meta_payloads_inline_false_has_empty_counts(tmp_path):
    deck_file = _deck_with_iframe(tmp_path)
    out = tmp_path / "dist"
    build_deck(deck_file, out, inline=False)

    payloads = _extract_meta_payloads(out)
    assert payloads == {"total": {}, "unique": {}, "compressed": False, "bytes_saved": 0}


def test_meta_payloads_markdown_only_deck(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("A", "# A\n\nbody"))
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
    out = tmp_path / "dist"
    build_deck(deck_file, out)

    payloads = _extract_meta_payloads(out)
    assert payloads == {"total": {}, "unique": {}, "compressed": False, "bytes_saved": 0}


def test_build_deck_with_custom_out_file(tmp_path):
    slide = tmp_path / "only.slide.json"
    slide.write_text(_markdown_slide("Only", "# Only\n\nhello"))

    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ title: "tiny", slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }'
    )

    out = tmp_path / "dist"
    build_deck(deck_file, out, out_file="deck.html")

    assert (out / "deck.html").exists()
    assert not (out / "index.html").exists()
