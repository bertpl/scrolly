# Animation

scrolly animates by **scroll position**, not by time. As the reader
scrolls through a slide, each element's properties interpolate between
keyframes you place along the scroll range.

## Keyframes

An animatable property is given as a set of keyframes — pairs of
*(scroll position, value)* — and scrolly interpolates between them
piecewise-linearly. Between the first and last keyframe the value
moves; outside that span it holds.

The animatable properties are:

- `position` — where the element sits within the slide
- `anchor` — the reference point for position, scaling, and rotation
- `opacity` — fade in and out
- `scale` — grow and shrink
- `angle` — rotate
- `width` and `height` — resize each dimension independently

## Scroll-position units

Keyframe positions are expressed in the slide's
[`scroll_range`](slides.md#scroll-range) units. Keyframes outside
`[0, scroll_range]` are allowed; `scrolly build --strict` and
`scrolly validate --strict` warn about them so you can catch
accidental out-of-range values.

## Worked patterns

See [Recipes / How-to](../recipes.md) for concrete animation patterns
— parallax backgrounds, incremental build-ups, and filmstrips.
