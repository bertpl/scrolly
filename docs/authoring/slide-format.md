# Slide format (`.slide.json`)

Each slide is a `.slide.json` file — JSON5 on the `.json` extension.
It declares the slide's title, its elements, and the properties that
control how it scrolls.

## Core fields

- **`title`** — the slide's title, required on every slide.
- **elements** — the stack of [elements](../concepts/elements.md) that
  make up the slide's content, each with its own position, size, and
  optional [animation](../concepts/animation.md).

## Scroll behavior

- **`scroll_range`** — how far the slide scrolls, as a number, or
  `"auto"` (default) for content-driven height; `0` pins the slide
  static. Animation keyframes are expressed in these units.
- **`snap_positions`** — scroll offsets the view eases to, letting the
  slide rest on meaningful moments.
- **`reverse`** — when true, flips the scroll direction so the thumb
  starts at the bottom and rises as the reader advances.
- **`font_scale`** — multiplies the slide's text size (default `1.0`).

## Multi-line content

Markdown and HTML element bodies with internal structure read best
split across source lines using JSON5 string-continuation, rather than
crammed into one long string. See
[Working with assets](assets.md) for how element content references
external files.

The authoritative, per-field schema for slides and every element type
lives in the [Element schemas](../reference/elements/index.md)
reference, generated from the installed scrolly version.
