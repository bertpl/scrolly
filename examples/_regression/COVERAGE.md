# Regression deck feature coverage

This deck deliberately exercises every shipped scrolly feature and corner
case, so it doubles as a regression contract: if a change drops one of the
demos below, coverage has regressed.

This file is the record of *what* is demonstrated and *where*. Two lookups:

- **Where is feature X demonstrated?** Find its row — the *Covered by*
  column lists the slides (and the specific element where it matters).
- **What does slide Y demonstrate?** Search this file for the slide id
  (e.g. `hidden-bytes`); every row that names it comes back.

Slide ids match the `slides/<id>.slide.json` filenames. A *single* entry in
a *Covered by* cell means that slide is the only demo of the feature — don't
break it. Update this file in the same change that adds or removes a demo.

Feature coverage is recorded here, not in slide comments — keep slide
comments to intent (*why* an animation looks the way it does).

## Element types

| Type | Covered by |
|---|---|
| `markdown` | most slides; richest syntax (headings, lists, links, code spans, a fenced code block, emphasis) on `reference`, a table on `affected` |
| `image` | `title` (glyph), `maint-bg` (jpg), `contributions` (timeline), `pressure` (png), `capability` (key), `affected` (logos) |
| `image_sequence` | `cast`, `blank-gap`, `hidden-bytes`, `investigation`, `build-trojan` |
| `html` | `title` (bg), `handover` (date callout), `anomaly` (terminal), `disclosure` (banner + progress bar) |
| `mermaid` (`mermaid_file`) | `ssh-hijack` |
| `iframe` (`iframe_html_file`) | `pressure` (thread), `lessons` (takeaways panel) |

## image_sequence compositing modes

| Mode | Covered by |
|---|---|
| `blend` | `blank-gap` |
| `overlay` | `cast`, `hidden-bytes`, `investigation` |
| `incremental` | `build-trojan` |

## Animatable element properties

| Property | Covered by |
|---|---|
| `position` (vec2 keyframes) | `contributions` (timeline pan), `handover` (date callout slide-in) |
| `anchor` (vec2 keyframes) | `contributions`, `ssh-hijack` — oversized-element panning |
| `opacity` (scalar keyframes) | `title`, `maint-bg`, `contributions`, `pressure`, `handover`, `capability`, `anomaly`, `disclosure` |
| `scale` (scalar keyframes) | `title` (glyph), `capability` (key), `disclosure` (banner) |
| `angle` (scalar keyframes) | `capability` (key) |
| `width` (size-dim keyframes) | `disclosure` (progress bar) |
| `height` (size-dim keyframes) | `disclosure` (progress bar) |
| `text_align` on `markdown` (static) | `title`, `cast`, `handover`, `blank-gap`, `hidden-bytes`, `build-trojan`, `capability`, `lessons` |

## Slide-level features

| Feature | Covered by |
|---|---|
| `scroll_range: "auto"` (content-driven height) | `reference`, `lessons`, `affected` |
| `scroll_range: <int>` (fixed) | most slides |
| `scroll_speed` ≠ 1.0 | `handover` (0.6), `capability` (0.7) |
| `reverse: true` | `disclosure` |
| author-supplied `snap_positions` | most slides |
| element-derived snaps (image_sequence hold-centers) | `cast`, `blank-gap`, `hidden-bytes`, `investigation` |
| `font_scale` ≠ 1.0 | `title` (1.4), `anomaly` (1.1) |
| dense snaps (thumb-sizing) | `contributions` (23, Δ100 grid) |

## Deck / canvas features

| Feature | Covered by |
|---|---|
| slide groups with `color` | Setup, Infiltration, Backdoor, Discovery (4 groups, varied hues) |
| group label auto-contrast — light bg → black | Setup, Infiltration |
| group label auto-contrast — dark bg → white | Backdoor (`#8B2F2F`) |
| group `label_color` override | Discovery (`#1B5E20` on light bg) |
| off-grid / negative origin | deck origin `(-1, -2)`; `affected` `(4, -2)`, `lessons` `(1, 3)`, `reference` `(4, 3)` |
| long bezier to an off-grid slide | `disclosure`→`affected`, `disclosure`→`lessons`, `lessons`→`reference` |
| non-adjacent curved beziers | `disclosure`→`affected`, `disclosure`→`reference` |
| edge endpoints (`slide\|side`) | throughout the edge list (e.g. `cast\|right`, `disclosure\|bottom`) |
| edge fan layout (≥2 edges at one side) | `disclosure\|right` (→`affected`, →`reference`); `reference\|left` (←`lessons`, ←`disclosure`) |

## Asset formats

| Format | Covered by |
|---|---|
| SVG | `title`, `cast`, `contributions`, `hidden-bytes`, `capability`, `investigation`, `build-trojan` |
| PNG | `pressure` |
| JPG | `maint-bg` |
| WebP | `affected` |
| AVIF | `blank-gap` |
| mermaid (`.mmd`) | `ssh-hijack` |
| HTML (`.html` via `iframe`) | `pressure`, `lessons` |

## Edge cases

| Case | Covered by |
|---|---|
| blank `""` slot in `image_sequence` | `blank-gap` |
| frame deduplication (same file reused) | `hidden-bytes` (`hidden-clean.svg` ×2) |
| oversized element panned via `anchor` | `contributions` (tall SVG), `ssh-hijack` (tall mermaid) |
| mermaid box hugs the diagram — pan edges land flush at scroll start/end, no stray whitespace or overflow | `ssh-hijack` |
| iframe `border_width` + `border_color` | `pressure`, `lessons` |
| iframe `shadow_size` + `shadow_color` | `pressure`, `lessons` |
| iframe internal scrollbar | `pressure`, `lessons` |
| multi-element layering / z-order | `title` (4 stacked layers) |
| full-bleed background | `title`, `maint-bg` |
| `object_fit: "cover"` | `maint-bg` |
| one `"auto"` size dimension | `title` (and most image elements); `ssh-hijack` (mermaid) |

## Gaps / partial coverage

- **`object_fit: "contain"`:** not set explicitly anywhere; only `"cover"`
  is exercised (`maint-bg`).
