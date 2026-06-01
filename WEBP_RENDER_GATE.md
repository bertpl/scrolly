# WebP render gate — THROWAWAY, do not merge

**Purpose:** confirm GitHub (and PyPI by proxy) actually render an *animated*
WebP before the hero swaps from GIF to WebP on the README / PyPI surfaces.

This is the approved hero encode: lossy, quality 80, method 4, 1282×725 (4.89 MB
— vs the 8.83 MB GIF currently shipping).

## 1. Absolute raw URL (exactly how the README + PyPI embed images)

![hero via absolute raw URL](https://raw.githubusercontent.com/bertpl/scrolly/chore/0-2-4-webp-render-gate/docs/assets/hero-v3.webp)

## 2. Relative path (how the docs site embeds it)

![hero via relative path](docs/assets/hero-v3.webp)

## Pass criteria

Both images above must **render and animate**. If they do, the gate passes and
the hero can move to WebP. Then: close this PR unmerged, delete the branch, and
ship the WebP through the real hero-adoption change.
