"""Stage 2 — Pillow overlay compositing + GIF / WebP assembly.

Reads the raw frames captured by stage 1, paints the recipe's overlays
(`FramePlan.overlay_draws`) onto them — captions, a cursor sprite, click
pulses, key chips — and hands the composited frames to gifski (GIF)
and / or img2webp (WebP) for assembly, one per output block the recipe
declares. This stage is browser-free, so re-running it after an
overlay-only recipe change is fast (the slow capture frames are reused).

Overlay coordinates in the recipe are capture-viewport pixels; frames
are rendered at ``deviceScaleFactor`` (``viewport.scale``), so all draw
coordinates are multiplied by ``scale`` here.

Requires the optional ``capture`` dependency group (Pillow) and, on
PATH, a ``gifski`` and / or ``img2webp`` binary per the requested
format (from ``make capture-setup``). Pillow is imported lazily so the
rest of the engine loads without it.
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

# Key chips can show arrow glyphs (↑ ↓ ← →), which the macOS Helvetica face
# Pillow loads from the .ttc does NOT cover (they render as tofu boxes). This
# list front-loads fonts that do cover the arrows; Helvetica trails as a
# last resort so plain labels (D / H / Z) still render if nothing else loads.
_KEY_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
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
    output_scale = recipe.viewport.output_scale
    out_dir = work_dir / "composited"
    _prepare(out_dir)
    fonts = _Fonts(
        caption=_load_font(round(26 * scale)),
        key=_load_font(round(20 * scale), _KEY_FONT_CANDIDATES),
    )

    for index in range(plan.total_frames):
        frame = Image.open(frames_dir / frame_filename(index)).convert("RGBA")
        draws = plan.overlay_draws[index]
        if draws:
            _paint(frame, draws, scale, fonts)
        if output_scale != scale:
            frame = _downscale(frame, scale, output_scale)
        frame = _add_chrome(frame, recipe, index, plan.total_frames)
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


# --- supersample downscale ------------------------
def _downscale(frame, scale: int, output_scale: float):
    """Lanczos-downsample a frame from capture to delivery resolution.

    The deck is captured at `scale`x for crisp supersampling and the
    asset is delivered at `output_scale`x (CSS-relative), so this
    resamples by `output_scale / scale`. Runs before `_add_chrome`, so
    the chrome's absolute-pixel sizes land crisp at the delivery
    resolution rather than being blurred by the downscale.

    Only called when `output_scale != scale`; the caller skips it
    entirely when capture and delivery resolutions match.

    Args:
        frame: The composited RGBA frame at capture resolution.
        scale: Capture device-pixel scale.
        output_scale: Delivery device-pixel scale (< `scale`).

    Returns:
        The resampled frame at delivery resolution.
    """
    from PIL import Image

    factor = output_scale / scale
    w, h = frame.size
    return frame.resize((round(w * factor), round(h * factor)), Image.Resampling.LANCZOS)


# --- chrome (border + progress bar) ---------------
def _add_chrome(frame, recipe: Recipe, index: int, total: int):
    """Add the progress bar under the frame, then the border around it.

    Both *extend* the canvas — they never overwrite captured frame content.
    Sizes are absolute output pixels (not scaled by `viewport.scale`). The
    progress bar fills its leftmost ``(index + 1) / total`` with the fill
    color and the remainder with the track color.

    Args:
        frame: The composited RGBA frame (after overlays).
        recipe: The recipe carrying `border` / `progress_bar` config.
        index: This frame's 0-based index.
        total: Total frame count (for the wall-clock fill fraction).

    Returns:
        The (possibly larger) RGBA frame with chrome added.
    """
    from PIL import Image, ImageDraw

    img = frame

    bar = recipe.progress_bar
    if bar.height > 0:
        w, h = img.size
        out = Image.new("RGBA", (w, h + bar.height), _rgba(bar.track_color))
        out.paste(img, (0, 0))
        fill_w = round(w * (index + 1) / total)
        if fill_w > 0:
            ImageDraw.Draw(out).rectangle([0, h, fill_w - 1, h + bar.height - 1], fill=_rgba(bar.color))
        img = out

    border = recipe.border
    if border.width > 0:
        w, h = img.size
        bw = border.width
        out = Image.new("RGBA", (w + 2 * bw, h + 2 * bw), _rgba(border.color))
        out.paste(img, (bw, bw))
        img = out

    return img


def _rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Parse an opaque hex color (#RGB / #RRGGBB) into an (r, g, b, 255) tuple."""
    from PIL import ImageColor

    r, g, b = ImageColor.getrgb(hex_color)[:3]
    return (r, g, b, 255)


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
def _load_font(size: int, candidates: tuple[str, ...] = _FONT_CANDIDATES):
    """Load a TrueType font at ``size`` from ``candidates``, else Pillow's default."""
    from PIL import ImageFont

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --- assembly -------------------------------------
def _assemble(recipe: Recipe, plan: FramePlan, composited_dir: Path) -> list[Path]:
    """Assemble composited frames into each configured output animation.

    Runs gifski and / or img2webp over the same PNG frame sequence — one
    per output block present in the recipe (`output.gif` / `output.webp`).
    Consuming the frames directly, rather than transcoding a finished GIF,
    keeps the WebP path free of a quantized-256-color round-trip.

    Args:
        recipe: The validated recipe (fps / output config).
        plan: The frame plan (for the frame count).
        composited_dir: Directory of composited ``frame-NNNNN.png``.

    Returns:
        The written output paths, one per output block present.
    """
    frames = [str(composited_dir / frame_filename(i)) for i in range(plan.total_frames)]
    output = recipe.output
    outputs: list[Path] = []
    if output.gif is not None:
        out = Path(output.gif.path)
        outputs.append(_encode(_gif_cmd(recipe, out, frames, _frame_width(frames[0])), out))
    if output.webp is not None:
        out = Path(output.webp.path)
        outputs.append(_encode(_webp_cmd(recipe, out, frames), out))
    return outputs


