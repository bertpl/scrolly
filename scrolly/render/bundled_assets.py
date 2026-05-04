"""Bundled static assets (canvas.css, canvas.js) shipped with the output."""

from __future__ import annotations

import urllib.request
from importlib.resources import files
from pathlib import Path

_BUNDLED_ASSET_NAMES: tuple[str, ...] = ("canvas.css", "canvas.js")

_MERMAID_VERSION = "11.4.1"
_MERMAID_URL = f"https://cdn.jsdelivr.net/npm/mermaid@{_MERMAID_VERSION}/dist/mermaid.min.js"
_MERMAID_CACHE_DIR = Path.home() / ".cache" / "scrolly"
_MERMAID_CACHE_PATH = _MERMAID_CACHE_DIR / f"mermaid-{_MERMAID_VERSION}.min.js"


def iter_assets() -> list[tuple[str, bytes]]:
    """Return each bundled static asset as (filename, content_bytes)."""
    base = files("scrolly.render").joinpath("assets")
    return [(name, base.joinpath(name).read_bytes()) for name in _BUNDLED_ASSET_NAMES]


def bundled_css() -> str:
    """Return the canvas CSS content as a string."""
    base = files("scrolly.render").joinpath("assets")
    return base.joinpath("canvas.css").read_text(encoding="utf-8")


def bundled_js() -> str:
    """Return the canvas JS content as a string."""
    base = files("scrolly.render").joinpath("assets")
    return base.joinpath("canvas.js").read_text(encoding="utf-8")


def mermaid_js() -> str:
    """Return the mermaid JS content as a string, downloading if needed."""
    _, content = mermaid_asset()
    return content.decode("utf-8")


def mermaid_asset() -> tuple[str, bytes]:
    """Return the mermaid.js asset, downloading and caching on first use."""
    if not _MERMAID_CACHE_PATH.exists():
        _MERMAID_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(_MERMAID_URL, _MERMAID_CACHE_PATH)
        except Exception as exc:
            _MERMAID_CACHE_PATH.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download mermaid.js v{_MERMAID_VERSION} from {_MERMAID_URL}: {exc}\n"
                f"Mermaid.js is required because this deck uses MermaidElement. "
                f"Check your internet connection, or manually place the file at:\n"
                f"  {_MERMAID_CACHE_PATH}"
            ) from exc
    return ("mermaid.min.js", _MERMAID_CACHE_PATH.read_bytes())
