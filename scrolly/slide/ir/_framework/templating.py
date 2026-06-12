"""Jinja2 template expansion for ``template`` elements.

A ``template`` element carries Jinja2 text — inline or from a
``*.elements.json.j2`` file — that renders to a JSON5 array of child
elements. Expansion happens at slide load time: the instantiation
becomes a ``container`` element holding the rendered children, so all
downstream machinery (name namespacing, z-slots, asset bundling,
introspection) sees plain containers.

Template files may open with a JSON5 front-matter block between two
``---`` lines declaring their parameter contract::

    ---
    {
      description: "Colored banner with title.",
      params: {
        title:  { type: "string", required: true },
        accent: { type: "string", default: "#5EB083" },
      },
    }
    ---
    [ { markdown: "## {{ title }}", ... } ]

Rendering is strict (``StrictUndefined``) and deterministic: no
filesystem or environment access from expressions; ``{% include %}`` /
``{% import %}`` resolve only inside the template file's directory
tree. Literal ``{{`` in template output (e.g. JS template literals)
must be wrapped in ``{% raw %}…{% endraw %}``.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import json5
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateSyntaxError, UndefinedError
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from scrolly.errors import SlideSourceError

_FRONT_MATTER_DELIMITER = "---"

# Front-matter `type:` names to the Python types they admit. `bool` is
# checked before the numeric entries because bool subclasses int.
_PARAM_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


# ==================================================================================================
#  Front-matter
# ==================================================================================================
def split_front_matter(text: str, origin: str) -> tuple[dict, str]:
    """Split optional JSON5 front-matter from a template's Jinja body.

    Front-matter is the block between a leading ``---`` line and the
    next ``---`` line, parsed as a JSON5 object. It is stripped before
    Jinja rendering — params are static metadata, never templated.

    Returns:
        ``(meta, body)`` — ``meta`` is ``{}`` when no front-matter block
        is present.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        return {}, text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONT_MATTER_DELIMITER:
            raw = "".join(lines[1:i])
            try:
                meta = json5.loads(raw)
            except ValueError as exc:
                hint = ""
                if _parses_as_yaml_mapping(raw):
                    hint = (
                        " The block parses as YAML — scrolly front-matter is JSON5, "
                        "not YAML: wrap it in { }, quote string values."
                    )
                raise SlideSourceError(
                    code="E801",
                    message=f"template front-matter is not valid JSON5: {origin}: {exc}.{hint}",
                ) from None
            if not isinstance(meta, dict):
                raise SlideSourceError(
                    code="E801",
                    message=f"template front-matter must be a JSON5 object: {origin}",
                )
            return meta, "".join(lines[i + 1 :])
    raise SlideSourceError(
        code="E801",
        message=f"template front-matter block is not closed (missing second '---' line): {origin}",
    )


def _parses_as_yaml_mapping(raw: str) -> bool:
    """Check whether a failed front-matter block is valid YAML — the classic mix-up.

    ``---``-delimited front-matter is a YAML idiom everywhere else, so
    authors (and agents) reaching for YAML out of habit deserve a
    pointed hint rather than a bare JSON5 syntax error.
    """
    try:
        import yaml

        return isinstance(yaml.safe_load(raw), dict)
    except Exception:  # noqa: BLE001 — any YAML failure just means no hint
        return False


def resolve_params(declared: dict, given: dict, origin: str) -> dict:
    """Validate call-site variables against a ``params`` declaration and apply defaults.

    Args:
        declared: The front-matter ``params`` object (may be empty —
            then ``given`` passes through unchecked).
        given: The instantiation's ``with:`` variables.
        origin: Template description for error messages.

    Returns:
        The render context: defaults overlaid with ``given``.

    Raises:
        SlideSourceError: ``E804`` for an unknown or missing parameter,
            or a top-level type mismatch. Validation is shallow — the
            declared ``array`` / ``object`` types check the container
            kind only.
    """
    if not declared:
        return dict(given)

    for key in given:
        if key not in declared:
            hint = ""
            close = difflib.get_close_matches(key, declared, n=1)
            if close:
                hint = f" — did you mean '{close[0]}'?"
            raise SlideSourceError(code="E804", message=f"unknown template param '{key}' for {origin}{hint}")

    context: dict = {}
    for key, spec in declared.items():
        spec = spec if isinstance(spec, dict) else {}
        if key in given:
            value = given[key]
            type_name = spec.get("type")
            if type_name is not None:
                admitted = _PARAM_TYPES.get(type_name)
                if admitted is None:
                    raise SlideSourceError(
                        code="E804",
                        message=(
                            f"param '{key}' of {origin} declares unknown type '{type_name}' "
                            f"(expected one of {', '.join(_PARAM_TYPES)})"
                        ),
                    )
                is_bool = isinstance(value, bool)
                matches = isinstance(value, admitted) and (is_bool == (type_name == "boolean"))
                if not matches:
                    raise SlideSourceError(
                        code="E804",
                        message=f"param '{key}' of {origin} expects {type_name}, got {type(value).__name__}",
                    )
            context[key] = value
        elif "default" in spec:
            context[key] = spec["default"]
        elif spec.get("required", False):
            raise SlideSourceError(code="E804", message=f"missing required template param '{key}' for {origin}")
    return context


