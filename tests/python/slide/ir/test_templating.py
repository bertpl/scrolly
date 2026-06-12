"""Tests for the ``template`` element — front-matter, params, rendering, expansion."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.errors import SlideSourceError
from scrolly.slide.ir import ContainerElement
from scrolly.slide.ir._framework.templating import (
    render_slide_template_previews,
    resolve_params,
    split_front_matter,
    template_contract,
)
from scrolly.slide.ir.slide import SlideIR


def _write(path: Path, text: str) -> Path:
    """Write ``text`` to ``path`` (creating parents) and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _slide(elements_json5: str) -> str:
    """Wrap an elements array body in a minimal slide source."""
    return f'{{ title: "T", scroll_range: 100, elements: [{elements_json5}] }}'


_BADGE_TEMPLATE = """\
---
{
  description: "Badge.",
  params: {
    label:  { type: "string", required: true },
    n:      { type: "integer", default: 2 },
  },
}
---
[
{% for i in range(n) %}
  { name: "row{{ i }}", markdown: "{{ label }} {{ i }}", position: [5, {{ 10 + i * 8 }}], width: 80 },
{% endfor %}
]
"""


# ── Front-matter ─────────────────────────────────────────────────


def test_split_front_matter_roundtrip() -> None:
    # --- act --------------------------
    meta, body = split_front_matter(_BADGE_TEMPLATE, "t")

    # --- assert -----------------------
    assert meta["description"] == "Badge."
    assert set(meta["params"]) == {"label", "n"}
    assert body.startswith("[")


def test_no_front_matter_means_empty_meta() -> None:
    # --- act --------------------------
    meta, body = split_front_matter("[]", "t")

    # --- assert -----------------------
    assert meta == {}
    assert body == "[]"


def test_yaml_front_matter_gets_pointed_hint() -> None:
    # --- arrange ----------------------
    yaml_block = "---\ndescription: Badge\nparams:\n  label:\n    type: string\n---\n[]"

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="JSON5, "):
        split_front_matter(yaml_block, "t")


def test_unclosed_front_matter_rejected() -> None:
    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E801"):
        split_front_matter("---\n{ params: {} }\n[]", "t")


# ── Param resolution ─────────────────────────────────────────────


def test_resolve_params_applies_defaults() -> None:
    # --- arrange ----------------------
    declared = {"a": {"type": "string", "required": True}, "b": {"type": "integer", "default": 7}}

    # --- act --------------------------
    ctx = resolve_params(declared, {"a": "x"}, "t")

    # --- assert -----------------------
    assert ctx == {"a": "x", "b": 7}


@pytest.mark.parametrize(
    ("given", "match"),
    [
        ({}, "missing required"),
        ({"a": "x", "zz": 1}, "unknown template param"),
        ({"a": 5}, "expects string"),
        ({"a": "x", "b": True}, "expects integer"),  # bool is not an integer here
    ],
)
def test_resolve_params_mismatches(given: dict, match: str) -> None:
    # --- arrange ----------------------
    declared = {"a": {"type": "string", "required": True}, "b": {"type": "integer", "default": 7}}

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match=match):
        resolve_params(declared, given, "t")


def test_resolve_params_suggests_close_match() -> None:
    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="did you mean 'label'"):
        resolve_params({"label": {"type": "string"}}, {"labl": "x"}, "t")


def test_resolve_params_composite_values_pass_shallow_check() -> None:
    # --- arrange ----------------------
    declared = {"teams": {"type": "array", "required": True}}
    teams = [{"name": "Core", "members": ["an", "bo"]}]

    # --- act --------------------------
    ctx = resolve_params(declared, {"teams": teams}, "t")

    # --- assert -----------------------
    assert ctx["teams"] == teams


# ── Expansion via SlideIR.from_file ──────────────────────────────


