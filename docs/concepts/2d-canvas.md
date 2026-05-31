# The 2D canvas

scrolly's defining idea is spatial: a deck is not a linear sequence of
slides but a set of slides placed on a **2D integer grid**. This page
covers the spatial authoring model — how slides, their coordinates,
groups, and edges fit together.

## Grid coordinates

Every slide has a `position: [col, row]` placing it on the grid.
Coordinates can be negative and need not start at the origin — scrolly
fits and centers the occupied region either way. A plus-shaped deck,
for example, places slides above, below, left, and right of a center
slide:

```
              [ intro ]  (0, -1)
                  |
[ left ] (-1,0)—[ main ]—[ right ] (1, 0)
                (0, 0)
                  |
             [ detail ]  (0, 1)
```

## Edges

Slides are connected by **edges** — directional links drawn between
grid neighbors that tell the reader where they can go next. Edges
render as connector lines in the deck map and as navigation arrows when
zoomed into a slide.

## Groups

Slides can be collected into **groups** that share a background color
and a labeled tab in the deck map. A group's label color is chosen
automatically for legibility against its background, or set explicitly
— see [Deck format](../authoring/deck-format.md).

## Two views

The rendered deck has two zoom levels, covered in
[Deck view & mini-map](../viewing-decks/deck-view-and-mini-map.md):

- the **deck map** — zoomed out, showing all slides, edges, and group
  tabs at once; and
- the **slide view** — zoomed into a single slide, which the reader
  scrolls through.
