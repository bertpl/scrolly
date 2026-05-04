---
initial_scroll_position: 0
---

# Background

This slide is intentionally long so that its content overflows the viewport
at typical sizes. The slide-container's `ResizeObserver` measures the
overflow and exposes a live `scroll_range` to the runtime; canvas.js wires
wheel, trackpad, and scrollbar-drag input into a single `--scroll-position`
custom property; the chunk's CSS translates the body upward by that amount.

## Why content-driven scroll

scrolly's slides live on a 2D grid where each cell renders at viewport
dimensions. That works beautifully for fixed-size slides, but it breaks
the moment a slide's natural content height depends on the viewport —
which is true for almost any prose slide rendered to anyone's screen.

If `scroll_range` were author-declared at build time, we'd have to write
a different number for every viewport size we wanted to support. The
runtime sees the actual size of the rendered content and the actual
viewport; it knows the right answer with zero authorial input. The
chunk-metadata channel models this with a discriminator: `None` =
content-driven (auto-detect), `int` = fixed-timeline (used by future
scrollimation slides whose range is an authorial parameter).

## Try it

- **Wheel or two-finger trackpad scroll** — moves through the content.
- **Drag the scrollbar thumb** on the left edge — same state path.
- **Resize the window** — the scrollbar adapts; the range recomputes
  automatically because `ResizeObserver` fires on every layout change.
- **Press Left or zoom out, then come back** — the scroll position is
  remembered.
- **Press an arrow key that has no edge that side** — Layer A's red
  no-target glow fires; scroll input is reserved for within-slide.

## Implementation snapshot

The data carried per slide in the embedded `#scrolly-deck` JSON:

```json5
{
  "title": "Background",
  "position": [3, 0],
  "scroll_range": null,        // null → content-driven; int → fixed-timeline
  "scroll_speed": 1.0,         // wheel-pixel multiplier
  "initial_scroll_position": 0,
  "edges": { "left": [...] }
}
```

The CSS rule that does the actual scrolling:

```css
.slide-container.has-scroll .chunk {
  transform: translateY(calc(-1px * var(--scroll-position, 0)));
}
```

That's the entire content-driven scroll mechanism on the chunk side.
Everything else — input capture, range measurement, position state,
scrollbar thumb sizing, drag handling — lives in canvas.js as Layer A
plumbing that any future slide type can build on.

## Notes for future slide types

- **`scrollable` does not exist as a separate type.** `static` auto-scrolls
  whenever its content overflows; if it fits, `scroll_range` is 0 and the
  scrollbar stays hidden.
- **`scrollimation` (v0.0.6)** will use the same `--scroll-position` channel
  but in fixed-timeline mode: an author-declared `scroll_range` represents
  the timeline length, and layer animations adapt to viewport via
  viewport-relative units inside the animation rather than via the range.
- **Per-segment easing, track-click on the scrollbar, auto-hide on idle,
  CSS scroll-driven animations** — all on the deferred list. The current
  contract is shaped to admit them later without breaking changes.

## Limitations to know about

- The `4rem` padding inside `.chunk` keeps content clear of the
  zoom-out control and edge arrows at rest. While scrolling, content does
  pass behind those nav-layer elements — the navigation layer sits above
  the canvas (z-index 20 > the canvas's auto). A fade mask at the top
  and bottom of `.subcanvas` could mitigate this; deferred until a real
  deck makes the overlap feel wrong.
- Horizontal scroll inputs (`deltaX`) are ignored. Scrolly's scroll
  contract is one-dimensional.
- Pan-transition handling: scroll input is blocked during the body
  `view-transitioning` class. If a user mashes arrow-key navigation while
  scroll-tracking, the pan animation runs without scroll-state churn.

## What's next

Resize the window to see the scroll range adapt. Drag the scrollbar to
the bottom and notice how it stays grabbable thanks to the 40-pixel
minimum thumb height. Press Left to go back to `notes` and you'll see
the scroll position you left this slide at — DOM continuity makes the
state survive navigation for free.
