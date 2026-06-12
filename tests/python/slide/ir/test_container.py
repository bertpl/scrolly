"""Tests for the ``container`` element — parsing, validation, includes, rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly._shared.paths import confine_paths
from scrolly.errors import SlideSourceError
from scrolly.slide.ir import ContainerElement
from scrolly.slide.ir.slide import SlideIR
from scrolly.slide.renderers.slide import SlideRenderer


def _write(path: Path, text: str) -> Path:
    """Write ``text`` to ``path`` (creating parents) and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _slide(elements_json5: str) -> str:
    """Wrap an elements array body in a minimal slide source."""
    return f'{{ title: "T", scroll_range: 100, elements: [{elements_json5}] }}'


# ── Parsing and defaults ─────────────────────────────────────────


def test_container_parses_with_full_slide_defaults(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ container: [{ markdown: "# Hi", position: [5, 33], width: 80 }] }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)
    ctr = ir.elements[0]

    # --- assert -----------------------
    assert isinstance(ctr, ContainerElement)
    assert ctr.position.static_value == (0.0, 0.0)
    assert ctr.width.static_value == 100.0
    assert ctr.height.static_value == 100.0
    assert len(ctr.container) == 1


def test_container_nests(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            """{ container: [
                 { container: [{ markdown: "# Deep", position: [0, 0], width: 50 }],
                   position: [10, 10], width: 50, height: 50 },
               ], position: [0, 0], width: 100, height: 100 }"""
        ),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    inner = ir.elements[0].container[0]
    assert isinstance(inner, ContainerElement)
    assert inner.container[0].markdown == "# Deep"


@pytest.mark.parametrize("dim", ["width", "height"])
def test_container_auto_dimension_rejected(tmp_path: Path, dim: str) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide(f'{{ container: [{{ markdown: "x" }}], {dim}: "auto" }}'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E309"):
        SlideIR.from_file(src)


def test_empty_container_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(tmp_path / "s.slide.json", _slide("{ container: [] }"))

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E310"):
        SlideIR.from_file(src)


# ── Name namespacing and E207 ────────────────────────────────────


def test_named_container_prefixes_children(tmp_path: Path) -> None:
    """Two instantiations with distinct names coexist; same child names inside."""
    # --- arrange ----------------------
    body = """
      { name: "left", container: [{ name: "label", markdown: "L" }], width: 50, height: 50 },
      { name: "right", container: [{ name: "label", markdown: "R" }], width: 50, height: 50 }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act / assert (no E207) -------
    ir = SlideIR.from_file(src)
    assert len(ir.elements) == 2


def test_unnamed_containers_with_colliding_children_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    body = """
      { container: [{ name: "label", markdown: "L" }], width: 50, height: 50 },
      { container: [{ name: "label", markdown: "R" }], width: 50, height: 50 }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="label"):
        SlideIR.from_file(src)


