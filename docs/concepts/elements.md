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

## Placement

Every element has a `position` and `anchor` within the slide, plus a
size. Any of these can be a fixed value or an animated one — see
[Animation](animation.md).

The exact field list for each element type is in the
[Element schemas](../reference/element-schemas.md) reference, generated
from the installed scrolly version so it never drifts from the code.