# ==================================================================================================
#  Rendering
# ==================================================================================================
def render_template_text(body: str, context: dict, origin: str, loader_dir: Path | None) -> str:
    """Render a template body to text with a strict, sandboxed environment.

    Args:
        body: The Jinja source (front-matter already stripped).
        context: Render variables (validated params + call-site values).
        origin: Template description for error messages.
        loader_dir: Root for ``{% include %}`` / ``{% import %}``
            lookups (the template file's directory); ``None`` for
            inline templates, which cannot include.

    Raises:
        SlideSourceError: ``E801`` for Jinja syntax errors, ``E802``
            for undefined variables (including missing keys on nested
            param structures), ``E805`` for any other render failure.
    """
    loader = FileSystemLoader(loader_dir) if loader_dir is not None else None
    env = Environment(loader=loader, undefined=StrictUndefined, keep_trailing_newline=True)
    try:
        return env.from_string(body).render(**context)
    except TemplateSyntaxError as exc:
        raise SlideSourceError(
            code="E801",
            message=(
                f"template syntax error in {origin}, line {exc.lineno}: {exc.message}. "
                f"Literal '{{{{' in content must be wrapped in {{% raw %}}…{{% endraw %}}."
            ),
        ) from None
    except UndefinedError as exc:
        raise SlideSourceError(
            code="E802",
            message=(
                f"undefined variable while rendering {origin}: {exc.message}. "
                f"Check the `with:` block — for nested params, a key may be "
                f"missing from the structure passed in."
            ),
        ) from None
    except Exception as exc:  # noqa: BLE001 — every render failure becomes the catalogued E805
        raise SlideSourceError(
            code="E805",
            message=f"template render failed for {origin}: {type(exc).__name__}: {exc}",
        ) from None


def parse_rendered_elements(rendered: str, origin: str) -> list:
    """Parse rendered template text as a JSON5 element array (raw dicts).

    Raises:
        SlideSourceError: ``E803`` when the text is not valid JSON5 or
            not an array; the message carries an excerpt around the
            failure point, since the rendered text exists only in
            memory (inspect it in full with ``scrolly expand``).
    """
    try:
        parsed = json5.loads(rendered)
    except ValueError as exc:
        raise SlideSourceError(
            code="E803",
            message=(
                f"rendered output of {origin} is not valid JSON5: {exc}\n"
                f"--- rendered output ---\n{_excerpt(rendered, exc)}\n"
                f"--- (run `scrolly expand` to see the full rendered text) ---"
            ),
        ) from None
    if not isinstance(parsed, list):
        raise SlideSourceError(
            code="E803",
            message=f"rendered output of {origin} must be a JSON5 array of elements, got {type(parsed).__name__}",
        )
    return parsed


def _excerpt(rendered: str, exc: ValueError, context_lines: int = 3) -> str:
    """Cut a numbered excerpt around the failing line (when the error names one)."""
    lines = rendered.splitlines()
    lineno = getattr(exc, "lineno", None)
    if lineno is None or not (1 <= lineno <= len(lines)):
        head = lines[:8]
        return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(head))
    lo = max(0, lineno - 1 - context_lines)
    hi = min(len(lines), lineno + context_lines)
    return "\n".join(f"{i + 1:4d}{'>' if i + 1 == lineno else ' '}| {lines[i]}" for i in range(lo, hi))


# ==================================================================================================
#  Slide factories (template-slide stubs)
# ==================================================================================================
_SLIDE_TEMPLATE_SUFFIX = ".slide.json.j2"
_ELEMENTS_TEMPLATE_SUFFIX = ".elements.json.j2"


