# Elements

A slide's content is a stack of **elements**, each positioned within
the slide and individually animatable. scrolly ships a small set of
element types covering text, images, embedded HTML, and scroll-driven
sequences.

## Element types

- **`markdown`** — a block of Markdown, rendered to HTML. The everyday
  text element.
- **`image`** — a single image asset (see
  [supported formats](../authoring/assets.md)).
- **`image_sequence`** — a scroll-driven filmstrip of images that
  crossfade as the reader scrolls, with `blend`, `overlay`, and
  `incremental` compositing modes.
- **`html`** — raw HTML inserted verbatim, for content the other
  elements don't cover.
- **`iframe`** — a self-contained HTML document embedded in a sandboxed
  `<iframe srcdoc>`, fully isolated from the slide's styles.
- **`mermaid`** — a [Mermaid](https://mermaid.js.org/) diagram rendered
  at build time.
- **`container`** — a positioned box holding child elements, for
  grouping and animating them as one unit. See
  [Containers](#containers) below.

## Containers

A `container` holds a child-element array; the children express
`position` / `width` / `height` as percentages of **the container's
box**, not the slide. The container itself carries the full animatable
substrate, and its animation composes onto the children: animate the
container's `position` or `opacity` and the whole group moves or fades
as one; its `anchor` is the pivot for `scale` / `angle`.

The box defaults to the full slide (`position [0, 0]`, `width 100`,
`height 100`), so wrapping existing elements changes nothing visually —
child coordinates are numerically identical to slide coordinates. Give
the container an explicit box and the children re-coordinate into it,
which makes a child block position-independent: the same partial can be
placed at several boxes, or kept in its own file and included with
`container_file: "path/to/children.json"` (a JSON5 array of elements,
paths resolved relative to that file).

Containers nest, and occupy a single z-slot in their parent: children
stack within the container in array order. Container `width` / `height`
must be numeric (or animated) — `"auto"` is rejected, since absolutely
positioned children give an auto box nothing to size against. When a
container has a `name`, its children's names are dot-prefixed
(`header.title`), so one partial can be instantiated twice on a slide
without duplicate-name errors.

## Placement

Every element has a `position` and `anchor` within the slide, plus a
size. Any of these can be a fixed value or an animated one — see
[Animation](animation.md).

The exact field list for each element type is in the
[Element schemas](../reference/elements/index.md) reference, generated
from the installed scrolly version so it never drifts from the code.
