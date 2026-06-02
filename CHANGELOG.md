# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `scrolly --help-for-ai-tools` prints the full CLI reference — commands, schemas, and error codes — as a single markdown document for AI agents.

### Changed

### Deprecated

### Removed

### Fixed

### Security

## 0.2.4 (2026-06-02)

### Added

- `scrolly schema element` shows the schema for each slide element type.

### Changed

- Lighter backdrop behind the help screen.
- **Breaking:** `scrolly schema <type>` is now `scrolly schema file <type>` (deck and slide schemas moved under a `file` subcommand).
## 0.2.3 (2026-05-31)

### Added

- Slide-group labels auto-pick a legible black or white color from the group background, with an optional `label_color` override.

### Fixed

- Slide-connector lines and their end dots now keep a constant on-screen size as the deck view zooms out, and carry a soft light outline so they stay legible against dark backgrounds.
- Stepping between snap positions no longer briefly jerks the animation backward before moving toward the target.
## 0.2.2 (2026-05-30)

### Added

- Mermaid builds no longer require network access.
- New `--offline` flag on `scrolly build` (and `SCROLLY_OFFLINE=1` env var) skips the mermaid CDN download for byte-reproducible builds.
- Help screen shows the mermaid version used in the build.
- Automation hook for capturing animations.

### Changed

- **Breaking:** `image_sequence` timing — the absolute `hold` field is replaced by `hold_fraction` (a fraction of `frame_distance`, default `0.2`). Frames snap to the frame grid, and `fade_in` / `fade_out` now bound the timeline exactly.

### Fixed

- Image-sequence slides now snap to each frame, not just the slide endpoints.
- Slides positioned at negative row or column indices now render with correct gaps.
- Bezier edge arrows no longer clip on decks whose top-left slide is not at the origin.
- Inline `<code>` and `<pre>` now visually match the size of surrounding body text in slide content.
- Mermaid diagrams now scale to fit their element box instead of overflowing.
## 0.2.1 (2026-05-24)

### Added

- Validation and parse errors now carry numbered codes (e.g. `[E202]`); look up cause / example / fix via `scrolly errors <code>`.
- `--json` flag on `scrolly validate` for machine-readable output.
- New `scrolly introspect slides|elements|assets` commands for inspecting a resolved deck.
- New `scrolly introspect snaps|timeline|snapshot` commands for inspecting scroll-driven element behavior.
- New `scrolly introspect dom` command for inspecting rendered per-element HTML and scoped CSS.
- New `scrolly schema --list-types` flag for scripting (bare type names, one per line).
## 0.2.0 (2026-05-24)

### Added

- `scroll_range` is optional everywhere now; omit it for content-driven height.
- `font_scale` is now available on every slide.

### Changed

- **Breaking:** the three slide types (`static`, `scrollimation`, `storyboard`) are unified into a single `slide` type with the `.slide.json` source suffix.

### Removed

- **Breaking:** the `.static.md`, `.scrollimation.json`, and `.storyboard.json` source formats. Convert each slide to `.slide.json` — markdown bodies become a `markdown` element, scrollimation contents move under the new top-level shape, and storyboard scenes become elements with explicit opacity keyframes.

### Fixed

- Builds are now byte-reproducible across runs.
- Slides containing an iframe are now selectable by clicking anywhere on them in deck view.
## 0.1.13 (2026-05-23)

### Changed

- Inlined assets and iframe HTML are now compressed together, shrinking HTML output for decks with shared or repeated assets.

### Fixed

- Help-screen statistics now show total vs deduplicated payload counts per type (including iframe HTML), alongside the bundle's compression state and bytes saved.
## 0.1.12 (2026-05-22)

### Added

- Help screen (`?` icon or `h` key) with About, keyboard shortcuts, and deck statistics (slide/edge/asset counts, file size).
- Inlined assets and iframe content are gzip-compressed when the compressed form is at least 10% smaller, decompressed client-side via `DecompressionStream`. Pass `--no-compress` to disable.
- Debug mode (`d` key) shows slide-grid boundaries and cell coordinates in deck view; 10% grid lines, snap-position values, and a live scroll-position readout in slide view.
## 0.1.11 (2026-05-21)

### Added

- New `iframe` element embeds a self-contained local HTML file in a sandboxed `<iframe srcdoc>` with its own scrollbar, isolated from slide CSS, optionally framed with a border and outer shadow.
## 0.1.10 (2026-05-20)

### Added

- Zoom-out control now defaults to a deck mini-map. Pass `--simplified-zoom-control` to `scrolly build` to keep the legacy icon.

