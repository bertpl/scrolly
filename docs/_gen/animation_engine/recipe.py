"""Animation-recipe schema + loader.

The recipe is a JSON5 document (``.json`` extension, matching scrolly's
own deck files) that fully specifies one hero animation: what to capture
(``steps``) and what to draw on top (``overlays``). It is the only input
to the engine, so the same ``make hero-animation`` invocation reproduces
the animation.

Two timelines:

- ``steps`` — the storyboard: ordered ``hold`` / ``view`` (pan or zoom
  transition) / ``scroll`` (over one slide) entries with durations.
- ``overlays`` — the compositing layer: ``caption`` / ``cursor`` /
  ``click`` / ``key`` entries, each anchored to a step index plus a
  fractional span within that step, so retiming a step does not shift
  every later overlay.

This module is pure (JSON5 + stdlib only); it does not import Playwright
or Pillow, so it loads without the optional ``capture`` group.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json5


# ==================================================================================================
#  Global config
# ==================================================================================================
@dataclass(frozen=True)
class Viewport:
    """Browser viewport the deck is captured at."""

    width: int
    height: int
    scale: int


@dataclass(frozen=True)
class Output:
    """Where and how the assembled animation is written."""

    path: str
    loop: bool = True
    quality: int = 80


@dataclass(frozen=True)
class Border:
    """A solid square frame added around every composited frame.

    `width` is in absolute output pixels (not scaled by `Viewport.scale`);
    `width == 0` disables the border.
    """

    width: int = 0
    color: str = "#000000"


@dataclass(frozen=True)
class ProgressBar:
    """A wall-clock progress bar added below every composited frame.

    `height` is in absolute output pixels (not scaled by `Viewport.scale`);
    `height == 0` disables the bar. The elapsed fraction is filled with
    `color`, the remainder with `track_color`.
    """

    height: int = 0
    color: str = "#000000"
    track_color: str = "#000000"


# ==================================================================================================
#  Steps — the storyboard timeline
# ==================================================================================================
@dataclass(frozen=True)
class HoldStep:
    """Hold a static view (no motion) for ``ms`` milliseconds."""

    ms: int
    view: str  # "deck" | "slide"
    slide: str | None = None


@dataclass(frozen=True)
class ViewStep:
    """A pan (slide change) and/or zoom (deck <-> slide) transition.

    Either ``to`` (zoom target) or ``slide`` (pan target) or both is
    set; the capture stage issues the corresponding hook calls and
    samples frames across the CSS transition.
    """

    ms: int
    to: str | None = None  # "deck" | "slide"
    slide: str | None = None


@dataclass(frozen=True)
class ScrollStep:
    """Scroll one slide from ``start`` to ``end`` (normalized 0..1)."""

    slide: str
    start: float
    end: float
    ms: int
    ease: str = "linear"  # "linear" | "ease-in-out"


Step = HoldStep | ViewStep | ScrollStep


# ==================================================================================================
#  Overlays — the compositing layer
# ==================================================================================================
@dataclass(frozen=True)
class CaptionOverlay:
    """Text caption shown over a fractional span of a step."""

    step: int
    span: tuple[float, float]
    text: str
    anchor: str = "bottom-center"
    fade_ms: int = 200


@dataclass(frozen=True)
class CursorOverlay:
    """A cursor sprite gliding from ``start`` to ``end`` over a span.

    Coordinates are in capture-viewport pixels (pre-scale).
    """

    step: int
    span: tuple[float, float]
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class ClickOverlay:
    """A click pulse at ``pos`` at a single moment within a step."""

    step: int
    at: float
    pos: tuple[float, float]


@dataclass(frozen=True)
class KeyOverlay:
    """A key-press chip showing ``label`` at a moment within a step."""

    step: int
    at: float
    label: str


@dataclass(frozen=True)
class ScrollHintOverlay:
    """An animated scroll-mouse glyph shown over a fractional span of a step."""

    step: int
    span: tuple[float, float]
    pos: tuple[float, float]


Overlay = CaptionOverlay | CursorOverlay | ClickOverlay | KeyOverlay | ScrollHintOverlay


# ==================================================================================================
#  Recipe
# ==================================================================================================
@dataclass(frozen=True)
class Recipe:
    """A fully-specified hero animation."""

    deck: str
    viewport: Viewport
    fps: int
    output: Output
    steps: tuple[Step, ...]
    overlays: tuple[Overlay, ...]
    border: Border = field(default_factory=Border)
    progress_bar: ProgressBar = field(default_factory=ProgressBar)


# ==================================================================================================
#  Loading + validation
# ==================================================================================================
def load_recipe(path: str | Path) -> Recipe:
    """Load and validate a recipe from a JSON5 file.

    Args:
        path: Path to the ``.json`` (JSON5 syntax) recipe file.

    Returns:
        The parsed, validated `Recipe`.

    Raises:
        ValueError: If the document is malformed or fails validation.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json5.loads(text)
    except ValueError as exc:
        raise ValueError(f"recipe {path}: invalid JSON5: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"recipe {path}: top level must be an object")
    return parse_recipe(data)


def parse_recipe(data: dict[str, Any]) -> Recipe:
    """Validate a recipe dict and build a `Recipe`.

    Args:
        data: The decoded recipe document.

    Returns:
        The validated `Recipe`.

    Raises:
        ValueError: On any missing / out-of-range / wrong-typed field.
    """
    deck = _req(data, "deck", str)
    fps = _req(data, "fps", int)
    if fps <= 0:
        raise ValueError("fps must be > 0")

    viewport = _parse_viewport(_req(data, "viewport", dict))
    output = _parse_output(_req(data, "output", dict))

    raw_steps = _req(data, "steps", list)
    if not raw_steps:
        raise ValueError("steps must be non-empty")
    steps = tuple(_parse_step(s, i) for i, s in enumerate(raw_steps))

    overlays = tuple(_parse_overlay(o, len(steps)) for o in data.get("overlays", []))

    border = _parse_border(_opt_dict(data, "border"))
    progress_bar = _parse_progress_bar(_opt_dict(data, "progress_bar"))

    return Recipe(
        deck=deck,
        viewport=viewport,
        fps=fps,
        output=output,
        steps=steps,
        overlays=overlays,
        border=border,
        progress_bar=progress_bar,
    )


# --- global config --------------------------------
def _parse_viewport(d: dict[str, Any]) -> Viewport:
    return Viewport(width=_req(d, "width", int), height=_req(d, "height", int), scale=_req(d, "scale", int))


def _parse_output(d: dict[str, Any]) -> Output:
    return Output(
        path=_req(d, "path", str),
        loop=bool(d.get("loop", True)),
        quality=int(d.get("quality", 80)),
    )


def _parse_border(d: dict[str, Any]) -> Border:
    return Border(
        width=_nonneg_int(d, "width", 0),
        color=_color(d, "color", "#000000"),
    )


def _parse_progress_bar(d: dict[str, Any]) -> ProgressBar:
    return ProgressBar(
        height=_nonneg_int(d, "height", 0),
        color=_color(d, "color", "#000000"),
        track_color=_color(d, "track_color", "#000000"),
    )


# --- steps ----------------------------------------
def _parse_step(d: Any, index: int) -> Step:
    """Dispatch one raw step dict to its typed `Step`."""
    if not isinstance(d, dict):
        raise ValueError(f"step {index}: must be an object")
    kind = _req(d, "type", str)
    ms = _req(d, "ms", int)
    if ms <= 0:
        raise ValueError(f"step {index}: ms must be > 0")

    if kind == "hold":
        view = _req(d, "view", str)
        _check_view(view, f"step {index}")
        return HoldStep(ms=ms, view=view, slide=d.get("slide"))
    if kind == "view":
        to = d.get("to")
        slide = d.get("slide")
        if to is None and slide is None:
            raise ValueError(f"step {index}: view step needs 'to' and/or 'slide'")
        if to is not None:
            _check_view(to, f"step {index}")
        return ViewStep(ms=ms, to=to, slide=slide)
    if kind == "scroll":
        return ScrollStep(
            slide=_req(d, "slide", str),
            start=_fraction(d, "from", index),
            end=_fraction(d, "to", index),
            ms=ms,
            ease=d.get("ease", "linear"),
        )
    raise ValueError(f"step {index}: unknown type {kind!r}")


# --- overlays -------------------------------------
def _parse_overlay(d: Any, n_steps: int) -> Overlay:
    """Dispatch one raw overlay dict to its typed `Overlay`."""
    if not isinstance(d, dict):
        raise ValueError("overlay: must be an object")
    kind = _req(d, "type", str)
    step = _req(d, "step", int)
    if not 0 <= step < n_steps:
        raise ValueError(f"overlay: step {step} out of range (0..{n_steps - 1})")

    if kind == "caption":
        return CaptionOverlay(
            step=step,
            span=_span(d, "span"),
            text=_req(d, "text", str),
            anchor=d.get("anchor", "bottom-center"),
            fade_ms=int(d.get("fade_ms", 200)),
        )
    if kind == "cursor":
        return CursorOverlay(step=step, span=_span(d, "span"), start=_xy(d, "from"), end=_xy(d, "to"))
    if kind == "click":
        return ClickOverlay(step=step, at=_at(d), pos=_xy(d, "pos"))
    if kind == "key":
        return KeyOverlay(step=step, at=_at(d), label=_req(d, "label", str))
    if kind == "scroll_hint":
        return ScrollHintOverlay(step=step, span=_span(d, "span"), pos=_xy(d, "pos"))
    raise ValueError(f"overlay: unknown type {kind!r}")


# --- field helpers --------------------------------
def _req(d: dict[str, Any], key: str, typ: type) -> Any:
    if key not in d:
        raise ValueError(f"missing required field {key!r}")
    value = d[key]
    # bool is a subclass of int; reject it where a real int is wanted.
    if typ is int and isinstance(value, bool):
        raise ValueError(f"field {key!r} must be {typ.__name__}, got bool")
    if not isinstance(value, typ):
        raise ValueError(f"field {key!r} must be {typ.__name__}, got {type(value).__name__}")
    return value


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _opt_dict(d: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``d[key]`` (which must be an object) or ``{}`` if absent."""
    if key not in d:
        return {}
    value = d[key]
    if not isinstance(value, dict):
        raise ValueError(f"field {key!r} must be an object")
    return value


def _nonneg_int(d: dict[str, Any], key: str, default: int) -> int:
    """Read a non-negative int field, or ``default`` if absent."""
    if key not in d:
        return default
    value = d[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"field {key!r} must be a non-negative int")
    if value < 0:
        raise ValueError(f"field {key!r} must be >= 0, got {value}")
    return value


def _color(d: dict[str, Any], key: str, default: str) -> str:
    """Read an opaque hex color (#RGB / #RRGGBB) field, or ``default`` if absent."""
    if key not in d:
        return default
    value = d[key]
    if not isinstance(value, str) or not _HEX_COLOR_RE.match(value):
        raise ValueError(f"field {key!r} must be an opaque hex color (#RGB or #RRGGBB), got {value!r}")
    return value


def _check_view(value: str, where: str) -> None:
    if value not in ("deck", "slide"):
        raise ValueError(f"{where}: view must be 'deck' or 'slide', got {value!r}")


def _fraction(d: dict[str, Any], key: str, index: int) -> float:
    value = d.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"step {index}: {key!r} must be a number")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"step {index}: {key!r} must be in [0, 1], got {value}")
    return value


def _span(d: dict[str, Any], key: str) -> tuple[float, float]:
    value = d.get(key)
    if not (isinstance(value, list) and len(value) == 2):
        raise ValueError(f"{key!r} must be a [start, end] pair")
    start, end = float(value[0]), float(value[1])
    if not (0.0 <= start <= 1.0 and 0.0 <= end <= 1.0):
        raise ValueError(f"{key!r} entries must be in [0, 1]")
    if start > end:
        raise ValueError(f"{key!r} start must be <= end")
    return (start, end)


def _xy(d: dict[str, Any], key: str) -> tuple[float, float]:
    value = d.get(key)
    if not (isinstance(value, list) and len(value) == 2):
        raise ValueError(f"{key!r} must be an [x, y] pair")
    return (float(value[0]), float(value[1]))


def _at(d: dict[str, Any]) -> float:
    value = d.get("at")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("'at' must be a number in [0, 1]")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"'at' must be in [0, 1], got {value}")
    return value
