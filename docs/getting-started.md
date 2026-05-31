# Getting started

This walkthrough takes you from an empty directory to an open
presentation in a few minutes.

## Install

```bash
pip install scrolly
```

Or, to install it as a standalone tool with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install scrolly
```

Verify the install:

```bash
scrolly --help
```

## Scaffold a deck

`scrolly init` writes a minimal starter deck you can build immediately:

```bash
scrolly init my-deck
```

Run `scrolly init --help` for the available options. The result is a
`.deck.json` manifest plus one `.slide.json` per slide — see
[Deck format](authoring/deck-format.md) and
[Slide format](authoring/slide-format.md) for what's inside.

## Build

```bash
scrolly build my-deck/deck.deck.json --out site --force
```

This compiles the deck into a single self-contained `site/index.html`.
The `--force` flag overwrites an existing output directory.

## Open

```bash
open site/index.html
```

The file has no external dependencies, so it works offline and can be
moved or hosted anywhere. To learn how to move around it, see
[Navigation & shortcuts](viewing-decks/navigation.md).

## Validate as you go

```bash
scrolly validate my-deck/deck.deck.json
```

`validate` reports any problems with numbered error codes; look up a
code's cause and fix with `scrolly errors <code>`. Add `--strict` to
also surface optional lint warnings.
