# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `reverse: true` flag on scrollimation slides — thumb starts at the bottom and rises as scroll advances, for naturally bottom-up content.

### Changed

### Deprecated

### Removed

### Fixed

### Security

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