def test_inline_template_expands_to_container(tmp_path: Path) -> None:
    # --- arrange ----------------------
    inline = (
        '[ {% for i in range(3) %} { name: \\"s{{ i }}\\", markdown: \\"step {{ i }}\\",'
        " position: [5, {{ 10 + i * 8 }}], width: 80 }, {% endfor %} ]"
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide(f'{{ name: "steps", template: "{inline}", width: 100, height: 50 }}'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)
    ctr = ir.elements[0]

    # --- assert -----------------------
    assert isinstance(ctr, ContainerElement)
    assert ctr.template_origin == "<inline template>"
    assert [c.name for c in ctr.container] == ["s0", "s1", "s2"]
    assert ctr.container[2].position.static_value == (5.0, 26.0)


def test_file_template_with_params_expands(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            '{ name: "b", template_file: "badge.elements.json.j2",'
            ' with: { label: "Step", n: 3 }, width: 100, height: 30 }'
        ),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)
    ctr = ir.elements[0]

    # --- assert -----------------------
    assert ctr.template_origin == "badge.elements.json.j2"
    assert len(ctr.container) == 3
    assert ctr.container[1].markdown == "Step 1"


def test_template_twice_with_names_no_collision(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)
    body = """
      { name: "a", template_file: "badge.elements.json.j2", with: { label: "A" }, width: 50, height: 30 },
      { name: "b", template_file: "badge.elements.json.j2", with: { label: "B" }, width: 50, height: 30 }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act / assert (no E207) -------
    ir = SlideIR.from_file(src)
    assert len(ir.elements) == 2


def test_template_twice_unnamed_collides(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)
    body = """
      { template_file: "badge.elements.json.j2", with: { label: "A" }, width: 50, height: 30 },
      { template_file: "badge.elements.json.j2", with: { label: "B" }, width: 50, height: 30 }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="duplicate element name"):
        SlideIR.from_file(src)


def test_template_inside_container_expands(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)
    body = """
      { name: "outer", container: [
          { name: "inner", template_file: "badge.elements.json.j2", with: { label: "X" },
            width: 100, height: 100 },
        ], width: 50, height: 50 }
    """
    src = _write(tmp_path / "s.slide.json", _slide(body))

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    inner = ir.elements[0].container[0]
    assert isinstance(inner, ContainerElement)
    assert inner.template_origin == "badge.elements.json.j2"


def test_template_rendering_template_cycle_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(
        tmp_path / "a.elements.json.j2",
        '[ { template_file: "a.elements.json.j2", width: 50, height: 50 } ]',
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template_file: "a.elements.json.j2", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E507"):
        SlideIR.from_file(src)


def test_nested_file_fields_resolve_against_template_dir(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "partials" / "body.md", "# from template dir")
    _write(
        tmp_path / "partials" / "t.elements.json.j2",
        '[ { markdown_file: "body.md", position: [0, 0], width: 80 } ]',
    )
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template_file: "partials/t.elements.json.j2", width: 100, height: 100 }'),
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].container[0].markdown == "# from template dir"


# ── Error surfaces ───────────────────────────────────────────────


