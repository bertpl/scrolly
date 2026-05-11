# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

- Refined snap-position styling in the scrollbar gutter: smaller solid-black
  dots and an opaque track, keeping the dots clearly visible against any
  slide background.

### Deprecated

### Removed

### Fixed

- README CI badge now reads "CI" instead of taking its label from the
  underlying workflow file name.

### Security

## 0.1.5 (2026-05-10)

### Added

- New `image_sequence` element type for scroll-driven filmstrips: an ordered list of images
  that crossfade as the user scrolls. Configurable `frame_distance` (slot width), `hold`
  (full-opacity span per frame), `scroll_offset`, and `fade_in` / `fade_out` (leading /
  trailing ramp distances). Repeating a path consecutively in the list extends its visible
  duration by one slot per repeat.
- `--strict` lint check warns when an `image_sequence` timeline extends below `0` (via
  `fade_in`) or past `scroll_range` (via `fade_out`).
## 0.1.4 (2026-05-07)

### Added

- Slide groups can now have a custom `color` (`#RGB` or `#RRGGBB`), shown as a solid fill
  on the group tab background in deck view.

### Changed

- Scrollbar and snap control auto-hide after 1 second of inactivity (0.5s fade-out,
  instant fade-in on interaction).

### Fixed

- Bezier edge curves in deck view were clipped for slides on the bottom row or far-right
  column when group-label gaps pushed coordinates outside the SVG viewBox.
- Improved rendering performance in slide view by hiding off-screen slides, reducing GPU
  compositor layers.
- Improved rendering performance in scrollimation slides by hiding elements at zero opacity,
  reducing GPU compositor layers during scroll.
- Improved rendering quality for animated elements by promoting them to dedicated GPU
  layers, avoiding invalidation rectangle rounding artefacts.
## 0.1.3 (2026-05-06)

### Added

- Element properties (`position`, `anchor`, `opacity`, `scale`, `angle`, `width`, `height`)
  can now be either static values or keyframe animations directly on the element.
- Keyframe positions beyond `[0, scroll_range]` are now allowed (useful for partial
  transitions). Use `--strict` to warn on out-of-range values.
- `--strict` flag on `build` and `validate` commands enables optional lint checks.

### Changed

- `size: [w, h]` replaced by separate `width` and `height` fields (independently animatable).
- `rotate` renamed to `angle`.
- `translate` removed — use animated `position` instead.
- Scrollimation JSON format simplified: elements are flat objects, no `element`/`initial`/`keyframes` wrapper.

### Fixed

- Scroll thumb now shrinks correctly on slides with many snap positions.
## 0.1.2 (2026-05-05)

### Added

- Animatable `anchor` via keyframes for viewport-independent panning over oversized
  elements.

## 0.1.1 (2026-05-05)

### Added

- `anchor` field on elements (replaces `transform_origin`). Controls position reference
  point and rotation/scale pivot.
- Field descriptions on all IR model fields for schema discoverability.
- `text_align` field on `MarkdownElement` (`"left"` | `"center"` | `"right"`).

### Fixed

- Scroll thumb sizing now caps at 2/3 of average snap spacing with a 10px floor.
- Image elements with one `"auto"` size dimension now render correctly.
- Element CSS targeting uses index-based identifiers, fixing collisions when multiple
  elements had no name.

## 0.1.0 (2026-05-04)

### Added

- Initial release.
- CLI with `build`, `validate`, `schema`, and `init` commands.
- Three slide types: static (Markdown), scrollimation (JSON), storyboard (JSON).
- Storyboard-to-scrollimation compiler.
- 2D-canvas HTML output with keyboard/scroll navigation, bezier transitions,
  slide groups, and fan layout for edge arrows.
- Worked example deck under `examples/worked-example/`.
- CI via GitHub Actions (Python 3.11–3.14, ubuntu + macOS).
- PyPI publishing via trusted publishing (OIDC).