def test_child_collides_with_prefixed_name(tmp_path: Path) -> None:
    """The dot-prefixed effective name shares one scope with literal names."""
    # --- arrange ----------------------
    body = """
      { name: "hdr", container: [{ name: "title", markdown: "T" }], width: 50, height: 50 },
      { name: "hdr.title", markdown: "imposter" }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="hdr.title"):
        SlideIR.from_file(src)


# ── container_file includes ──────────────────────────────────────


def test_container_file_include(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(
        tmp_path / "partials" / "header.json",
        '[{ name: "banner", html: "<div></div>", position: [0, 0], width: 100, height: 100 }]',
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ name: "hdr", container_file: "partials/header.json", width: 100, height: 15 }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    ctr = ir.elements[0]
    assert isinstance(ctr, ContainerElement)
    assert ctr.container[0].html == "<div></div>"
    assert ctr.container_file is None  # schema artifact, popped pre-validation


def test_container_file_nested_file_fields_resolve_against_include_dir(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "partials" / "body.md", "# From include dir")
    _write(
        tmp_path / "partials" / "header.json",
        '[{ markdown_file: "body.md", position: [0, 0], width: 100 }]',
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ container_file: "partials/header.json", width: 100, height: 15 }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].container[0].markdown == "# From include dir"


def test_container_file_rebases_image_paths(tmp_path: Path) -> None:
    # --- arrange ----------------------
    img = _write(tmp_path / "partials" / "pic.png", "fake")
    _write(
        tmp_path / "partials" / "header.json",
        '[{ image: "pic.png", position: [0, 0], width: 50, height: "auto" }]',
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ container_file: "partials/header.json", width: 100, height: 15 }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].container[0].image == img.resolve()


def test_container_file_cycle_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "a.json", '[{ container_file: "b.json", width: 50, height: 50 }]')
    _write(tmp_path / "b.json", '[{ container_file: "a.json", width: 50, height: 50 }]')
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ container_file: "a.json", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E507"):
        SlideIR.from_file(src)


def test_container_both_forms_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "a.json", "[]")
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ container: [{ markdown: "x" }], container_file: "a.json", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="cannot specify both"):
        SlideIR.from_file(src)


# ── Path confinement ─────────────────────────────────────────────


def test_confined_file_field_escape_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "outside.md", "# secret")
    deck_root = tmp_path / "deck"
    src = _write(
        deck_root / "s.slide.json",
        _slide('{ markdown_file: "../outside.md", position: [0, 0], width: 80 }'),
    )

    # --- act / assert -----------------
    with confine_paths(deck_root):
        with pytest.raises(SlideSourceError, match="E506"):
            SlideIR.from_file(src)


def test_confined_allow_path_grants_extra_root(tmp_path: Path) -> None:
    # --- arrange ----------------------
    shared = tmp_path / "shared"
    _write(shared / "outside.md", "# granted")
    deck_root = tmp_path / "deck"
    src = _write(
        deck_root / "s.slide.json",
        _slide('{ markdown_file: "../shared/outside.md", position: [0, 0], width: 80 }'),
    )

    # --- act --------------------------
    with confine_paths(deck_root, [shared]):
        ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].markdown == "# granted"


def test_confined_absolute_path_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    target = _write(tmp_path / "deck" / "inside.md", "# in root")
    src = _write(
        tmp_path / "deck" / "s.slide.json",
        _slide(f'{{ markdown_file: "{target}", position: [0, 0], width: 80 }}'),
    )

    # --- act / assert -----------------
    with confine_paths(tmp_path / "deck"):
        with pytest.raises(SlideSourceError, match="E506"):
            SlideIR.from_file(src)


def test_unconfined_relative_escape_still_works(tmp_path: Path) -> None:
    """Outside a confinement context (direct API use) behavior is unchanged."""
    # --- arrange ----------------------
    _write(tmp_path / "outside.md", "# fine")
    src = _write(
        tmp_path / "deck" / "s.slide.json",
        _slide('{ markdown_file: "../outside.md", position: [0, 0], width: 80 }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].markdown == "# fine"


# ── Rendering ────────────────────────────────────────────────────


def test_container_renders_nested_children(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            """{ container: [
                 { html: "<b>a</b>", position: [0, 0], width: 100, height: 100 },
                 { markdown: "## b", position: [5, 33], width: 80 },
               ], position: [0, 5], width: 100, height: 15 }"""
        ),
    )
    ir = SlideIR.from_file(src)

    # --- act --------------------------
    rendered = SlideRenderer().render_elements(ir, css_namespace="t")[0]

    # --- assert -----------------------
    assert rendered.html.count('data-element-id="t-0.0"') == 1
    assert rendered.html.count('data-element-id="t-0.1"') == 1
    assert rendered.html.index("t-0.0") > rendered.html.index('data-element-id="t-0"')
    assert 'data-element-id="t-0"] > [data-element-id="t-0.0"]' in rendered.scoped_css
    assert "isolation: isolate" in rendered.scoped_css


def test_container_propagates_child_assets_and_snaps(tmp_path: Path) -> None:
    # --- arrange ----------------------
    for i in (1, 2):
        _write(tmp_path / f"f{i}.png", "fake")
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            """{ container: [
                 { image_sequence: ["f1.png", "f2.png"], frame_distance: 10,
                   position: [0, 0], width: 100, height: "auto" },
               ], position: [0, 0], width: 100, height: 100 }"""
        ),
    )
    ir = SlideIR.from_file(src)

    # --- act --------------------------
    rendered = SlideRenderer().render_elements(ir, css_namespace="t")[0]

    # --- assert -----------------------
    assert len(rendered.assets) == 2
    assert rendered.snap_positions == (0.0, 10.0)
