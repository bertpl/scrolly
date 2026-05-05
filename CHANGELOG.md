# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## 0.1.2 (2026-05-05)

### Added

- Animatable `anchor` via keyframes. Enables viewport-independent panning over
  oversized elements (e.g. scrolling through a tall image). Mutually exclusive
  with the element-level `anchor` field — set in one place only.
## 0.1.1 (2026-05-05)

### Added

- `anchor` field on `SlideElement` (replaces `transform_origin`). Controls both the
  position reference point and the rotation/scale pivot. Default `[0, 0]` (top-left)
  preserves current positioning behavior.
- Field descriptions on all IR model fields. `scrolly schema <type>` now includes
  semantic information (units, coordinate system, validation rules) for every field.
- `text_align` field on `MarkdownElement` (`"left"` | `"center"` | `"right"`,
  default `"left"`). Enables horizontal text alignment within the element box.

### Fixed

- Scroll thumb sizing: increased default to 60px, capped at 2/3 of average snap spacing
  when many snap positions exist, with a 10px floor.
- Image elements with one `"auto"` size dimension now render correctly. The `img` CSS
  rule is always emitted (`width: 100%; height: 100%; display: block`), with `object-fit`
  included only when set.
- Element `id` field renamed to `name` (optional, for error messages only). CSS targeting
  now uses deterministic index-based identifiers, fixing a bug where multiple elements
  without an `id` all received `data-element-id="None"` causing CSS rules to collide.
## 0.1.0 (2026-05-04)

### Added

- Initial open-source release of scrolly (previously named slider).
- CLI with `build`, `validate`, `schema`, and `init` commands.
- Three slide types: static (Markdown), scrollimation (JSON), storyboard (JSON).
- Storyboard-to-scrollimation compiler.
- 2D-canvas HTML output with keyboard/scroll navigation, bezier transitions,
  slide groups with tab-shaped backgrounds, and fan layout for edge arrows.
- Worked example deck under `examples/worked-example/`.
- CI via GitHub Actions (Python 3.11–3.14, ubuntu + macOS).
- PyPI publishing via trusted publishing (OIDC).
