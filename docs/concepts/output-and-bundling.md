# Output & bundling

A default `scrolly build` produces a **single self-contained
`index.html`** with no external resource loads. This page explains what
that means and the knobs that affect it.

## The single-file guarantee

Every referenced asset — images, embedded HTML, the runtime — is
inlined into the output file. The result opens by double-clicking,
works offline, and can be hosted anywhere or sent as one attachment.

## Compression

Inlined assets are compressed and decompressed in the browser at load
time, so the single-file convenience doesn't bloat the download. The
help screen's statistics panel reports payload sizes and how much
compression saved — see [Help screen](../viewing-decks/help-screen.md).
Pass `--no-compress` to disable compression.

## Offline and reproducible builds

Builds are byte-reproducible across runs. Diagrams that would normally
fetch a rendering library are handled without network access; pass
`--offline` (or set `SCROLLY_OFFLINE=1`) to guarantee a build performs
no downloads.

The exact set of build flags is in the [CLI reference](../reference/cli.md).
