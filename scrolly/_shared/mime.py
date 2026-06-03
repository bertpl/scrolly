"""Single source of truth for the image formats scrolly supports.

The supported set lives here once, as ``{extension -> MIME type}``. Asset
delivery (``pipeline/assets.py``) resolves a path's MIME type for inlining
and gates unsupported formats; ``scrolly introspect assets`` reports the
same MIME type; the help-screen payload stats (``render/assembler.py``)
map a MIME type back to a friendly extension label. All three derive from
the maps here so the accepted set can't drift between them.
"""

from __future__ import annotations

from pathlib import Path

_EXT_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


def _build_mime_to_ext() -> dict[str, str]:
    """Invert ``_EXT_TO_MIME``; the first extension for each MIME type wins.

    ``.jpg`` precedes ``.jpeg`` in ``_EXT_TO_MIME``, so ``image/jpeg`` maps
    back to ``.jpg`` — the canonical label for the help-screen stats.
    """
    inverse: dict[str, str] = {}
    for ext, mime in _EXT_TO_MIME.items():
        inverse.setdefault(mime, ext)
    return inverse


_MIME_TO_EXT = _build_mime_to_ext()


def mime_for(path: Path) -> str | None:
    """Return the MIME type for ``path``'s extension, or ``None`` if unsupported."""
    return _EXT_TO_MIME.get(path.suffix.lower())


def ext_for(mime: str) -> str | None:
    """Return the canonical file extension for a supported image MIME type, or ``None``."""
    return _MIME_TO_EXT.get(mime)


def supported_extensions() -> list[str]:
    """Return the sorted list of supported image-file extensions."""
    return sorted(_EXT_TO_MIME)
