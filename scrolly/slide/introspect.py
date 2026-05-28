"""Build-time slide introspection — JSON-ready views of resolved slide IRs.

The ``*_to_json`` helpers here power the ``scrolly introspect`` CLI
subcommands that surface slide-level state: the resolved element tree,
snap positions (author + element-derived), per-element scroll timeline
(animated keyframes + visibility intervals), and per-scroll snapshot of
substrate properties. Each helper is pure (no I/O), takes the resolved
``Deck`` + ``slide_irs`` map produced by ``load_deck`` and returns a
``dict`` that's safe to feed into ``json.dumps``.
"""

from __future__ import annotations

from typing import Any

from scrolly.deck.model import Deck
from scrolly.errors import SlideSourceError
from scrolly.slide.ir import SlideIR
from scrolly.slide.ir._framework.animated_values import AnimatedScalar
from scrolly.slide.ir._framework.element import ImageSequenceElement
from scrolly.slide.registry import find_renderer

# The substrate properties shared by every ``SlideElement`` subtype.
# Used by ``timeline_to_json`` (to list animated ones) and
# ``snapshot_to_json`` (to resolve all at the requested scroll values).
_SUBSTRATE_PROPERTIES: tuple[str, ...] = (
    "position",
    "width",
    "height",
    "anchor",
    "opacity",
    "scale",
    "angle",
)


def element_tree_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize per-slide element trees to a JSON-ready dict.

    Each element is dumped via Pydantic's ``model_dump(mode="json")``
    then augmented with ``index`` and ``type`` fields. Animated values
    surface as their underlying root form — a static scalar, an
    ``[x, y]`` list, the literal string ``"auto"`` for size dims, or a
    ``{"keyframes": [...]}`` dict for animated values.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to include; ``None``
            (or empty) returns all slides.

    Returns:
        Dict ``{"slides": {<id>: {title, scroll_range, elements: [...]}}}``.
    """
    target_ids = set(slide_ids) if slide_ids else None

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]
        elements_view = []
        for index, el in enumerate(ir.elements):
            element_dict = el.model_dump(mode="json")
            element_dict["index"] = index
            element_dict["type"] = type(el).__name__
            elements_view.append(element_dict)
        slides_view[slide.id] = {
            "title": ir.title,
            "scroll_range": ir.scroll_range,
            "elements": elements_view,
        }

    return {"slides": slides_view}


def snaps_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize per-slide snap positions (author + element-derived).

    Author snap positions come from each slide's ``snap_positions`` field.
    Element-derived snap positions come from ``ImageSequenceElement``
    hold-centres — every frame's hold period contributes one snap stop
    at its centre. The ``merged`` list is the deduplicated + sorted
    union the slide renderer threads into ``SlideHTML.snap_positions`` —
    the value the canvas runtime actually uses.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to include; ``None``
            (or empty) returns all slides.

    Returns:
        Dict ``{"slides": {<id>: {scroll_range, author_snap_positions,
        derived_snap_positions, merged}}}``. Each derived entry carries
        a structured ``source`` identifying the element and frame index.
    """
    target_ids = set(slide_ids) if slide_ids else None

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]

        author = list(ir.snap_positions)
        derived: list[dict[str, Any]] = []
        for index, el in enumerate(ir.elements):
            if isinstance(el, ImageSequenceElement):
                for frame_index, pos in enumerate(el.hold_centre_positions()):
                    derived.append(
                        {
                            "value": pos,
                            "source": {
                                "element_index": index,
                                "element_name": el.name,
                                "frame_index": frame_index,
                            },
                        }
                    )

        # Merged set: union of author and derived values, sorted, deduplicated.
        # Author entries are ints; derived entries are floats — keep original
        # numeric types in the merged list (JSON renders both as numbers).
        all_values: set[float] = set(author) | {d["value"] for d in derived}
        merged = sorted(all_values)

        slides_view[slide.id] = {
            "scroll_range": ir.scroll_range,
            "author_snap_positions": author,
            "derived_snap_positions": derived,
            "merged": merged,
        }

    return {"slides": slides_view}