### Fixed

- Deck view now centres on the actual slide cluster when the leftmost column or topmost row of the deck is not at zero, instead of including the empty leading columns/rows in its fit-and-centre computation.
## 0.1.9 (2026-05-19)

### Fixed

- Pressing `s` to toggle scroll snapping now brings the scrollbar and snap control back from their idle fade-out, instead of mutating snap state invisibly.
- Slide-group tabs in deck view now stay wider than their label text across all viewport sizes and resize sequences, instead of squeezing in around the text after a window resize.
## 0.1.8 (2026-05-15)

### Added

- `.avif` accepted as an image asset format alongside the existing `.png`, `.jpg`, `.svg`, `.gif`, and `.webp`. README now enumerates the supported set.
- `compositing` field on `image_sequence` elements selects one of three frame-compositing strategies: `blend` (default, current behaviour — symmetric crossfade), `overlay` (opaque-frame mode that keeps a fully-opaque underlayer through every transition, eliminating mid-transition background bleed-through), or `incremental` (additive transparent layers that build up a composite as the sequence advances).
## 0.1.7 (2026-05-11)

### Added

- `reverse: true` flag on scrollimation slides — thumb starts at the bottom and rises as scroll advances, for naturally bottom-up content.
- Empty `image_sequence` slots — `""` reserves a slot in the timeline that renders blank, with neighbouring frames fading out before and in after it.
- Edge arrows and zoom-out control now auto-fade after 2 seconds of mouse inactivity, independent of the scrollbar fade.
## 0.1.6 (2026-05-11)

### Changed

- Smaller solid-black snap-position dots and an opaque scrollbar track for clearer visibility against any slide background.

### Fixed

- README CI badge now reads "CI" instead of the workflow file name.

## 0.1.5 (2026-05-10)

### Added

- New `image_sequence` element type: a scroll-driven filmstrip of images that crossfade as the user scrolls.
- `--strict` lint warns when an `image_sequence` timeline extends outside `[0, scroll_range]`.

## 0.1.4 (2026-05-07)

### Added

- Slide groups can have a custom `color` (`#RGB` or `#RRGGBB`), shown on the group tab in deck view.

### Changed

- Scrollbar and snap control auto-hide after 1 second of inactivity.

### Fixed

- Bezier edge curves are no longer clipped for slides on the bottom row or far-right column.
- Improved rendering performance in slide view by hiding off-screen slides.
- Improved rendering performance in scrollimation slides by hiding zero-opacity elements.
- Fixed rendering artefacts on animated elements during scroll.

## 0.1.3 (2026-05-06)

### Added

- Element properties (`position`, `anchor`, `opacity`, `scale`, `angle`, `width`, `height`) are now animatable via inline keyframes.
- Keyframe positions outside `[0, scroll_range]` are now allowed; `--strict` lint warns on them.
- `--strict` flag on `build` and `validate` enables optional lint checks.

### Changed

- `size: [w, h]` replaced by separate `width` and `height` fields (independently animatable).
- `rotate` renamed to `angle`.
- `translate` removed — use animated `position` instead.
- Scrollimation JSON simplified: elements are flat objects, no `element`/`initial`/`keyframes` wrapper.

### Fixed

- Scroll thumb now shrinks correctly on slides with many snap positions.

## 0.1.2 (2026-05-05)

### Added

- Animatable `anchor` via keyframes for viewport-independent panning over oversized elements.

## 0.1.1 (2026-05-05)

### Added

- `anchor` field on elements (replaces `transform_origin`); controls position reference and rotation/scale pivot.
- Field descriptions on all IR model fields for schema discoverability.
- `text_align` field on `MarkdownElement` (`"left"` | `"center"` | `"right"`).

### Fixed

- Scroll thumb sizing now caps at 2/3 of average snap spacing with a 10px floor.
- Image elements with one `"auto"` size dimension now render correctly.
- Fixed CSS collisions when multiple elements in a slide have no name.

## 0.1.0 (2026-05-04)

### Added

- Initial release.
- CLI with `build`, `validate`, `schema`, and `init` commands.
- Three slide types: static (Markdown), scrollimation (JSON), storyboard (JSON).
- Storyboard-to-scrollimation compiler.
- 2D-canvas HTML output with keyboard/scroll navigation, bezier transitions, slide groups, and fan layout for edge arrows.
- Worked example deck under `examples/worked-example/`.
- CI via GitHub Actions (Python 3.11–3.14, ubuntu + macOS).
- PyPI publishing via trusted publishing (OIDC).
