import json
from pathlib import Path

import pytest

from scrolly.deck.model import Deck, Edge, Endpoint, Position, Side, Slide
from scrolly.render.assembler import assemble
from scrolly.slide.html import SlideHTML


@pytest.fixture(params=[True, False], ids=["inline", "no-inline"])
def inline(request):
    return request.param


def _single(id_: str, html: str) -> tuple[Deck, dict[str, SlideHTML]]:
    slide = Slide(id=id_, position=Position(0, 0), source=Path(f"/{id_}.slide.json"))
    deck = Deck(title="test", slides=(slide,), edges=())
    chunks = {id_: SlideHTML(title=id_.title(), html=html)}
    return deck, chunks


def _l_shape() -> tuple[Deck, dict[str, SlideHTML]]:
    intro = Slide(id="intro", position=Position(0, 0), source=Path("/intro.slide.json"))
    details = Slide(id="details", position=Position(1, 0), source=Path("/details.slide.json"))
    appendix = Slide(id="appendix", position=Position(1, 1), source=Path("/appendix.slide.json"))
    deck = Deck(
        title="L",
        slides=(intro, details, appendix),
        edges=(
            Edge(Endpoint("intro", Side.RIGHT), Endpoint("details", Side.LEFT)),
            Edge(Endpoint("details", Side.BOTTOM), Endpoint("appendix", Side.TOP)),
        ),
    )
    chunks = {
        "intro": SlideHTML(title="Intro", html="<h1>Intro</h1>"),
        "details": SlideHTML(title="Details", html="<h1>Details</h1>"),
        "appendix": SlideHTML(title="Appendix", html="<h1>Appendix</h1>"),
    }
    return deck, chunks


def test_assembler_produces_html5_doctype(inline):
    deck, chunks = _single("x", "<h1>X</h1>")
    html = assemble(deck, chunks, inline=inline)
    assert html.lstrip().startswith("<!DOCTYPE html>")


def test_assembler_includes_deck_title(inline):
    deck, chunks = _single("x", "")
    assert "<title>test</title>" in assemble(deck, chunks, inline=inline)


def test_assembler_uses_fallback_title_when_none(inline):
    slide = Slide(id="x", position=Position(0, 0), source=Path("/x.slide.json"))
    deck = Deck(title=None, slides=(slide,), edges=())
    chunks = {"x": SlideHTML(title="X", html="")}
    assert "<title>scrolly</title>" in assemble(deck, chunks, inline=inline)


def test_assembler_inlines_css_and_js_by_default():
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks)
    assert "<style>" in html
    assert ".canvas {" in html
    assert "<script>" in html
    assert 'href="canvas.css"' not in html
    assert 'src="canvas.js"' not in html


def test_assembler_links_canvas_assets_when_not_inline():
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks, inline=False)
    assert 'href="canvas.css"' in html
    assert 'src="canvas.js"' in html


