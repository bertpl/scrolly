# scrolly

Compile a JSON5 deck into a self-contained, scrollable 2D-canvas HTML presentation.

[![CI](https://github.com/bertpl/scrolly/actions/workflows/push_to_main.yml/badge.svg)](https://github.com/bertpl/scrolly/actions/workflows/push_to_main.yml)
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
scrolly build examples/worked-example/deck.deck.json --out /tmp/scrolly-out --force
open /tmp/scrolly-out/index.html
```

See [`examples/worked-example/`](examples/worked-example/) for a reference deck
demonstrating all supported slide types.

## License

[MIT](https://github.com/bertpl/scrolly/blob/main/LICENSE).
