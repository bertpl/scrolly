"""Build the compressed bootstrap page wrapping a fully-assembled inner document.

The compressed output inverts the page structure: instead of a full
document carrying a compressed asset bundle, the file on disk is a
minimal black bootstrap document (title + og meta tags for link
unfurlers, a noscript notice, one base64 blob, and the loader script)
and everything else — slide DOM, CSS, deck config, runtime JS, mermaid,
asset payloads — lives inside the blob: a single gzip stream of the
inner HTML document followed by the raw asset payload bytes.

The loader (``assets/loader.js``) inflates the blob client-side,
stashes the asset remainder on ``window`` for canvas.js, and replaces
the document via ``document.write``.
"""

from __future__ import annotations

import base64
import gzip
from html import escape as html_escape

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from scrolly.render.bundled_assets import bundled_loader_js

GZIP_LEVEL = 9

# Both placeholders are emitted into the inner document's help-screen
# meta JSON by the assembler (in deferred-stats mode) and resolved here:
# their values depend on the size of the compressed page they live in,
# so a first compression pass measures, then a second pass ships the
# substituted document. The few bytes the substitution shifts the final
# size by are accepted — the same placeholder-before-measure
# approximation the assembler has always used for ``file_size``.
FILE_SIZE_PLACEHOLDER = '"__FILE_SIZE_PLACEHOLDER__"'
BYTES_SAVED_PLACEHOLDER = '"__BYTES_SAVED_PLACEHOLDER__"'


def build_compressed_page(
    inner_html: str,
    asset_stream: bytes,
    *,
    title: str,
    slide_count: int,
    plain_size: int,
    minify: bool = True,
) -> str:
    """Wrap an assembled inner document and its asset bytes into a bootstrap page.

    Args:
        inner_html: The fully-assembled inner document, still carrying
            the deferred-stats placeholders (see module constants).
        asset_stream: Concatenated raw payload bytes, appended to the
            inner document in the single gzip stream
            (``PayloadBundler.manifest_and_stream``'s second element).
        title: Deck title for the bootstrap ``<title>`` / ``og:title``.
        slide_count: Number of slides, used in the og description.
        plain_size: Byte size of the equivalent uncompressed build,
            baked into the help screen's space-saved figure.
        minify: Ship the loader JS minified (comments stripped).

    Returns:
        The bootstrap page HTML.
    """
    loader_js = bundled_loader_js(minify=minify)

    first_pass = _render_bootstrap(inner_html, asset_stream, title=title, slide_count=slide_count, loader_js=loader_js)
    file_size = len(first_pass.encode("utf-8"))

    final_inner = inner_html.replace(FILE_SIZE_PLACEHOLDER, str(file_size)).replace(
        BYTES_SAVED_PLACEHOLDER, str(max(0, plain_size - file_size))
    )
    return _render_bootstrap(final_inner, asset_stream, title=title, slide_count=slide_count, loader_js=loader_js)


def _render_bootstrap(
    inner_html: str,
    asset_stream: bytes,
    *,
    title: str,
    slide_count: int,
    loader_js: str,
) -> str:
    """Compress document + assets into one stream and render the bootstrap template."""
    doc_bytes = inner_html.encode("utf-8")
    blob = base64.b64encode(gzip.compress(doc_bytes + asset_stream, GZIP_LEVEL, mtime=0)).decode("ascii")

    template = _env().get_template("bootstrap.html.j2")
    return template.render(
        # The Jinja env runs with autoescape off (matching the assembler),
        # so attribute-bound strings are escaped here.
        title=html_escape(title),
        og_description=html_escape(f"Interactive presentation — {slide_count} slides."),
        doc_length=len(doc_bytes),
        blob=blob,
        loader_js=loader_js,
    )


def _env() -> Environment:
    """Build the Jinja environment for the bootstrap template (no autoescape, strict undefined)."""
    return Environment(
        loader=PackageLoader("scrolly.render", "templates"),
        autoescape=select_autoescape(default=False),
        undefined=StrictUndefined,
    )