def timeline_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize per-element scroll timeline (animated keyframes + visibility intervals).

    For each element the result contains:

    * ``animated_properties`` — only the substrate properties that are
      actually animated (have keyframes); static properties are omitted
      to avoid redundancy with ``element_tree_to_json``.
    * ``visibility_intervals`` — scroll ranges where ``opacity > 0``,
      derived by walking the opacity keyframes and finding zero
      crossings. For ``scroll_range: "auto"`` slides whose opacity is
      held-constant at a positive value past the last keyframe, the
      final interval's ``"to"`` is ``null`` — the upper bound is a
      runtime DOM measurement.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to include; ``None``
            (or empty) returns all slides.

    Returns:
        Dict ``{"slides": {<id>: {scroll_range, elements: [...]}}}``.
    """
    target_ids = set(slide_ids) if slide_ids else None

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]

        elements_view = []
        for index, el in enumerate(ir.elements):
            animated_properties: dict[str, dict] = {}
            for prop in _SUBSTRATE_PROPERTIES:
                value = getattr(el, prop)
                if value.is_animated:
                    animated_properties[prop] = value.model_dump(mode="json")

            visibility_intervals = _compute_visibility_intervals(el.opacity, ir.scroll_range)

            elements_view.append(
                {
                    "index": index,
                    "name": el.name,
                    "type": type(el).__name__,
                    "animated_properties": animated_properties,
                    "visibility_intervals": visibility_intervals,
                }
            )

        slides_view[slide.id] = {
            "scroll_range": ir.scroll_range,
            "elements": elements_view,
        }

    return {"slides": slides_view}


def snapshot_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_id: str,
    scrolls: tuple[float, ...],
) -> dict:
    """Resolve per-element substrate properties at one or more scroll positions.

    Unlike the other ``*_to_json`` helpers, this one takes a single
    ``slide_id`` (mandatory) and a tuple of ``scrolls`` (mandatory).
    Scroll-position validation against the slide's ``scroll_range`` is
    the CLI's responsibility — by the time this helper is called, every
    scroll in ``scrolls`` is known to lie within the slide's reachable
    range.

    For each scroll, every element's seven substrate properties
    (``position``, ``width``, ``height``, ``anchor``, ``opacity``,
    ``scale``, ``angle``) are resolved to numeric values via
    ``evaluate_at``. Type-specific content (image path, markdown text,
    iframe HTML, etc.) is omitted: it doesn't change with scroll, and
    ``element_tree_to_json`` already exposes it.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_id: Slide to snapshot (validated upstream).
        scrolls: Non-empty tuple of scroll positions to snapshot at.

    Returns:
        Dict ``{"slides": {<slide_id>: {scroll_range, snapshots:
        [{scroll, elements: [...]}, ...]}}}``. The single-slide map
        shape preserves uniformity with the rest of the introspect
        family.
    """
    del deck  # validated already; we only need the IR
    ir = slide_irs[slide_id]

    snapshots = []
    for scroll in scrolls:
        elements_view = []
        for index, el in enumerate(ir.elements):
            position = el.position.evaluate_at(scroll)
            anchor = el.anchor.evaluate_at(scroll)
            opacity = el.opacity.evaluate_at(scroll)
            elements_view.append(
                {
                    "index": index,
                    "name": el.name,
                    "type": type(el).__name__,
                    "position": list(position),
                    "width": el.width.evaluate_at(scroll),
                    "height": el.height.evaluate_at(scroll),
                    "anchor": list(anchor),
                    "opacity": opacity,
                    "scale": el.scale.evaluate_at(scroll),
                    "angle": el.angle.evaluate_at(scroll),
                    "visible": opacity > 0,
                }
            )
        snapshots.append({"scroll": scroll, "elements": elements_view})

    return {
        "slides": {
            slide_id: {
                "scroll_range": ir.scroll_range,
                "snapshots": snapshots,
            }
        }
    }


def dom_to_json(
    deck: Deck,
    slide_irs: dict[str, SlideIR],
    slide_ids: tuple[str, ...] | None = None,
) -> dict:
    """Serialize the rendered per-element HTML + scoped CSS for each slide.

    Drives the slide renderer's ``render_elements`` (the per-element
    sibling of ``render``) for each slide, returning the per-element
    pieces without going through deck-level assembly: no canvas runtime,
    no scrollbar, no edge geometry, no inter-slide chrome — just what
    each element produced. The single biggest agent blind spot is
    "what does my config actually become" and this is the answer.

    For the current 1:1 authored→primitive mapping (no element
    compilers are registered today) each authored element yields one
    rendered piece. The renderer joins multi-primitive expansions per
    authored element so the output remains one entry per author-visible
    element regardless of future compiler additions.

    Args:
        deck: Fully-resolved deck.
        slide_irs: Map from slide id to loaded ``SlideIR``.
        slide_ids: Optional tuple of slide ids to include; ``None``
            (or empty) returns all slides.

    Returns:
        Dict ``{"slides": {<id>: {elements: [{index, name, type, html,
        scoped_css}, ...]}}}``.

    Raises:
        SlideSourceError: If no slide renderer is registered for an
            IR type (E603) or no element renderer for a primitive
            (E601). These mirror the same errors raised during
            ``build_deck`` so introspect doesn't mask them.
    """
    target_ids = set(slide_ids) if slide_ids else None

    slides_view: dict[str, dict] = {}
    for slide in deck.slides:
        if target_ids is not None and slide.id not in target_ids:
            continue
        ir = slide_irs[slide.id]
        renderer = find_renderer(ir)
        if renderer is None:
            raise SlideSourceError(
                code="E603",
                message=f"no renderer for {type(ir).__name__} (slide '{slide.id}')",
            )

        rendered_elements = renderer.render_elements(ir, css_namespace=slide.id)

        elements_view = []
        for index, (authored_el, rendered) in enumerate(zip(ir.elements, rendered_elements)):
            elements_view.append(
                {
                    "index": index,
                    "name": authored_el.name,
                    "type": type(authored_el).__name__,
                    "html": rendered.html,
                    "scoped_css": rendered.scoped_css,
                }
            )

        slides_view[slide.id] = {"elements": elements_view}

    return {"slides": slides_view}


def _compute_visibility_intervals(
    opacity: AnimatedScalar,
    scroll_range: float | str,
) -> list[dict[str, float | None]]:
    """Compute scroll intervals where ``opacity > 0``.

    Returns a list of ``{"from": x, "to": y}`` dicts (half-open, with
    ``opacity > 0`` strictly inside). For ``scroll_range: "auto"`` slides
    whose final held-constant opacity is positive, the last interval's
    ``"to"`` is ``None`` — the upper bound is a runtime DOM measurement.

    Args:
        opacity: The element's opacity (static or animated).
        scroll_range: The slide's ``scroll_range`` field (number or
            ``"auto"``).

    Returns:
        List of interval dicts. Empty if the element is never visible
        in the slide's scroll range.
    """
    upper: float | None = scroll_range if isinstance(scroll_range, (int, float)) else None

    # Static opacity: either always visible or never.
    if not opacity.is_animated:
        if opacity.static_value > 0:
            return [{"from": 0, "to": upper}]
        return []

    kf = opacity.keyframes

    # Breakpoints: 0, each keyframe position inside (0, upper), and upper
    # (when numeric). Evaluating opacity at each breakpoint lets us treat
    # the held-constant prefix/suffix and the interior linear segments
    # uniformly — for the prefix/suffix the values at both endpoints are
    # equal, so the segment is constant.
    positions: list[float] = [0.0]
    for pos, _ in kf:
        if pos > 0 and (upper is None or pos < upper):
            positions.append(pos)
    if upper is not None:
        positions.append(upper)
    positions = sorted(set(positions))

    bp_values = [opacity.evaluate_at(p) for p in positions]

    intervals: list[tuple[float, float | None]] = []
    for i in range(len(positions) - 1):
        p1, p2 = positions[i], positions[i + 1]
        v1, v2 = bp_values[i], bp_values[i + 1]
        if v1 > 0 and v2 > 0:
            intervals.append((p1, p2))
        elif v1 <= 0 and v2 <= 0:
            continue
        elif v1 > 0:  # crossing from positive to non-positive
            t = v1 / (v1 - v2)
            intervals.append((p1, p1 + t * (p2 - p1)))
        else:  # crossing from non-positive to positive
            t = -v1 / (v2 - v1)
            intervals.append((p1 + t * (p2 - p1), p2))

    # ``"auto"`` slides have no final upper breakpoint; account for the
    # held-constant suffix that extends past the last keyframe to
    # runtime-determined infinity.
    if upper is None and kf[-1][1] > 0:
        intervals.append((kf[-1][0], None))

    # Merge intervals that touch end-to-start (a crossing exactly at a
    # keyframe position can split what's really one continuous visible
    # range across two segments).
    if not intervals:
        return []
    merged: list[tuple[float, float | None]] = [intervals[0]]
    for f, t in intervals[1:]:
        prev_f, prev_t = merged[-1]
        if prev_t is not None and prev_t == f:
            merged[-1] = (prev_f, t)
        else:
            merged.append((f, t))

    return [{"from": f, "to": t} for f, t in merged]
