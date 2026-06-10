# Slides

A slide is a single cell on the [2D canvas](2d-canvas.md). It carries a
title, a position, and a stack of positioned [elements](elements.md),
plus a few properties that control how it scrolls.

## Anatomy

Each slide is authored as a `.slide.json` file (JSON5 on the `.json`
extension). At minimum it has a `title` and a list of elements; its
grid `position` is set from the deck manifest. See
[Slide format](../authoring/slide-format.md) for the full field list.

## Scroll range

A slide's `scroll_range` is how far the reader scrolls from top to
bottom. It can be a fixed number, or `"auto"` (the default) for
content-driven height — the slide is exactly as tall as its content
needs. An explicit `0` pins the slide static: it never scrolls, even
when its content is taller than the viewport. Animation keyframes are
expressed in scroll-position units within this range.

## Snap positions

`snap_positions` are scroll offsets the view eases to as the reader
scrolls, so a slide can rest on meaningful moments rather than
anywhere. Readers can toggle snapping on or off while viewing — see
[Navigation & shortcuts](../viewing-decks/navigation.md).

## Other controls

- **`font_scale`** multiplies the slide's text size, for tuning
  density independently per slide.
- **`reverse`** flips the scroll direction so the thumb starts at the
  bottom and rises as the reader advances — natural for bottom-up
  content.
