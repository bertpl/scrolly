# Working with assets

Slides reference external files — images, embedded HTML — that scrolly
resolves at build time and inlines into the single-file output.

## Supported image formats

Image assets may use any of these formats:

`.png` · `.jpg` / `.jpeg` · `.svg` · `.gif` · `.webp` · `.avif`

## Asset resolution

Assets are referenced by path relative to the deck source. At build
time scrolly resolves, deduplicates, and inlines them, so repeated use
of the same asset costs space only once. The result is still a single
self-contained file — see
[Output & bundling](../concepts/output-and-bundling.md).

## Embedded HTML

The [`iframe`](../concepts/elements.md) element embeds a self-contained
HTML document in a sandboxed `<iframe srcdoc>`, isolated from the
slide's own styles. Because the embedded document has no external base
URL, it must be self-contained: inline its CSS and JavaScript, and
reference images as `data:` URIs.

## Diagrams and offline builds

The [`mermaid`](../concepts/elements.md) element renders diagrams at
build time. Builds are reproducible and can run fully offline; see the
`--offline` flag in the [CLI reference](../reference/cli.md).
