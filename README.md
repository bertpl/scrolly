# scrolly

Compile a JSON5 deck into a self-contained, scrollable 2D-canvas HTML presentation.

*Liked by humans; understood by agents.*

[![scrolly — scroll-driven 2D-canvas presentations](https://raw.githubusercontent.com/bertpl/scrolly/main/docs/assets/hero-v3.webp)](https://github.com/bertpl/scrolly)

[![CI](https://img.shields.io/github/actions/workflow/status/bertpl/scrolly/push_to_main.yml?branch=main&label=CI)](https://github.com/bertpl/scrolly/actions/workflows/push_to_main.yml)
[![PyPI](https://img.shields.io/pypi/v/scrolly.svg)](https://pypi.org/project/scrolly/)
[![Python](https://img.shields.io/pypi/pyversions/scrolly.svg)](https://pypi.org/project/scrolly/)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/bertpl/scrolly/blob/main/LICENSE)

## Installation

```bash
pip install scrolly
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install scrolly
```

## Quickstart

```bash
scrolly build examples/stacked-diffs/deck.deck.json --out /tmp/scrolly-out --force
open /tmp/scrolly-out/index.html
```

See [`examples/stacked-diffs/`](examples/stacked-diffs/) for a complete example deck.

## Source format

A deck is a `.deck.json` manifest plus one `.slide.json` per slide.
Both files are parsed as **JSON5** but kept on the `.json` extension —
a deliberate agent-first choice so common tooling that defaults to
`*.json` continues to work; the JSON5 superset is what authors and
agents actually write.

## Supported image formats

Image assets referenced from slides may use any of the following formats:
`.png`, `.jpg` / `.jpeg`, `.svg`, `.gif`, `.webp`, `.avif`.

## License

[MIT](https://github.com/bertpl/scrolly/blob/main/LICENSE).
