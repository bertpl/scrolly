"""Render a ScrollimationIR into a SlideHTML.

Generates CSS with piecewise-linear calc() expressions for animated
properties.  Static properties emit plain CSS values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path

import markdown

from scrolly.pipeline._compress import CompressionStats, try_compress
from scrolly.slide.html import SlideHTML
from scrolly.slide.ir import (
    HtmlElement,
    IframeElement,
    ImageElement,
    ImageSequenceElement,
    MarkdownElement,
    MermaidElement,
    SlideIR,
)
from scrolly.slide.ir._framework.animated_values import AnimatedScalar, AnimatedVec2
from scrolly.slide.ir.scrollimation import AnyElement, ScrollimationIR
from scrolly.slide.processor import Renderer

_MD_EXTENSIONS: tuple[str, ...] = ("fenced_code", "tables", "sane_lists")
_SCROLL_VAR = "var(--scroll-position, 0)"

# Width (in scroll units) of the near-instantaneous opacity drop used by
# ``compositing: "overlay"`` to take a frame from full opacity to 0 once
# its successor has fully faded in. A true step discontinuity cannot be
# expressed by the CSS ``calc()``-based ramp generator (which produces
# continuous piecewise-linear functions), so we use a 1-unit ramp that
# is visually indistinguishable from a step at any reasonable scroll
# speed but keeps slope computation well-defined.
_STEP_RAMP_WIDTH = 1.0


# ==================================================================================================
#  CSS ramp expression generation
# ==================================================================================================


def ramp_expr(kfs: list[tuple[float, float]]) -> str | None:
    """Generate a CSS calc()-compatible sum-of-ramps expression.

    Returns ``None`` if the timeline is constant (all values equal),
    meaning the caller should emit a static CSS value instead.
    """
    if len(kfs) <= 1:
        return None

    if all(v == kfs[0][1] for _, v in kfs):
        return None

    v0 = kfs[0][1]
    slopes = [(kfs[i + 1][1] - kfs[i][1]) / (kfs[i + 1][0] - kfs[i][0]) for i in range(len(kfs) - 1)]

    parts = [_num(v0)]
    prev_slope = 0.0
    for i, slope in enumerate(slopes):
        delta = slope - prev_slope
        if abs(delta) > 1e-12:
            ramp = f"max(0, {_SCROLL_VAR} - {_num(kfs[i][0])})"
            if delta > 0:
                parts.append(f"+ {_num(delta)} * {ramp}")
            else:
                parts.append(f"- {_num(-delta)} * {ramp}")
        prev_slope = slope

    if abs(prev_slope) > 1e-12:
        ramp = f"max(0, {_SCROLL_VAR} - {_num(kfs[-1][0])})"
        if prev_slope > 0:
            parts.append(f"- {_num(prev_slope)} * {ramp}")
        else:
            parts.append(f"+ {_num(-prev_slope)} * {ramp}")

    return " ".join(parts)


def _num(v: float) -> str:
    """Format a float for CSS: drop trailing '.0' for integers."""
    return str(int(v)) if v == int(v) else str(v)


# ==================================================================================================
#  ScrollimationRenderer
# ==================================================================================================


class ScrollimationRenderer(Renderer):
    """Renderer for the `scrollimation` slide type."""

    @classmethod
    def can_process(cls, ir: SlideIR) -> bool:
        """Return True if this renderer handles the given IR type."""
        return isinstance(ir, ScrollimationIR)

    def render(self, ir: SlideIR, css_namespace: str = "", *, compress: bool = True) -> SlideHTML:
        """Render a ScrollimationIR to SlideHTML."""
        assert isinstance(ir, ScrollimationIR)
        element_htmls = []
        asset_paths: list[Path] = []
        prefix = f"{css_namespace}-" if css_namespace else ""

        has_mermaid = False
        compression_stats = CompressionStats()
        for i, el in enumerate(ir.elements):
            content_html, el_stats = _render_element_content(el, compress=compress)
            compression_stats = compression_stats + el_stats
            attrs = f'class="scrollimation-element" data-element-id="{prefix}{i}"'
            if el.opacity.is_animated:
                kf_json = json.dumps(el.opacity.keyframes, separators=(",", ":"))
                attrs += f" data-opacity-keyframes='{html_escape(kf_json)}'"
            element_htmls.append(f"<div {attrs}>{content_html}</div>")
            if isinstance(el, ImageElement):
                asset_paths.append(el.image)
            elif isinstance(el, ImageSequenceElement):
                asset_paths.extend(p for p in el.image_sequence if p is not None)
            if isinstance(el, MermaidElement):
                has_mermaid = True

        inner = "\n".join(element_htmls)
        slide_type = ir.slide_type
        html = f'<div class="slide-type-{slide_type}">\n{inner}\n</div>'

        scoped_css = _build_scoped_css(ir, slide_type, prefix)

        unique_assets = list(dict.fromkeys(asset_paths))

        return SlideHTML(
            title=ir.title,
            html=html,
            scoped_css=scoped_css,
            scroll_range=int(ir.scroll_range) if ir.scroll_range > 0 else None,
            initial_scroll_position=int(ir.initial_scroll_position),
            scroll_speed=ir.scroll_speed,
            assets=tuple(unique_assets),
            snap_positions=ir.snap_positions,
            reverse=ir.reverse,
            has_mermaid=has_mermaid,
            compression_stats=compression_stats,
        )


# ==================================================================================================
#  Content rendering
# ==================================================================================================


def _render_element_content(
    el: AnyElement, *, compress: bool = True,
) -> tuple[str, CompressionStats]:
    """Render an element's content to HTML.

    Returns:
        Tuple of (html, compression stats). Only iframes contribute non-empty
        stats today; all other element types return ``CompressionStats()``.
    """
    no_stats = CompressionStats()
    if isinstance(el, ImageElement):
        return f'<img src="__asset__/{el.image.name}" alt="">', no_stats
    if isinstance(el, ImageSequenceElement):
        return _render_image_sequence_imgs(el), no_stats
    if isinstance(el, HtmlElement):
        return el.html, no_stats
    if isinstance(el, IframeElement):
        return _render_iframe(el, compress=compress)
    if isinstance(el, MermaidElement):
        return f'<pre class="mermaid">{html_escape(el.mermaid)}</pre>', no_stats
    return markdown.markdown(el.markdown, extensions=list(_MD_EXTENSIONS)), no_stats


# --------------------------------------------------------------------------
#  Iframe helpers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _IframeSrc:
    """Resolved source-attribute fragment for an iframe element.

    Encapsulates the choice between plain ``srcdoc="…"`` and the
    compressed ``data-scrolly-gz="…" data-scrolly-sink="srcdoc"`` form
    so the renderer doesn't carry the compression branch itself.
    """

    attrs: str
    stats: CompressionStats


def _resolve_iframe_src(srcdoc: str, *, compress: bool) -> _IframeSrc:
    """Resolve the source-attribute fragment for an iframe element.

    Args:
        srcdoc: The raw iframe HTML payload (un-escaped).
        compress: Whether to attempt gzip+base64 compression and prefer
            the compressed form when it clears the 5% gate.

    Returns:
        An ``_IframeSrc`` with the attribute fragment to embed in the
        ``<iframe>`` tag and the compression stats for the payload
        (zero when the payload was emitted uncompressed).
    """
    escaped = html_escape(srcdoc)
    if compress:
        result = try_compress(srcdoc.encode("utf-8"), len(escaped))
        if result.packed is not None:
            return _IframeSrc(
                attrs=f'data-scrolly-gz="{result.packed}" data-scrolly-sink="srcdoc"',
                stats=CompressionStats(compressed=1, bytes_saved=result.bytes_saved),
            )
    return _IframeSrc(
        attrs=f'srcdoc="{escaped}"',
        stats=CompressionStats(),
    )


def _render_iframe(
    el: IframeElement, *, compress: bool,
) -> tuple[str, CompressionStats]:
    """Render an iframe element to its ``<iframe …>`` HTML.

    Args:
        el: The iframe element to render.
        compress: Whether to attempt gzip+base64 compression of the
            ``srcdoc`` payload.

    Returns:
        Tuple of (rendered HTML, compression stats). Stats are non-empty
        only when the srcdoc cleared the 5% gate and was emitted in
        compressed form.
    """
    src = _resolve_iframe_src(el.iframe_html, compress=compress)
    title_attr = f' title="{html_escape(el.name)}"' if el.name else ""
    html = f'<iframe {src.attrs} sandbox="allow-scripts"{title_attr}></iframe>'
    return html, src.stats


# --------------------------------------------------------------------------
#  Image sequence helpers
# --------------------------------------------------------------------------


def _render_image_sequence_imgs(el: ImageSequenceElement) -> str:
    """Render image-sequence content: one <img> per non-empty consecutive-run, each with its own opacity ramp.

    Empty runs (``path is None``) are skipped entirely — they reserve a slot in
    the timeline but emit no markup. The crossfade keyframes on the neighbouring
    runs naturally bracket the empty period so nothing is visible during it.
    """
    runs = _image_sequence_runs(list(el.image_sequence))
    img_tags = []
    for run_idx, (path, i_start, _) in enumerate(runs):
        if path is None:
            continue
        kfs = _image_sequence_run_keyframes(el, runs, run_idx)
        kf_json = json.dumps(kfs, separators=(",", ":"))
        img_tags.append(
            f'<img data-frame-index="{i_start}" '
            f"data-opacity-keyframes='{html_escape(kf_json)}' "
            f'src="__asset__/{path.name}" alt="">'
        )
    return "\n".join(img_tags)


def _image_sequence_runs(paths: list[Path | None]) -> list[tuple[Path | None, int, int]]:
    """Group consecutive identical paths into ``(path, start_idx, end_idx)`` runs.

    Empty slots (``None``) group together the same way as identical paths.
    """
    runs: list[tuple[Path | None, int, int]] = []
    i = 0
    while i < len(paths):
        j = i
        while j + 1 < len(paths) and paths[j + 1] == paths[i]:
            j += 1
        runs.append((paths[i], i, j))
        i = j + 1
    return runs


def _image_sequence_run_keyframes(
    el: ImageSequenceElement,
    runs: list[tuple[Path, int, int]],
    run_idx: int,
) -> list[tuple[float, float]]:
    """Build opacity keyframes for one post-dedup run.

    The leading edge always uses ``fade_in`` for the first run (absent when
    ``fade_in == 0``) and the inter-run crossfade for every other run. The
    trailing edge depends on ``el.compositing``:

    - ``"blend"`` (default): each run ramps 1→0 over the crossfade into the
      next run; the last run uses ``fade_out`` (or stays at 1 if 0).
      Symmetric crossfade — leaves a brief mid-transition window where both
      neighbours are partially transparent.
    - ``"overlay"``: non-last runs hold at 1 through the *next* run's fade-in
      window, then step instantly to 0 at the moment the next run reaches
      opacity 1. The last run behaves like ``"blend"``'s last run. Keeps a
      fully-opaque underlayer through every transition (no background
      bleed-through for opaque frames).
    - ``"incremental"``: every run holds at 1 until the sequence's final
      ``hold_end``, then participates in any trailing ``fade_out``. All
      revealed runs ramp out together. Used for additive transparent layers
      that build up a composite.

    Args:
        el: The image-sequence element whose run is being laid out.
        runs: Post-dedup runs as ``(path, i_start, i_end)`` tuples, where
            ``i_start`` / ``i_end`` are inclusive scroll-grid slot indices.
        run_idx: Index of the run to emit keyframes for.

    Returns:
        Ordered list of ``(scroll_position, opacity)`` keyframes suitable
        for piecewise-linear evaluation.
    """
    _, i_start, i_end = runs[run_idx]
    hold_start = el.scroll_offset + i_start * el.frame_distance
    hold_end = el.scroll_offset + i_end * el.frame_distance + el.hold
    crossfade = el.frame_distance - el.hold

    is_first = run_idx == 0
    is_last = run_idx == len(runs) - 1

    kfs: list[tuple[float, float]] = []

    # --- leading edge -------------------------------
    if is_first:
        if el.fade_in > 0:
            kfs.append((hold_start - el.fade_in, 0.0))
        kfs.append((hold_start, 1.0))
    else:
        kfs.append((hold_start - crossfade, 0.0))
        kfs.append((hold_start, 1.0))

    # --- trailing edge ------------------------------
    if el.compositing == "blend":
        kfs.append((hold_end, 1.0))
        if is_last:
            if el.fade_out > 0:
                kfs.append((hold_end + el.fade_out, 0.0))
        else:
            kfs.append((hold_end + crossfade, 0.0))
    elif el.compositing == "overlay":
        if is_last:
            kfs.append((hold_end, 1.0))
            if el.fade_out > 0:
                kfs.append((hold_end + el.fade_out, 0.0))
        else:
            # Extended hold through the next run's fade-in, then a 1-unit
            # ramp to 0 at the instant the next run reaches full opacity.
            # See ``_STEP_RAMP_WIDTH`` for why this is a ramp rather than
            # a true step discontinuity.
            kfs.append((hold_end + crossfade, 1.0))
            kfs.append((hold_end + crossfade + _STEP_RAMP_WIDTH, 0.0))
    else:  # "incremental"
        # Hold at 1 until the sequence's final hold_end; every run
        # participates in the trailing fade-out together (if any).
        last_hold_end = el.scroll_offset + runs[-1][2] * el.frame_distance + el.hold
        kfs.append((last_hold_end, 1.0))
        if el.fade_out > 0:
            kfs.append((last_hold_end + el.fade_out, 0.0))

    return kfs


# ==================================================================================================
#  CSS generation
# ==================================================================================================


def _build_scoped_css(slide: ScrollimationIR, slide_type: str, prefix: str) -> str:
    """Build all scoped CSS rules for a scrollimation slide."""
    ns = f".slide-type-{slide_type}"
    rules: list[str] = []

    rules.append(
        f"{ns} {{\n"
        f"  position: absolute;\n"
        f"  top: 0;\n"
        f"  left: 0;\n"
        f"  width: 100%;\n"
        f"  height: 100%;\n"
        f"  transform: translateY(calc(1px * var(--scroll-position, 0)));\n"
        f"}}"
    )

    rules.append(f"{ns} .scrollimation-element {{\n  position: absolute;\n  overflow: hidden;\n}}")

    has_mermaid = False
    for i, el in enumerate(slide.elements):
        eid = f"{prefix}{i}"
        rules.append(_element_css(ns, el, eid, i))
        if isinstance(el, ImageElement):
            obj_fit_line = f"  object-fit: {el.object_fit};\n" if el.object_fit else ""
            rules.append(
                f'{ns} [data-element-id="{eid}"] img {{\n'
                f"  width: 100%;\n"
                f"  height: 100%;\n"
                f"{obj_fit_line}"
                f"  display: block;\n"
                f"}}"
            )
        elif isinstance(el, ImageSequenceElement):
            rules.extend(_image_sequence_css(ns, el, eid))
        elif isinstance(el, IframeElement):
            rules.append(
                f'{ns} [data-element-id="{eid}"] iframe {{\n'
                f"  width: 100%;\n"
                f"  height: 100%;\n"
                f"  border: 0;\n"
                f"  display: block;\n"
                f"}}"
            )
        if isinstance(el, MermaidElement):
            has_mermaid = True

    if has_mermaid:
        rules.append(f"{ns} .mermaid svg {{\n  width: 100%;\n  height: 100%;\n}}")

    return "\n\n".join(rules)


def _image_sequence_css(ns: str, el: ImageSequenceElement, eid: str) -> list[str]:
    """Build CSS rules for an image-sequence element: stacked img layout + per-run opacity ramps.

    The first ``<img>`` sits in normal flow so it establishes the container's intrinsic
    height (important when ``height: auto``); subsequent ``<img>`` tags are absolutely
    positioned to overlay it pixel-for-pixel.
    """
    sel = f'{ns} [data-element-id="{eid}"]'
    obj_fit_line = f"  object-fit: {el.object_fit};\n" if el.object_fit else ""

    rules = [
        f"{sel} img {{\n"
        f"  width: 100%;\n"
        f"  height: 100%;\n"
        f"{obj_fit_line}"
        f"  display: block;\n"
        f"}}",
        f"{sel} img:not(:first-of-type) {{\n  position: absolute;\n  top: 0;\n  left: 0;\n}}",
    ]

    runs = _image_sequence_runs(list(el.image_sequence))
    for run_idx, (path, i_start, _) in enumerate(runs):
        if path is None:
            continue  # no <img> emitted for empty runs, so no opacity rule needed
        kfs = _image_sequence_run_keyframes(el, runs, run_idx)
        expr = ramp_expr(kfs)
        if expr is None:
            opacity_val = _num(kfs[0][1])
        else:
            opacity_val = f"calc({expr})"
        rules.append(f'{sel} img[data-frame-index="{i_start}"] {{\n  opacity: {opacity_val};\n}}')

    return rules


def _element_css(ns: str, el: AnyElement, eid: str, index: int) -> str:
    """Generate the CSS rule for a single element."""
    sel = f'{ns} [data-element-id="{eid}"]'

    left_val = _vec2_component_expr(el.position, 0, "%")
    top_val = _vec2_component_expr(el.position, 1, "%")

    width = _size_dim_expr(el.width)
    height = _size_dim_expr(el.height)

    opacity_val = _scalar_expr(el.opacity)
    scale_val = _scalar_expr(el.scale)
    angle_val = _scalar_expr(el.angle, unit="deg")

    origin_x, origin_y, anchor_translate = _anchor_exprs(el.anchor)

    extra_lines = ""
    if el.position.is_animated or el.anchor.is_animated or el.angle.is_animated:
        extra_lines += "  will-change: transform;\n"
    if isinstance(el, MarkdownElement):
        extra_lines += f"  color: {el.color};\n"
        if el.text_align != "left":
            extra_lines += f"  text-align: {el.text_align};\n"
    if isinstance(el, IframeElement):
        if el.border_width > 0 or el.shadow_size > 0:
            extra_lines += "  box-sizing: border-box;\n"
        if el.border_width > 0:
            extra_lines += f"  border: {el.border_width}px solid {el.border_color};\n"
        if el.shadow_size > 0:
            extra_lines += f"  box-shadow: 0 0 {el.shadow_size}px {el.shadow_color};\n"

    return (
        f"{sel} {{\n"
        f"  left: {left_val};\n"
        f"  top: {top_val};\n"
        f"  width: {width};\n"
        f"  height: {height};\n"
        f"  transform-origin: {origin_x} {origin_y};\n"
        f"  transform: {anchor_translate}scale({scale_val}) rotate({angle_val});\n"
        f"  opacity: {opacity_val};\n"
        f"  z-index: {index};\n"
        f"{extra_lines}"
        f"}}"
    )


# --------------------------------------------------------------------------
#  Expression helpers
# --------------------------------------------------------------------------


def _scalar_expr(field: AnimatedScalar, unit: str = "") -> str:
    """Generate CSS value for a scalar animated field."""
    if not field.is_animated:
        val = _num(field.static_value)
        return f"{val}{unit}" if unit else val
    expr = ramp_expr(field.keyframes)
    if expr is None:
        val = _num(field.keyframes[0][1])
        return f"{val}{unit}" if unit else val
    if unit:
        return f"calc(({expr}) * 1{unit})"
    return f"calc({expr})"


def _vec2_component_expr(field: AnimatedVec2, axis: int, unit: str = "") -> str:
    """Generate CSS value for one component (x=0, y=1) of an animated vec2."""
    if not field.is_animated:
        val = _num(field.static_value[axis])
        return f"{val}{unit}" if unit else val
    kfs = [(at, v[axis]) for at, v in field.keyframes]
    expr = ramp_expr(kfs)
    if expr is None:
        val = _num(kfs[0][1])
        return f"{val}{unit}" if unit else val
    return f"calc(({expr}) * 1{unit})" if unit else f"calc({expr})"


def _size_dim_expr(field) -> str:
    """Generate CSS value for a size dimension."""
    if field.is_auto:
        return "auto"
    if not field.is_animated:
        return f"{_num(field.static_value)}%"
    expr = ramp_expr(field.keyframes)
    if expr is None:
        return f"{_num(field.keyframes[0][1])}%"
    return f"calc(({expr}) * 1%)"


def _anchor_exprs(field: AnimatedVec2) -> tuple[str, str, str]:
    """Generate CSS transform-origin and translate expressions for anchor."""
    if not field.is_animated:
        ax, ay = field.static_value
        origin_x = f"{_num(ax)}%"
        origin_y = f"{_num(ay)}%"
        if ax != 0 or ay != 0:
            tx = f"-{_num(ax)}%" if ax != 0 else "0%"
            ty = f"-{_num(ay)}%" if ay != 0 else "0%"
            anchor_translate = f"translate({tx}, {ty}) "
        else:
            anchor_translate = ""
        return origin_x, origin_y, anchor_translate

    kfs_x = [(at, v[0]) for at, v in field.keyframes]
    kfs_y = [(at, v[1]) for at, v in field.keyframes]

    ax_expr = ramp_expr(kfs_x)
    ay_expr = ramp_expr(kfs_y)

    if ax_expr is None:
        origin_x = f"{_num(kfs_x[0][1])}%"
        tx = f"-{_num(kfs_x[0][1])}%" if kfs_x[0][1] != 0 else "0%"
    else:
        origin_x = f"calc({ax_expr} * 1%)"
        tx = f"calc(-1 * ({ax_expr}) * 1%)"

    if ay_expr is None:
        origin_y = f"{_num(kfs_y[0][1])}%"
        ty = f"-{_num(kfs_y[0][1])}%" if kfs_y[0][1] != 0 else "0%"
    else:
        origin_y = f"calc({ay_expr} * 1%)"
        ty = f"calc(-1 * ({ay_expr}) * 1%)"

    anchor_translate = f"translate({tx}, {ty}) "
    return origin_x, origin_y, anchor_translate
