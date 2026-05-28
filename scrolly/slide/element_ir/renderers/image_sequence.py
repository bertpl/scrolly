"""``ImageSequenceRenderer`` — renders an ``ImageSequenceElement`` primitive.

This renderer stays as a primitive in v0.2.0 even though conceptually it
"wants" to be a compiler that expands into N ``ImageElement`` primitives
with computed opacity keyframes. The expansion would change the HTML
structure (one wrapper ``<div>`` containing N ``<img>`` becomes N
wrappers, one per ``<img>``), which conflicts with the byte-identical
output invariant this PR series carries. The conversion to an
``ElementCompiler`` is deferred to the worked-example regeneration step
later in v0.2.0.
"""

from __future__ import annotations

import json
from html import escape as html_escape
from pathlib import Path

from scrolly.slide.element_ir.ir import ElementIR, PrimitiveElement
from scrolly.slide.element_ir.processor import ElementRenderer, RenderContext
from scrolly.slide.element_ir.rendered import RenderedElement
from scrolly.slide.element_ir.renderers._shared import num, ramp_expr, substrate_css, wrap_element
from scrolly.slide.ir._framework.element import ImageSequenceElement

# Width (in scroll units) of the near-instantaneous opacity drop used by
# ``compositing: "overlay"`` to take a frame from full opacity to 0 once
# its successor has fully faded in. A true step discontinuity cannot be
# expressed by the CSS ``calc()``-based ramp generator (which produces
# continuous piecewise-linear functions), so we use a 1-unit ramp that
# is visually indistinguishable from a step at any reasonable scroll
# speed but keeps slope computation well-defined.
_STEP_RAMP_WIDTH = 1.0


class ImageSequenceRenderer(ElementRenderer):
    """Renders an ``ImageSequenceElement`` to a ``RenderedElement``."""

    @classmethod
    def can_process(cls, ir: ElementIR) -> bool:
        """Match `ImageSequenceElement` instances."""
        return isinstance(ir, ImageSequenceElement)

    def render(self, ir: PrimitiveElement, *, ctx: RenderContext) -> RenderedElement:
        """Render the filmstrip's ``<img>`` tags and their per-frame opacity ramps.

        Args:
            ir: The ``ImageSequenceElement`` to render.
            ctx: Per-element rendering context.

        Returns:
            A ``RenderedElement`` whose ``html`` is the wrapper plus N
            inner ``<img>`` tags (one per non-empty consecutive run);
            whose ``scoped_css`` is the substrate rule plus img-layout
            rules plus per-frame opacity rules; and whose ``assets``
            lists every non-empty path in the sequence.
        """
        assert isinstance(ir, ImageSequenceElement)
        runs = _image_sequence_runs(list(ir.image_sequence))

        # --- inner img tags + opacity keyframes ----
        img_tags: list[str] = []
        for run_idx, (path, i_start, _) in enumerate(runs):
            if path is None:
                continue
            kfs = _image_sequence_run_keyframes(ir, runs, run_idx)
            kf_json = json.dumps(kfs, separators=(",", ":"))
            img_tags.append(
                f'<img data-frame-index="{i_start}" '
                f"data-opacity-keyframes='{html_escape(kf_json)}' "
                f'src="__asset__/{path.name}" alt="">'
            )
        inner = "\n".join(img_tags)
        html = wrap_element(inner, eid=ctx.eid, el=ir)

        # --- css: substrate + nested img rules + per-frame opacity ----
        substrate = substrate_css(ir, index=ctx.index, selector_prefix=ctx.selector_prefix)

        obj_fit_line = f"  object-fit: {ir.object_fit};\n" if ir.object_fit else ""
        nested_rules: list[str] = [
            f"{ctx.selector_prefix} img {{\n  width: 100%;\n  height: 100%;\n{obj_fit_line}  display: block;\n}}",
            f"{ctx.selector_prefix} img:not(:first-of-type) {{\n  position: absolute;\n  top: 0;\n  left: 0;\n}}",
        ]
        for run_idx, (path, i_start, _) in enumerate(runs):
            if path is None:
                continue
            kfs = _image_sequence_run_keyframes(ir, runs, run_idx)
            expr = ramp_expr(kfs)
            opacity_val = num(kfs[0][1]) if expr is None else f"calc({expr})"
            nested_rules.append(
                f'{ctx.selector_prefix} img[data-frame-index="{i_start}"] {{\n  opacity: {opacity_val};\n}}'
            )

        scoped_css = "\n\n".join([substrate, *nested_rules])

        assets = tuple(p for p in ir.image_sequence if p is not None)

        # Per-frame snap stops, the same values `scrolly introspect snaps`
        # derives, so the rendered slide and introspect agree by construction.
        snap_positions = tuple(ir.snap_positions())

        return RenderedElement(html=html, scoped_css=scoped_css, assets=assets, snap_positions=snap_positions)


