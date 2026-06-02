# scrolly

Compile a JSON5 deck into a single, self-contained, scrollable 2D-canvas HTML presentation.

*Liked by humans; understood by agents.*

[![scrolly — scroll-driven 2D-canvas presentations](https://raw.githubusercontent.com/bertpl/scrolly/main/docs/assets/hero-v4.webp)](https://scrolly.readthedocs.io/en/stable/)

[![CI](https://img.shields.io/github/actions/workflow/status/bertpl/scrolly/push_to_main.yml?branch=main&label=CI)](https://github.com/bertpl/scrolly/actions/workflows/push_to_main.yml)
[![PyPI](https://img.shields.io/pypi/v/scrolly.svg)](https://pypi.org/project/scrolly/)
[![Python](https://img.shields.io/pypi/pyversions/scrolly.svg)](https://pypi.org/project/scrolly/)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/bertpl/scrolly/blob/main/LICENSE)

## Why it's different

- **A 2D canvas you fly around**, not a linear reel. Slides sit on an
  integer grid connected by edges; readers zoom out to a deck map and
  zoom into any slide to scroll through it.
- **Scroll-driven keyframe animation.** Element properties (position,
  size, opacity, scale, angle) interpolate as the reader scrolls — no
  timeline, no autoplay.
- **One self-contained HTML file.** A default build inlines every
  asset into a single `index.html` with zero external loads — open it
  by double-clicking, host it anywhere, email it.
- **Agent-friendly.** The CLI exposes full help, input schemas, deck
  introspection, and numbered error codes, so agentic coding tools
  immediately understand how to author and debug scrolly decks.

## Installation

```bash
pip install scrolly        # or: uv tool install scrolly
```

## Quickstart

```bash
scrolly init my-deck                                    # scaffold a starter deck
scrolly build my-deck/deck.deck.json --out out --force  # compile to one HTML file
open out/index.html                                     # double-click anywhere
```

A deck is a `.deck.json` manifest plus one `.slide.json` per slide (both
parsed as JSON5):

```json5
// deck.deck.json
{
  title: "My Deck",
  slides: [
    { id: "intro", position: [0, 0], source: "slides/intro.slide.json" },
  ],
  edges: [],
}
```

```json5
// slides/intro.slide.json
{
  title: "My Deck",
  elements: [
    { markdown: "# My Deck\n\nWelcome to your new presentation." },
  ],
}
```

## Elements

Slides hold elements of six types — `markdown`, `image`, `image_sequence`,
`mermaid`, `html`, and `iframe` — each animatable via scroll-driven
keyframes. See the [element reference](https://scrolly.readthedocs.io/en/stable/reference/elements/)
for fields and examples.

## Learn more

- **[Documentation](https://scrolly.readthedocs.io/en/stable/)** — guided
  walkthrough, concepts, authoring, and the full reference, with a live
  interactive deck right on the homepage.
- **[Examples](examples/)** — including the
  [stacked-diffs](examples/stacked-diffs/) hero deck.
- **[Changelog](CHANGELOG.md)**.

## License

[MIT](https://github.com/bertpl/scrolly/blob/main/LICENSE).
