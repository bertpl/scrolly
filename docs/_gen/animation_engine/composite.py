"""Stage 2 — Pillow overlay compositing + gifski assembly.

Reads the raw frames captured by stage 1, paints the recipe's overlays
(`FramePlan.overlay_draws`) onto them — captions, a cursor sprite, click
pulses, key chips — and hands the composited frames to gifski for
assembly. This stage is browser-free, so re-running it after an
overlay-only recipe change is fast (the slow capture frames are reused).

Overlay coordinates in the recipe are capture-viewport pixels; frames
are rendered at ``deviceScaleFactor`` (``viewport.scale``), so all draw
coordinates are multiplied by ``scale`` here.

Requires the optional ``capture`` dependency group (Pillow) and a
``gifski`` binary on PATH (from ``make capture-setup``). Pillow is
imported lazily so the rest of the engine loads without it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .plan import CaptionDraw, ClickDraw, CursorDraw, FramePlan, KeyDraw, ScrollHintDraw, frame_filename
from .recipe import Recipe

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


# ==================================================================================================
#  Entry point
# ==================================================================================================
def run_composite(recipe: Recipe, plan: FramePlan, frames_dir: Path, work_dir: Path) -> Path:
    """Paint overlays onto cached frames and assemble the animation.

    Args:
        recipe: The validated recipe (scale / fps / output).
        plan: The frame plan whose `overlay_draws` are painted.
        frames_dir: Directory of raw ``frame-NNNNN.png`` from stage 1.
        work_dir: Scratch directory; composited frames go in a
            ``composited/`` subdirectory.

    Returns:
        Path to the assembled output animation.
    """
    from PIL import Image

    scale = recipe.viewport.scale
    out_dir = work_dir / "composited"
    _prepare(out_dir)
    fonts = _Fonts(caption=_load_font(round(26 * scale)), key=_load_font(round(20 * scale)))

    for index in range(plan.total_frames):
        frame = Image.open(frames_dir / frame_filename(index)).convert("RGBA")
        draws = plan.overlay_draws[index]
        if draws:
            _paint(frame, draws, scale, fonts)
        frame.convert("RGB").save(out_dir / frame_filename(index))

    return _assemble(recipe, plan, out_dir)


# --- painting -------------------------------------
class _Fonts:
    """Pre-loaded fonts for captions and key chips."""

    def __init__(self, caption, key) -> None:
        self.caption = caption
        self.key = key


def _paint(frame, draws, scale: int, fonts: _Fonts) -> None:
    """Composite all overlay draws for one frame onto ``frame`` (RGBA)."""
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for d in draws:
        if isinstance(d, CaptionDraw):
            _draw_caption(draw, frame.size, d, scale, fonts.caption)
        elif isinstance(d, CursorDraw):
            _draw_cursor(draw, d.pos, scale)
        elif isinstance(d, ClickDraw):
            _draw_click(draw, d, scale)
        elif isinstance(d, KeyDraw):
            _draw_key(draw, frame.size, d, scale, fonts.key)
        elif isinstance(d, ScrollHintDraw):
            _draw_scroll_hint(draw, d, scale)
    frame.alpha_composite(layer)


def _draw_caption(draw, size, d: CaptionDraw, scale: int, font) -> None:
    """Draw a captioned pill at the requested anchor and opacity."""
    width, height = size
    alpha = round(d.alpha * 255)
    pad = round(16 * scale)
    left, top, right, bottom = draw.textbbox((0, 0), d.text, font=font)
    box_w, box_h = (right - left) + 2 * pad, (bottom - top) + 2 * pad
    x, y = _anchor_xy(d.anchor, width, height, box_w, box_h, round(30 * scale))
    draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=round(12 * scale), fill=(0, 0, 0, round(alpha * 0.6)))
    draw.text((x + pad - left, y + pad - top), d.text, font=font, fill=(255, 255, 255, alpha))


def _draw_cursor(draw, pos: tuple[float, float], scale: int) -> None:
    """Draw a simple arrow-cursor sprite with its tip at ``pos``."""
    x, y = pos[0] * scale, pos[1] * scale
    s = 34 * scale
    points = [
        (x, y),
        (x, y + 0.80 * s),
        (x + 0.22 * s, y + 0.60 * s),
        (x + 0.36 * s, y + 0.92 * s),
        (x + 0.52 * s, y + 0.86 * s),
        (x + 0.38 * s, y + 0.54 * s),
        (x + 0.62 * s, y + 0.54 * s),
    ]
    draw.polygon(points, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))


def _draw_click(draw, d: ClickDraw, scale: int) -> None:
    """Draw an expanding, fading ring for a click pulse.

    Amber on a white halo so the pulse reads on both the light deck map
    and darker slide content (a plain white ring vanished on the deck).
    """
    x, y = d.pos[0] * scale, d.pos[1] * scale
    radius = (14 + d.progress * 46) * scale
    alpha = round(255 * (1.0 - d.progress))
    box = [x - radius, y - radius, x + radius, y + radius]
    draw.ellipse(box, outline=(255, 255, 255, alpha), width=max(5, round(9 * scale)))
    draw.ellipse(box, outline=(255, 138, 0, alpha), width=max(3, round(5 * scale)))


def _draw_key(draw, size, d: KeyDraw, scale: int, font) -> None:
    """Draw a centered key-press chip near the top of the frame."""
    width, _height = size
    alpha = round(d.alpha * 255)
    pad = round(14 * scale)
    left, top, right, bottom = draw.textbbox((0, 0), d.label, font=font)
    text_w, text_h = right - left, bottom - top
    box_w, box_h = max(text_w + 2 * pad, round(40 * scale)), text_h + 2 * pad
    x, y = (width - box_w) // 2, round(60 * scale)
    draw.rounded_rectangle(
        [x, y, x + box_w, y + box_h],
        radius=round(8 * scale),
        fill=(20, 20, 20, alpha),
        outline=(255, 255, 255, alpha),
        width=max(1, round(2 * scale)),
    )
    draw.text((x + (box_w - text_w) // 2 - left, y + pad - top), d.label, font=font, fill=(255, 255, 255, alpha))


def _draw_scroll_hint(draw, d: ScrollHintDraw, scale: int) -> None:
    """Draw a 'scroll down' mouse glyph; the wheel pill ticks downward."""
    cx, cy = d.pos[0] * scale, d.pos[1] * scale
    w, h = 30 * scale, 48 * scale
    body = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    draw.rounded_rectangle(
        body, radius=w / 2, fill=(255, 255, 255, 205), outline=(40, 40, 40, 235), width=max(2, round(3 * scale))
    )
    # Wheel pill ticks down from the top third and fades — reads as scroll-down.
    top = cy - h / 2
    wy = top + h * 0.18 + d.phase * h * 0.30
    r = max(2, round(3.4 * scale))
    a = round(235 * (1.0 - 0.7 * d.phase))
    draw.rounded_rectangle([cx - r, wy - r * 1.7, cx + r, wy + r * 1.7], radius=r, fill=(40, 40, 40, a))


def _anchor_xy(anchor: str, width: int, height: int, box_w: int, box_h: int, margin: int) -> tuple[int, int]:
    """Top-left placement of a box for a named anchor."""
    cx = (width - box_w) // 2
    if anchor == "top-center":
        return cx, margin
    if anchor == "center":
        return cx, (height - box_h) // 2
    return cx, height - box_h - margin  # bottom-center (default)


# --- fonts ----------------------------------------
def _load_font(size: int):
    """Load a TrueType font at ``size``, falling back to Pillow's default."""
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --- assembly -------------------------------------
def _assemble(recipe: Recipe, plan: FramePlan, composited_dir: Path) -> Path:
    """Assemble composited frames into the output animation via gifski."""
    out = Path(recipe.output.path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = [str(composited_dir / frame_filename(i)) for i in range(plan.total_frames)]
    cmd = ["gifski", "--fps", str(recipe.fps), "--quality", str(recipe.output.quality), "-o", str(out)]
    if not recipe.output.loop:
        cmd += ["--repeat", "-1"]
    cmd += frames
    subprocess.run(cmd, check=True)
    return out


def _prepare(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("frame-*.png"):
        stale.unlink()
