# Recipes / How-to

Short, task-focused patterns for common authoring needs. Each builds on
the [Concepts](concepts/2d-canvas.md) and
[Authoring](authoring/deck-format.md) material.

## Parallax background

Give a slide depth by scrolling a background `image` slower than the
foreground: keyframe the image's `position` (and optionally `scale`)
across the slide's [`scroll_range`](concepts/slides.md#scroll-range) so
it drifts as the reader scrolls. See [Animation](concepts/animation.md)
for the keyframe model.

## Incremental build-up

Reveal a diagram step by step with an
[`image_sequence`](concepts/elements.md) in `incremental` compositing
mode: each frame adds to the composite rather than replacing it, so the
diagram accumulates as the reader scrolls.

## Filmstrip crossfade

Use an `image_sequence` in the default `blend` mode to crossfade
through a series of images — a compact way to show a process or a
before/after sweep driven entirely by scroll.

## Bottom-up content

For content that reads naturally from the bottom up (timelines,
call stacks), set [`reverse: true`](concepts/slides.md) on the slide so
the scrollbar thumb starts at the bottom and rises as the reader
advances.

!!! note
    More recipes will be added over time. For the full set of fields
    each pattern uses, see the
    [Element schemas](reference/elements/index.md) reference.
