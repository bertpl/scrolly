"""Write the assembled HTML and bundled static assets to an output directory."""

from __future__ import annotations

from pathlib import Path

from scrolly.errors import OutputError
from scrolly.render import MermaidAsset, iter_assets


def write_output(
    out_dir: Path,
    html: str,
    *,
    force: bool = False,
    mermaid: MermaidAsset | None = None,
    inline: bool = True,
) -> None:
    """Write `html` as `out_dir/index.html` and optionally copy bundled assets.

    Args:
        out_dir: Destination directory.
        html: Assembled page HTML.
        force: Allow overwriting a non-empty `out_dir`.
        mermaid: Resolved mermaid asset (passed through from
            :func:`build_deck`). When ``inline=False`` and ``mermaid``
            is non-None, the mermaid JS file is written alongside the
            other bundled assets.
        inline: When ``True``, only ``index.html`` is written (CSS, JS,
            and mermaid are embedded in the HTML).

    Raises:
        OutputError: ``out_dir`` exists but is not a directory, or is
            non-empty without ``force=True``.
    """
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

    (out_dir / "index.html").write_text(html)
    if not inline:
        for name, content in iter_assets():
            (out_dir / name).write_bytes(content)
        if mermaid is not None:
            (out_dir / mermaid.name).write_bytes(mermaid.content)