def _encode(cmd: list[str], out: Path) -> Path:
    """Run one assembly command, creating the output's parent directory first."""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    return out


def _frame_width(frame_path: str) -> int:
    """Read a composited frame's pixel width (gifski renders at this native width)."""
    from PIL import Image

    with Image.open(frame_path) as im:
        return im.width


def _gif_cmd(recipe: Recipe, out: Path, frames: list[str], width: int) -> list[str]:
    """Build the gifski command for the GIF output.

    Passes ``--width`` at the composited frame's native width so gifski
    renders 1:1 rather than applying its built-in downsize cap — leaving
    `viewport.output_scale` the single resolution control, shared with the
    WebP path.

    Args:
        recipe: The validated recipe (fps / output config).
        out: The GIF file to write.
        frames: Ordered composited PNG frame paths.
        width: Native composited frame width, passed as gifski ``--width``.

    Returns:
        The full ``gifski`` argument vector.
    """
    cmd = [
        "gifski",
        "--fps",
        str(recipe.fps),
        "--quality",
        str(recipe.output.gif.quality),
        "--width",
        str(width),
        "-o",
        str(out),
    ]
    if not recipe.output.loop:
        cmd += ["--repeat", "-1"]
    return cmd + frames


def _webp_cmd(recipe: Recipe, out: Path, frames: list[str]) -> list[str]:
    """Build the img2webp command for the WebP output.

    fps becomes a per-frame duration (`-d <ms>`); ``output.loop == False``
    maps to a single play-through (`-loop 1`, against the infinite-loop
    default). The `webp.mode` knob selects the libwebp coding strategy.

    Args:
        recipe: The validated recipe (fps / output / webp config).
        out: The WebP file to write.
        frames: Ordered PNG frame paths.

    Returns:
        The full ``img2webp`` argument vector.
    """
    webp = recipe.output.webp
    duration_ms = round(1000 / recipe.fps)
    cmd = ["img2webp", "-loop", "0" if recipe.output.loop else "1"]
    cmd += _webp_file_opts(webp)
    cmd += ["-d", str(duration_ms), "-m", str(webp.method)]
    cmd += _webp_quality_opts(webp)
    cmd += frames
    cmd += ["-o", str(out)]
    return cmd


def _webp_file_opts(webp) -> list[str]:
    """File-level img2webp flags (apply to the whole sequence): size minimization + mixed / near-lossless modes."""
    opts: list[str] = []
    if webp.min_size:
        opts.append("-min_size")
    if webp.mode == "mixed":
        opts.append("-mixed")
    elif webp.mode == "near_lossless":
        opts += ["-near_lossless", str(webp.near_lossless)]
    return opts


def _webp_quality_opts(webp) -> list[str]:
    """Per-frame img2webp flags selecting the coding mode and (where it applies) quality."""
    if webp.mode == "lossless":
        return ["-lossless"]
    if webp.mode == "near_lossless":
        return []  # -near_lossless (file-level) implies lossless coding; -q does not apply
    if webp.mode == "mixed":
        return ["-q", str(webp.quality)]  # tunes the lossy-coded frames
    return ["-lossy", "-q", str(webp.quality)]


def _prepare(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("frame-*.png"):
        stale.unlink()