def test_jinja_syntax_error_is_e801(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template: "[ {% broken ]", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E801"):
        SlideIR.from_file(src)


def test_undefined_variable_is_e802(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template: "[ { markdown: \\"{{ nope }}\\" } ]", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E802"):
        SlideIR.from_file(src)


def test_invalid_rendered_json5_is_e803_with_excerpt(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template: "[ { markdown: \\"x\\" position: [5, 5] } ]", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E803"):
        SlideIR.from_file(src)


def test_render_failure_on_bad_structure_is_e805(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            '{ template: "[ {% for x in items %} {{ x.y }} {% endfor %} ]",'
            " with: { items: 42 }, width: 100, height: 100 }"
        ),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E805"):
        SlideIR.from_file(src)


def test_both_template_forms_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    src = _write(
        tmp_path / "s.slide.json",
        _slide('{ template: "[]", template_file: "x.j2", width: 100, height: 100 }'),
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E311"):
        SlideIR.from_file(src)


# ── Slide factories (template-slide stubs) ───────────────────────


_CHAPTER_FACTORY = """\
---
{
  params: {
    heading: { type: "string", required: true },
    part:    { type: "string", default: "1/1" },
  },
}
---
{
  title: "{{ heading }} ({{ part }})",
  scroll_range: 100,
  elements: [
    { name: "h", markdown: "## {{ heading }}", position: [5, 5], width: 90 },
  ],
}
"""


def test_slide_stub_renders_factory(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "factories" / "chapter.slide.json.j2", _CHAPTER_FACTORY)
    src = _write(
        tmp_path / "s.slide.json",
        '{ template_file: "factories/chapter.slide.json.j2", with: { heading: "Hi", part: "2/3" } }',
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.title == "Hi (2/3)"
    assert ir.elements[0].markdown == "## Hi"


def test_slide_stub_file_fields_resolve_against_factory_dir(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "factories" / "note.md", "# factory-side note")
    factory = _CHAPTER_FACTORY.replace('markdown: "## {{ heading }}"', 'markdown_file: "note.md"')
    _write(tmp_path / "factories" / "chapter.slide.json.j2", factory)
    src = _write(
        tmp_path / "s.slide.json",
        '{ template_file: "factories/chapter.slide.json.j2", with: { heading: "Hi" } }',
    )

    # --- act --------------------------
    ir = SlideIR.from_file(src)

    # --- assert -----------------------
    assert ir.elements[0].markdown == "# factory-side note"


def test_slide_stub_extra_keys_rejected(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "factories" / "chapter.slide.json.j2", _CHAPTER_FACTORY)
    src = _write(
        tmp_path / "s.slide.json",
        '{ template_file: "factories/chapter.slide.json.j2", with: { heading: "x" }, title: "no" }',
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E208"):
        SlideIR.from_file(src)


def test_slide_stub_missing_required_param_is_e804(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "factories" / "chapter.slide.json.j2", _CHAPTER_FACTORY)
    src = _write(
        tmp_path / "s.slide.json",
        '{ template_file: "factories/chapter.slide.json.j2", with: {} }',
    )

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E804"):
        SlideIR.from_file(src)


@pytest.mark.parametrize(
    ("stub_target", "element_target"),
    [("badge.elements.json.j2", None), (None, "chapter.slide.json.j2")],
)
def test_template_suffix_mismatch_is_e806(tmp_path: Path, stub_target: str | None, element_target: str | None) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", "[]")
    _write(tmp_path / "chapter.slide.json.j2", "{}")
    if stub_target is not None:
        body = f'{{ template_file: "{stub_target}", with: {{}} }}'
    else:
        body = _slide(f'{{ template_file: "{element_target}", width: 100, height: 100 }}')
    src = _write(tmp_path / "s.slide.json", body)

    # --- act / assert -----------------
    with pytest.raises(SlideSourceError, match="E806"):
        SlideIR.from_file(src)


# ── Preview + contract surfaces ──────────────────────────────────


def test_render_slide_template_previews(tmp_path: Path) -> None:
    # --- arrange ----------------------
    _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)
    src = _write(
        tmp_path / "s.slide.json",
        _slide(
            '{ name: "b", template_file: "badge.elements.json.j2", with: { label: "P", n: 1 }, width: 100, height: 30 }'
        ),
    )

    # --- act --------------------------
    previews = render_slide_template_previews(src)

    # --- assert -----------------------
    assert len(previews) == 1
    origin, rendered = previews[0]
    assert origin == "badge.elements.json.j2"
    assert '"P 0"' in rendered


def test_template_contract_reads_front_matter(tmp_path: Path) -> None:
    # --- arrange ----------------------
    path = _write(tmp_path / "badge.elements.json.j2", _BADGE_TEMPLATE)

    # --- act --------------------------
    contract = template_contract(path)

    # --- assert -----------------------
    assert contract["description"] == "Badge."
    assert contract["params"]["label"]["required"] is True