# ==================================================================================================
#  Run grouping + keyframe construction
# ==================================================================================================
def _image_sequence_runs(paths: list[Path | None]) -> list[tuple[Path | None, int, int]]:
    """Group consecutive identical paths into ``(path, start_idx, end_idx)`` runs.

    Empty slots (``None``) group together the same way as identical
    paths.
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
    runs: list[tuple[Path | None, int, int]],
    run_idx: int,
) -> list[tuple[float, float]]:
    """Build opacity keyframes for one post-dedup run.

    Each frame holds at full opacity over a window symmetric around its snap
    (``scroll_offset + i * frame_distance``). The half-width is
    ``hold_fraction * frame_distance / 2`` on interior sides, and
    ``hold_fraction * fade_in / 2`` / ``hold_fraction * fade_out / 2`` on the
    fade-in / fade-out sides. Crossfades and the leading/trailing fades fill
    the gaps, so the timeline runs exactly from ``scroll_offset - fade_in`` to
    ``last_snap + fade_out``.

    The trailing edge depends on ``el.compositing``:

    - ``"blend"`` (default): each run ramps 1→0 over the crossfade into the
      next run; the last run uses ``fade_out`` (or stays at 1 if 0).
    - ``"overlay"``: non-last runs hold at 1 through the *next* run's fade-in,
      then step to 0 at the moment the next run reaches opacity 1. The last
      run behaves like ``"blend"``'s last run.
    - ``"incremental"``: every run holds at 1 until the final frame's hold
      ends, then participates in any trailing ``fade_out``.

    Args:
        el: The image-sequence element whose run is being laid out.
        runs: Post-dedup runs as ``(path, i_start, i_end)`` tuples, where
            ``i_start`` / ``i_end`` are inclusive scroll-grid slot indices.
        run_idx: Index of the run to emit keyframes for.

    Returns:
        Ordered list of ``(scroll_position, opacity)`` keyframes suitable for
        piecewise-linear evaluation (consecutive duplicates collapsed).
    """
    _, i_start, i_end = runs[run_idx]
    n = len(el.image_sequence)
    f = el.hold_fraction
    crossfade = el.frame_distance * (1 - f)
    interior_half = f * el.frame_distance / 2

    is_first = run_idx == 0
    is_last = run_idx == len(runs) - 1

    leading_half = (f * el.fade_in / 2) if is_first else interior_half
    trailing_half = (f * el.fade_out / 2) if is_last else interior_half
    hold_lo = el.scroll_offset + i_start * el.frame_distance - leading_half
    hold_hi = el.scroll_offset + i_end * el.frame_distance + trailing_half
    timeline_end = el.scroll_offset + (n - 1) * el.frame_distance + el.fade_out

    kfs: list[tuple[float, float]] = []

    # --- leading edge -------------------------------
    if is_first:
        if el.fade_in > 0:
            kfs.append((el.scroll_offset - el.fade_in, 0.0))
        kfs.append((hold_lo, 1.0))
    else:
        kfs.append((hold_lo - crossfade, 0.0))
        kfs.append((hold_lo, 1.0))

    # --- trailing edge ------------------------------
    if el.compositing == "blend":
        kfs.append((hold_hi, 1.0))
        if is_last:
            if el.fade_out > 0:
                kfs.append((timeline_end, 0.0))
        else:
            kfs.append((hold_hi + crossfade, 0.0))
    elif el.compositing == "overlay":
        if is_last:
            kfs.append((hold_hi, 1.0))
            if el.fade_out > 0:
                kfs.append((timeline_end, 0.0))
        else:
            # Hold through the next run's fade-in, then a 1-unit ramp to 0 at
            # the instant the next run reaches full opacity.
            kfs.append((hold_hi + crossfade, 1.0))
            kfs.append((hold_hi + crossfade + _STEP_RAMP_WIDTH, 0.0))
    else:  # "incremental"
        last_hold_hi = el.scroll_offset + runs[-1][2] * el.frame_distance + f * el.fade_out / 2
        kfs.append((last_hold_hi, 1.0))
        if el.fade_out > 0:
            kfs.append((timeline_end, 0.0))

    # A zero-width hold (hold_fraction = 0, or a single-slot run with no
    # fades) can emit two identical keyframes at the snap; collapse them so
    # the piecewise-linear ramp has no zero-length segment.
    deduped = [kfs[0]]
    for kf in kfs[1:]:
        if kf != deduped[-1]:
            deduped.append(kf)
    return deduped
