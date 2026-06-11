"""Write the assembled HTML and bundled static assets to an output directory."""

from __future__ import annotations

from pathlib import Path

from scrolly.errors import OutputError
from scrolly.render import MermaidAsset, iter_assets


def validate_out_file(out_file: str) -> None:
    """Validate a user-supplied output file name.

    Args:
        out_file: The HTML output file name, relative to the output
            directory.

    Raises:
        OutputError: ``out_file`` contains a path separator or does not
            end in ``.html``.
    """
    if "/" in out_file or "\\" in out_file:
        raise OutputError(
            code="E703",
            message=f"output file name must not contain path separators: {out_file}",
        )
    if not out_file.endswith(".html") or out_file == ".html":
        raise OutputError(
            code="E703",
            message=f"output file name must end in .html: {out_file}",
        )


def write_output(
    out_dir: Path,
    html: str,
    *,
    force: bool = False,
    mermaid: MermaidAsset | None = None,
    inline: bool = True,
    out_file: str = "index.html",
    minify: bool = True,
) -> None:
    """Write `html` as `out_dir/<out_file>` and optionally copy bundled assets.

    Args:
        out_dir: Destination directory.
        html: Assembled page HTML.
        force: Allow overwriting a non-empty `out_dir`.
        mermaid: Resolved mermaid asset (passed through from
            :func:`build_deck`). When ``inline=False`` and ``mermaid``
            is non-None, the mermaid JS file is written alongside the
            other bundled assets.
        inline: When ``True``, only the HTML file is written (CSS, JS,
            and mermaid are embedded in the HTML).
        out_file: Name of the HTML file inside ``out_dir``.
        minify: Write the standalone canvas JS and CSS minified (only
            meaningful when ``inline=False``).

    Raises:
        OutputError: ``out_dir`` exists but is not a directory, is
            non-empty without ``force=True``, or ``out_file`` is not a
            valid file name.
    """
    validate_out_file(out_file)
    if out_dir.exists():
        if not out_dir.is_dir():
            raise OutputError(code="E701", message=f"output path is not a directory: {out_dir}")
        if any(out_dir.iterdir()) and not force:
            raise OutputError(
                code="E702",
                message=f"output directory is not empty: {out_dir}. Pass --force to overwrite.",
            )
    else:
        out_dir.mkdir(parents=True)

    (out_dir / out_file).write_text(html)
    if not inline:
        for name, content in iter_assets(minify=minify):
            (out_dir / name).write_bytes(content)
        if mermaid is not None:
            (out_dir / mermaid.name).write_bytes(mermaid.content)
