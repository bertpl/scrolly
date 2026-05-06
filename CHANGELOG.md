# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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

### Deprecated

### Removed

### Fixed

- Scroll thumb now shrinks correctly on slides with many snap positions.

### Security

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