def expand_slide_stub(raw: dict, source_path: Path) -> tuple[dict, Path]:
    """Resolve a template-slide stub to its rendered slide object.

    A stub is a ``.slide.json`` whose top level carries ``template_file``
    (+ optional ``with``) instead of ``elements``. The referenced
    ``*.slide.json.j2`` factory renders to a full slide JSON5 object.
    Plain slides pass through unchanged.

    Returns:
        ``(slide_raw, content_dir)`` — the slide object and the
        directory its file references resolve against (the factory's
        directory for stubs, the slide's own for plain slides).
    """
    from scrolly._shared.paths import resolve_reference

    if "template_file" not in raw:
        return raw, source_path.parent

    extra_keys = set(raw) - {"template_file", "with"}
    if extra_keys:
        raise SlideSourceError(
            code="E208",
            message=(
                f"template-slide stub may carry only 'template_file' and 'with', "
                f"got extra keys {sorted(extra_keys)}: {source_path}. The factory "
                f"template provides all slide fields (title, elements, …)."
            ),
        )
    given = raw.get("with", {})
    if not isinstance(given, dict):
        raise SlideSourceError(code="E208", message=f"stub 'with' must be an object: {source_path}")

    authored = str(raw["template_file"])
    _check_template_suffix(authored, _SLIDE_TEMPLATE_SUFFIX, f"slide stub {source_path}")
    template_path = resolve_reference(authored, source_path.parent, what="template_file")
    try:
        text = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SlideSourceError(code="E505", message=f"template_file not found: {template_path}") from None

    origin = authored
    meta, body = split_front_matter(text, origin)
    declared = meta.get("params", {})
    if not isinstance(declared, dict):
        raise SlideSourceError(code="E801", message=f"front-matter `params` must be an object: {origin}")
    context = resolve_params(declared, given, origin)
    rendered = render_template_text(body, context, origin, template_path.parent)

    try:
        slide_raw = json5.loads(rendered)
    except ValueError as exc:
        raise SlideSourceError(
            code="E803",
            message=(
                f"rendered output of {origin} is not valid JSON5: {exc}\n"
                f"--- rendered output ---\n{_excerpt(rendered, exc)}\n"
                f"--- (run `scrolly expand` to see the full rendered text) ---"
            ),
        ) from None
    if not isinstance(slide_raw, dict):
        raise SlideSourceError(
            code="E803",
            message=f"rendered output of {origin} must be a JSON5 slide object, got {type(slide_raw).__name__}",
        )
    return slide_raw, template_path.parent


def _check_template_suffix(authored: str, expected: str, where: str) -> None:
    """Enforce that a template reference's suffix matches its render target (E806)."""
    if not authored.endswith(expected):
        other = _SLIDE_TEMPLATE_SUFFIX if expected == _ELEMENTS_TEMPLATE_SUFFIX else _ELEMENTS_TEMPLATE_SUFFIX
        raise SlideSourceError(
            code="E806",
            message=(
                f"template_file of {where} must end with '{expected}' "
                f"(templates rendering the other target use '{other}'): got '{authored}'"
            ),
        )


# ==================================================================================================
#  Preview (``scrolly expand``)
# ==================================================================================================
def render_slide_template_previews(slide_path: Path) -> list[tuple[str, str]]:
    """Render every template instantiation in a slide source to text, for preview.

    Walks the *raw* parsed slide (no model validation), so the preview
    works even when the rendered output fails later stages — that is
    its purpose. Nested templates inside rendered output are not
    recursed into; preview shows each authored instantiation's own
    rendered text.

    Returns:
        ``(origin, rendered_text)`` per instantiation, in document order.
    """
    from scrolly._shared.paths import resolve_reference

    try:
        raw = json5.loads(slide_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SlideSourceError(code="E505", message=f"slide source not found: {slide_path}") from None
    except ValueError as exc:
        raise SlideSourceError(code="E001", message=f"slide source is not valid JSON5: {slide_path}: {exc}") from None

    previews: list[tuple[str, str]] = []

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            if "template" in node or "template_file" in node:
                given = node.get("with", {}) if isinstance(node.get("with", {}), dict) else {}
                if node.get("template_file") is not None:
                    path = resolve_reference(node["template_file"], slide_path.parent, what="template_file")
                    try:
                        text = path.read_text(encoding="utf-8")
                    except FileNotFoundError:
                        raise SlideSourceError(code="E505", message=f"template_file not found: {path}") from None
                    origin = str(node["template_file"])
                    meta, body = split_front_matter(text, origin)
                    loader_dir: Path | None = path.parent
                else:
                    origin, meta, body, loader_dir = "<inline template>", {}, str(node.get("template", "")), None
                context = resolve_params(meta.get("params", {}), given, origin)
                previews.append((origin, render_template_text(body, context, origin, loader_dir)))
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw)
    return previews


