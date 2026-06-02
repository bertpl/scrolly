# Deck format (`.deck.json`)

A deck is described by a single `.deck.json` manifest: the slides it
contains, where they sit on the grid, the edges between them, and any
groups. Like all scrolly sources it is authored as **JSON5** but kept
on the `.json` extension, so tooling that defaults to `*.json` keeps
working while you write the friendlier JSON5 superset.

## Slides and positions

The manifest lists each slide and its grid `position: [col, row]`.
Positions may be negative and need not start at the origin (see
[The 2D canvas](../concepts/2d-canvas.md)). Each entry points at a
`.slide.json` file described in [Slide format](slide-format.md).

## Edges

Edges connect grid-neighboring slides to show the reader where they can
navigate. Each edge names its endpoints; scrolly draws the connector in
the deck map and the corresponding navigation arrow in slide view.

## Groups

A group collects slides under a shared background color and a labeled
tab in the deck map. A group has a `label`, the `slide_ids` it
contains, and an optional `color`.

### Label coloring

By default a group's label color is derived automatically from its
background `color` for legibility — scrolly picks black or white by
whichever gives the higher contrast against the background. This means
that just setting a background gets you a readable label with no extra
work.

When the automatic black-or-white choice isn't what you want — for
example a tinted label that matches the group's hue — set `label_color`
explicitly to override it. Both `color` and `label_color` accept the
same hex forms (`#RGB` or `#RRGGBB`).

The complete manifest field list is in the
[Element schemas](../reference/elements/index.md) reference.
