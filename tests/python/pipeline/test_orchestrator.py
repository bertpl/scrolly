from pathlib import Path

import pytest

from scrolly.errors import ScrollyError
from scrolly.pipeline.orchestrator import build_deck, validate_deck_sources
from tests.python.conftest import PROJECT_ROOT

EXAMPLES_DIR = PROJECT_ROOT / "examples"


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
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# Only\n\nhello")

    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        '{ title: "tiny", slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }'
    )

    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    assert deck.title == "tiny"
    html = (out / "index.html").read_text()
    assert "<h1>Only</h1>" in html
    assert "<title>tiny</title>" in html
    assert 'data-id="only"' in html
    # SlideHTML-extracted title (from the H1) lands in the embedded nav-data JSON.
    assert '"title": "Only"' in html


def test_builds_multi_slide_deck(tmp_path):
    (tmp_path / "a.static.md").write_text("---\ninitial_scroll_position: 0\n---\n# A")
    (tmp_path / "b.static.md").write_text("---\ninitial_scroll_position: 0\n---\n# B")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text(
        "{ slides: ["
        '{ id: "a", position: [0, 0], source: "a.static.md" },'
        '{ id: "b", position: [1, 0], source: "b.static.md" }'
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
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# x")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }')

    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.txt").write_text("leftover")

    with pytest.raises(ScrollyError, match="not empty"):
        build_deck(deck_file, out)


def test_worked_example_long_bg_slide_is_content_driven(tmp_path):
    # The long-bg slide added in v0.0.5 M4 exercises content-driven scroll
    # end-to-end: its rendered chunk content reaches the HTML, and the
    # embedded nav-data marks scroll_range: null so canvas.js's
    # ResizeObserver path activates.
    deck_file = EXAMPLES_DIR / "worked-example" / "deck.deck.json"
    out = tmp_path / "dist"
    deck = build_deck(deck_file, out)

    assert any(s.id == "long-bg" for s in deck.slides)

    html = (out / "index.html").read_text()
    # A line of body content from long-bg should land in the rendered HTML.
    assert "Why content-driven scroll" in html
    # And the nav-data entry for long-bg carries a null scroll_range.
    import json

    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    data = json.loads(blob)
    assert data["slides"]["long-bg"]["scroll_range"] is None
    assert data["slides"]["long-bg"]["scroll_speed"] == 1.0


# ---------------------------------------------------------------------------
# validate_deck_sources
# ---------------------------------------------------------------------------
def test_validate_deck_sources_on_worked_example():
    deck_file = EXAMPLES_DIR / "worked-example" / "deck.deck.json"
    deck = validate_deck_sources(deck_file)
    assert len(deck.slides) == 18
    assert len(deck.edges) == 21


def test_validate_deck_sources_on_minimal_deck(tmp_path):
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# Only\n")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }')
    deck = validate_deck_sources(deck_file)
    assert len(deck.slides) == 1


def test_validate_deck_sources_rejects_missing_slide(tmp_path):
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "gone", position: [0, 0], source: "nonexistent.static.md" }], edges: [] }')
    with pytest.raises(ScrollyError):
        validate_deck_sources(deck_file)


def test_validate_deck_sources_rejects_invalid_slide_content(tmp_path):
    slide = tmp_path / "bad.static.md"
    slide.write_text("no frontmatter here")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "bad", position: [0, 0], source: "bad.static.md" }], edges: [] }')
    with pytest.raises(ScrollyError):
        validate_deck_sources(deck_file)


def test_build_force_overwrites_non_empty_out_dir(tmp_path):
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# x")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }')

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
    slide_src = tmp_path / "only.scrollimation.json"
    iframe_html = "<!doctype html><p>some compressible iframe content</p>" * 30
    import json as _json

    slide_src.write_text(
        '{\n  title: "T", scroll_range: 100,\n  elements: [\n'
        f"    {{ iframe_html: {_json.dumps(iframe_html)}, position: [10, 10], width: 80, height: 80 }},\n"
        "  ],\n}\n"
    )
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.scrollimation.json" }], edges: [] }')
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


def test_static_only_deck_emits_no_bundle_script(tmp_path):
    # A static-only deck has no compressible payloads, so the bundler has
    # nothing to register and the script tag is not emitted.
    slide = tmp_path / "only.static.md"
    slide.write_text("---\ninitial_scroll_position: 0\n---\n# A\n\nsome body text")
    deck_file = tmp_path / "deck.deck.json"
    deck_file.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.static.md" }], edges: [] }')

    out = tmp_path / "dist"
    build_deck(deck_file, out)

    html = (out / "index.html").read_text()
    assert _BUNDLE_TAG not in html