def test_assembler_renders_every_slide_as_container(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    for slide_id in ("intro", "details", "appendix"):
        assert f'data-id="{slide_id}"' in html


def test_assembler_sets_per_slide_position_vars(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert "--cell-x: 1; --cell-y: 1" in html


def test_assembler_injects_each_slide_html(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert "<h1>Intro</h1>" in html
    assert "<h1>Details</h1>" in html
    assert "<h1>Appendix</h1>" in html


def test_assembler_embeds_nav_data_json(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    data = json.loads(blob)
    assert data["initial_slide"] == "intro"
    assert set(data["slides"]) == {"intro", "details", "appendix"}
    assert data["slides"]["intro"]["edges"] == {
        "right": [{"target": "details", "fan_index": 0, "fan_size": 1}],
    }


def test_scrollbar_in_navigation_scroll_ui(inline):
    # The scrollbar lives inside .scroll-ui in .navigation (single instance,
    # not per slide). JS manages its visibility based on selected slide state.
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert html.count('class="slide-scrollbar"') == 1
    assert html.count('class="slide-scrollbar-thumb"') == 1
    assert html.count('class="scroll-ui"') == 1


def test_nav_data_carries_per_slide_titles(inline):
    # Layer A surfaces titles in the navigation UI; the assembler propagates
    # each chunk's title into the embedded JSON blob.
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    data = json.loads(blob)
    assert data["slides"]["intro"]["title"] == "Intro"
    assert data["slides"]["details"]["title"] == "Details"
    assert data["slides"]["appendix"]["title"] == "Appendix"


def test_assembler_handles_empty_deck(inline):
    deck = Deck(title=None, slides=(), edges=())
    html = assemble(deck, {}, inline=inline)
    assert html.lstrip().startswith("<!DOCTYPE html>")


def _head_of(html: str) -> str:
    head_start = html.index("<head>")
    head_end = html.index("</head>", head_start)
    return html[head_start:head_end]


def test_scoped_css_emitted_in_head_when_chunk_carries_it(inline):
    # When a chunk's scoped_css is non-empty, the assembler emits a
    # <style> block in <head>. Per-slide-type CSS cascades from <head>
    # alongside canvas.css.
    slide = Slide(id="x", position=Position(0, 0), source=Path("/x.slide.json"))
    deck = Deck(title="t", slides=(slide,), edges=())
    chunks = {"x": SlideHTML(title="X", html="<p>x</p>", scoped_css=".x { color: red }")}
    html = assemble(deck, chunks, inline=inline)
    assert "<style>.x { color: red }</style>" in _head_of(html)


def test_scoped_css_dedup_across_chunks(inline):
    # Identical scoped_css across multiple chunks (e.g. all static
    # slides sharing one block) emits exactly once.
    a = Slide(id="a", position=Position(0, 0), source=Path("/a.slide.json"))
    b = Slide(id="b", position=Position(1, 0), source=Path("/b.slide.json"))
    deck = Deck(title="t", slides=(a, b), edges=())
    same_css = ".same { color: red }"
    chunks = {
        "a": SlideHTML(title="A", html="", scoped_css=same_css),
        "b": SlideHTML(title="B", html="", scoped_css=same_css),
    }
    html = assemble(deck, chunks, inline=inline)
    assert html.count(f"<style>{same_css}</style>") == 1


def test_scoped_css_ordering_is_first_occurrence_in_slide_order(inline):
    # Multiple unique scoped_css blocks emit in the order their
    # first-carrying chunk appears in deck.slides — stable across builds.
    a = Slide(id="a", position=Position(0, 0), source=Path("/a.slide.json"))
    b = Slide(id="b", position=Position(1, 0), source=Path("/b.slide.json"))
    deck = Deck(title="t", slides=(a, b), edges=())
    chunks = {
        "a": SlideHTML(title="A", html="", scoped_css=".A {}"),
        "b": SlideHTML(title="B", html="", scoped_css=".B {}"),
    }
    html = assemble(deck, chunks, inline=inline)
    a_pos = html.index("<style>.A {}</style>")
    b_pos = html.index("<style>.B {}</style>")
    assert a_pos < b_pos


def test_no_scoped_style_block_when_all_scoped_css_empty():
    deck, chunks = _l_shape()  # default SlideHTMLs have empty scoped_css
    html = assemble(deck, chunks, inline=False)
    assert "<style>" not in _head_of(html)


def test_navigation_layer_rendered_once(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    # The body-level navigation container hosts all nav chrome and is
    # a single instance regardless of slide count.
    assert html.count('class="navigation"') == 1


def test_zoom_out_control_rendered_once_in_navigation_layer(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    # One zoom-out control for the whole page (was: one per slide in v0.0.1).
    # Match the button-opening fragment so both the legacy icon and the
    # default mini-map (which carries a second class) count the same.
    assert html.count('<button type="button" class="zoom-out-control') == 1


def test_default_zoom_control_is_minimap_with_one_cell_per_slide():
    deck, chunks = _l_shape()
    html = assemble(deck, chunks)
    assert "zoom-out-control-minimap" in html
    assert html.count('<span class="minimap-cell"') == len(deck.slides)
    for slide in deck.slides:
        assert f'data-slide-id="{slide.id}"' in html


def test_simplified_zoom_control_flag_emits_legacy_icon():
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, simplified_zoom_control=True)
    # Inspect the rendered button, not the embedded stylesheet (which
    # always carries the `.zoom-out-control-minimap` selector).
    assert 'class="zoom-out-control zoom-out-control-minimap"' not in html
    assert 'class="minimap-cell"' not in html
    # Legacy chevron SVG is back.
    assert '<svg viewBox="0 0 24 24"' in html


def test_edge_arrows_not_in_static_html():
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=False)
    assert "edge-arrow edge-arrow-" not in html


def test_nav_data_still_carries_edges_for_js_to_consume():
    # The data contract for edge rendering lives in the embedded JSON blob.
    deck, chunks = _l_shape()
    html = assemble(deck, chunks)
    start = html.index('<script type="application/json" id="scrolly-deck">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    data = json.loads(blob)
    assert data["slides"]["intro"]["edges"] == {
        "right": [{"target": "details", "fan_index": 0, "fan_size": 1}],
    }
    assert data["slides"]["details"]["edges"] == {
        "left": [{"target": "intro", "fan_index": 0, "fan_size": 1}],
        "bottom": [{"target": "appendix", "fan_index": 0, "fan_size": 1}],
    }


def test_canvas_edges_svg_always_present(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert 'class="canvas-edges"' in html


def test_canvas_edges_svg_present_even_without_edges(inline):
    deck, chunks = _single("solo", "")
    html = assemble(deck, chunks, inline=inline)
    assert 'class="canvas-edges"' in html


def test_canvas_edges_svg_has_no_build_time_paths(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert 'class="canvas-edge"' not in html


def test_slide_container_omits_font_scale_for_default_chunk():
    # When chunk.font_scale == 1.0 (the default), no inline --font-scale
    # is emitted on .slide-container — the CSS fallback `var(--font-scale, 1)`
    # in `.chunk { font-size: ... }` handles it. Avoids HTML noise on the
    # common case.
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks, inline=False)
    assert "--font-scale" not in html


def test_slide_container_emits_font_scale_when_non_default():
    # When chunk.font_scale differs from 1.0, the assembler appends
    # --font-scale: <N>; to the slide-container's inline style. The CSS
    # rule `.chunk { font-size: calc(1rem * var(--font-scale, 1)) }`
    # consumes it.
    slide = Slide(id="big", position=Position(0, 0), source=Path("/big.slide.json"))
    deck = Deck(title="t", slides=(slide,), edges=())
    chunks = {"big": SlideHTML(title="Big", html="<p>x</p>", font_scale=1.4)}
    html = assemble(deck, chunks)
    assert "--font-scale: 1.4" in html


def test_slide_container_font_scale_isolated_per_slide():
    # A per-slide font_scale must not leak to other slides — each
    # slide-container gets its own inline-style decision based on its own
    # chunk's font_scale.
    intro = Slide(id="intro", position=Position(0, 0), source=Path("/intro.slide.json"))
    big = Slide(id="big", position=Position(1, 0), source=Path("/big.slide.json"))
    deck = Deck(title="t", slides=(intro, big), edges=())
    chunks = {
        "intro": SlideHTML(title="Intro", html=""),
        "big": SlideHTML(title="Big", html="", font_scale=2.0),
    }
    html = assemble(deck, chunks, inline=False)
    assert html.count("--font-scale") == 1
    assert "--font-scale: 2.0" in html


def test_canvas_edges_defs_emit_endpoint_dot_marker(inline):
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    assert '<marker id="edge-dot"' in html
    assert 'stroke-linecap="round"' in html
    assert 'vector-effect="non-scaling-stroke"' in html


def test_no_group_divs_in_template():
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks, inline=False)
    assert "slide-group" not in html


# ---- Help screen metadata --------------------------------------------------


def _extract_meta(html: str) -> dict:
    start = html.index('<script type="application/json" id="scrolly-meta">')
    end = html.index("</script>", start)
    blob = html[start:end].split(">", 1)[1]
    return json.loads(blob)


def test_meta_json_embedded(inline):
    # --- arrange / act ----------------------
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    meta = _extract_meta(html)

    # --- assert ------------------------------
    assert meta["version"]
    assert meta["author"]
    assert meta["pypi_url"].startswith("https://")


def test_meta_stats_slide_and_edge_counts(inline):
    # --- arrange / act ----------------------
    deck, chunks = _l_shape()
    meta = _extract_meta(assemble(deck, chunks, inline=inline))

    # --- assert ------------------------------
    assert meta["stats"]["slides"] == 3
    assert meta["stats"]["edges"] == 2


def test_meta_stats_file_size_is_integer(inline):
    # --- arrange / act ----------------------
    deck, chunks = _l_shape()
    html = assemble(deck, chunks, inline=inline)
    meta = _extract_meta(html)

    # --- assert ------------------------------
    assert isinstance(meta["stats"]["file_size"], int)
    assert meta["stats"]["file_size"] > 0


def test_meta_stats_payloads_shape_from_bundle():
    # --- arrange ----------------------------
    from scrolly.pipeline._bundler import BundleStats

    deck, chunks = _single("x", "")
    bundle_stats = BundleStats(
        text_targets=2,
        text_payloads=1,
        blob_targets_by_mime={"image/svg+xml": 3, "image/png": 1},
        blob_payloads_by_mime={"image/svg+xml": 2, "image/png": 1},
        baseline_bytes=10_000,
        compressed_bytes=7_500,
        compressed=True,
    )

    # --- act --------------------------------
    meta = _extract_meta(assemble(deck, chunks, bundle_stats=bundle_stats))

    # --- assert ------------------------------
    payloads = meta["stats"]["payloads"]
    # Per-extension counts, mime → extension mapping applied.
    assert payloads["total"] == {".html": 2, ".svg": 3, ".png": 1}
    assert payloads["unique"] == {".html": 1, ".svg": 2, ".png": 1}
    assert payloads["compressed"] is True
    assert payloads["bytes_saved"] == 2_500


def test_meta_stats_payloads_when_compressed_false():
    # --- arrange ----------------------------
    from scrolly.pipeline._bundler import BundleStats

    deck, chunks = _single("x", "")
    bundle_stats = BundleStats(
        text_targets=1,
        text_payloads=1,
        blob_targets_by_mime={},
        blob_payloads_by_mime={},
        baseline_bytes=2_000,
        compressed_bytes=0,
        compressed=False,
    )

    # --- act --------------------------------
    meta = _extract_meta(assemble(deck, chunks, bundle_stats=bundle_stats))

    # --- assert ------------------------------
    payloads = meta["stats"]["payloads"]
    # Total + unique still populated (deck has 1 iframe) even though the
    # bundle wasn't emitted.
    assert payloads["total"] == {".html": 1}
    assert payloads["unique"] == {".html": 1}
    assert payloads["compressed"] is False
    # Space saved is zero when nothing was compressed.
    assert payloads["bytes_saved"] == 0


def test_meta_stats_payloads_empty_when_no_bundler(inline):
    # --- arrange / act ----------------------
    # `bundle_stats=None` is the inline=False case (orchestrator skips the
    # bundler entirely) — meta payloads must still be present and well-formed.
    deck, chunks = _single("x", "")
    meta = _extract_meta(assemble(deck, chunks, inline=inline))

    # --- assert ------------------------------
    payloads = meta["stats"]["payloads"]
    assert payloads == {"total": {}, "unique": {}, "compressed": False, "bytes_saved": 0}


def test_help_button_in_navigation(inline):
    # --- arrange / act ----------------------
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks, inline=inline)

    # --- assert ------------------------------
    assert 'class="help-button"' in html


def test_help_modal_in_output(inline):
    # --- arrange / act ----------------------
    deck, chunks = _single("x", "")
    html = assemble(deck, chunks, inline=inline)

    # --- assert ------------------------------
    assert 'class="help-modal"' in html
    assert 'class="help-modal-ok"' in html


def test_meta_mermaid_version_null_when_no_mermaid(inline):
    # --- arrange / act ----------------------
    deck, chunks = _single("x", "")
    meta = _extract_meta(assemble(deck, chunks, inline=inline))

    # --- assert ------------------------------
    assert meta["stats"]["mermaid_version"] is None


def test_meta_mermaid_version_populated_when_mermaid_provided(inline):
    # --- arrange ----------------------------
    from scrolly.render.bundled_assets import MermaidAsset

    deck, chunks = _single("x", "")
    mermaid = MermaidAsset(name="mermaid.min.js", content=b"<<bytes>>", version="11.15.0", source="bundled")

    # --- act --------------------------------
    meta = _extract_meta(assemble(deck, chunks, inline=inline, mermaid=mermaid))

    # --- assert ------------------------------
    assert meta["stats"]["mermaid_version"] == "11.15.0"
