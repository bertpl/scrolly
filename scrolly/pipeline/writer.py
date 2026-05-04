"""Write the assembled HTML and bundled static assets to an output directory."""

from __future__ import annotations

from pathlib import Path

from scrolly.errors import OutputError
from scrolly.render import iter_assets, mermaid_asset


def write_output(
    out_dir: Path,
    html: str,
    *,
    force: bool = False,
    has_mermaid: bool = False,
    inline: bool = True,
) -> None:
    """Write `html` as `out_dir/index.html` and optionally copy bundled assets.

    If `out_dir` exists and is non-empty, `force=True` is required to overwrite.
    In inline mode, only `index.html` is written (CSS/JS are embedded in the HTML).
    """
    if out_dir.exists():
        if not out_dir.is_dir():
            raise OutputError(f"output path is not a directory: {out_dir}")
        if any(out_dir.iterdir()) and not force:
            raise OutputError(f"output directory is not empty: {out_dir}. Pass --force to overwrite.")
    else:
        out_dir.mkdir(parents=True)

    (out_dir / "index.html").write_text(html)
    if not inline:
        for name, content in iter_assets():
            (out_dir / name).write_bytes(content)
        if has_mermaid:
            name, content = mermaid_asset()
            (out_dir / name).write_bytes(content)