def template_contract(template_path: Path) -> dict:
    """Read a template file's front-matter contract for ``scrolly schema template``.

    Returns:
        ``{"description": str | None, "params": dict}`` — empty contract
        when the file has no front-matter.
    """
    try:
        text = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SlideSourceError(code="E505", message=f"template file not found: {template_path}") from None
    meta, _body = split_front_matter(text, str(template_path))
    return {"description": meta.get("description"), "params": meta.get("params", {})}


# ==================================================================================================
#  Expansion
# ==================================================================================================
def expand_templates(elements: list, source_dir: Path, include_stack: tuple[Path, ...] = ()) -> list:
    """Expand every ``template`` element in ``elements`` (recursively) to containers.

    Returns a new list; non-template elements pass through (containers
    get their children expanded). ``include_stack`` carries the chain
    of template files for cycle detection (E507).
    """
    # Function-local import: the element models import nothing from this
    # module, but live in a sibling whose import must come first.
    from scrolly.slide.ir._framework.element import ContainerElement, TemplateElement

    expanded: list = []
    for el in elements:
        if isinstance(el, TemplateElement):
            expanded.append(_expand_one(el, source_dir, include_stack))
        elif isinstance(el, ContainerElement):
            children = expand_templates(el.container, source_dir, include_stack)
            if children != list(el.container):
                el = el.model_copy(update={"container": children})
            expanded.append(el)
        else:
            expanded.append(el)
    return expanded


def _expand_one(el, source_dir: Path, include_stack: tuple[Path, ...]):
    """Expand a single ``TemplateElement`` into a ``ContainerElement``."""
    from scrolly._shared.paths import resolve_reference
    from scrolly.slide.ir._framework.element import AnyElement, ContainerElement
    from scrolly.slide.ir._framework.utils import _rebase_asset_paths, _resolve_file_fields

    if el.template_file is not None:
        _check_template_suffix(str(el.template_file), _ELEMENTS_TEMPLATE_SUFFIX, "a template element")
        template_path = resolve_reference(el.template_file, source_dir, what="template_file")
        normalized = template_path.resolve()
        if normalized in include_stack:
            chain = " -> ".join(str(p) for p in (*include_stack, normalized))
            raise SlideSourceError(code="E507", message=f"template_file include cycle: {chain}")
        try:
            text = template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise SlideSourceError(code="E505", message=f"template_file not found: {template_path}") from None
        origin = str(el.template_file)
        meta, body = split_front_matter(text, origin)
        template_dir: Path | None = template_path.parent
        next_stack = (*include_stack, normalized)
    else:
        origin = "<inline template>"
        meta, body = {}, el.template
        template_dir = None
        next_stack = include_stack

    declared = meta.get("params", {})
    if not isinstance(declared, dict):
        raise SlideSourceError(code="E801", message=f"front-matter `params` must be an object: {origin}")
    context = resolve_params(declared, el.with_, origin)

    rendered = render_template_text(body, context, origin, template_dir)
    raw_children = parse_rendered_elements(rendered, origin)

    content_dir = template_dir if template_dir is not None else source_dir
    _resolve_file_fields(raw_children, content_dir, next_stack)
    if template_dir is not None:
        _rebase_asset_paths(raw_children, template_dir, source_dir)

    try:
        children = TypeAdapter(list[AnyElement]).validate_python(raw_children)
    except PydanticValidationError as exc:
        raise SlideSourceError(
            code="E803",
            message=f"rendered output of {origin} is not a valid element array: {exc}",
        ) from None

    children = expand_templates(children, source_dir, next_stack)
    return ContainerElement(
        container=children,
        template_origin=origin,
        name=el.name,
        position=el.position,
        width=el.width,
        height=el.height,
        anchor=el.anchor,
        opacity=el.opacity,
        scale=el.scale,
        angle=el.angle,
    )
