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

## Content from files

Text-content element fields have a `*_file` twin that reads the
content from an external file at build time:

| Inline field | File form |
|---|---|
| `markdown` | `markdown_file` |
| `html` | `html_file` |
| `mermaid` | `mermaid_file` |
| `iframe_html` | `iframe_html_file` |

```json5
// instead of a long inline string …
{ markdown_file: "../postscript.md", position: [10, 5], width: 80 }
```

The file's text is inlined at parse time, so the built output is
identical either way. Paths resolve relative to the slide source
file. Author exactly one form per element — specifying both the
inline field and its `*_file` form is an error. Use the file form to
keep long-form content out of slide sources and to edit it with
proper syntax highlighting (`.md`, `.html`, `.mmd`).

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
