"""Bundled static assets shipped with the output (canvas.css, canvas.js, mermaid.min.js).

Canvas JS and CSS are minified (rjsmin/rcssmin: comments and
inter-token whitespace stripped, semantics untouched) before they
ship, so built decks don't carry source comments; the tracked
``assets/canvas.js`` and ``assets/canvas.css`` stay the readable
files of record.

Mermaid uses a two-tier resolution chain: try jsdelivr first
(``mermaid@11`` major-version pin) for freshness, fall back to the
wheel-bundled copy when the network is unreachable or when the user
forces offline mode via ``--offline`` / ``SCROLLY_OFFLINE=1``.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.resources import files

import rcssmin
import rjsmin

_BUNDLED_ASSET_NAMES: tuple[str, ...] = ("canvas.css", "canvas.js")

# Major-version pin so users on the network get mermaid 11.x patches and
# minor releases automatically; the bundled file is the offline-safe
# baseline. Bumps to mermaid@12 (or whatever the next major is) require
# deliberate scrolly action: update this URL + regenerate the bundled
# file from the new major.
_MERMAID_CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
_MERMAID_CDN_TIMEOUT_SECONDS = 5.0

# Mermaid embeds its version exactly once in the minified bundle as
# ``version:"X.Y.Z"`` (verified against 11.15.0). Match three numeric
# components; if the format ever changes, the help-screen reports
# "unknown" rather than crashing the build.
_MERMAID_VERSION_RE = re.compile(rb'version:"(\d+\.\d+\.\d+)"')

_OFFLINE_ENV_VAR = "SCROLLY_OFFLINE"
_OFFLINE_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class MermaidAsset:
    """A resolved mermaid asset, ready to inline or write to disk."""

    name: str
    content: bytes
    version: str
    source: str  # "cdn" | "bundled"


def iter_assets(*, minify: bool = True) -> list[tuple[str, bytes]]:
    """Return each bundled static asset as (filename, content_bytes).

    Args:
        minify: Minify the JS and CSS assets (see :func:`bundled_js` /
            :func:`bundled_css`).
    """
    base = files("scrolly.render").joinpath("assets")
    assets: list[tuple[str, bytes]] = []
    for name in _BUNDLED_ASSET_NAMES:
        content = base.joinpath(name).read_bytes()
        if minify:
            content = _minify(name, content.decode("utf-8")).encode("utf-8")
        assets.append((name, content))
    return assets


def bundled_css(*, minify: bool = True) -> str:
    """Return the canvas CSS content as a string, minified by default.

    Args:
        minify: Strip comments and collapse whitespace via rcssmin.
            ``False`` returns the readable source verbatim (the
            ``--no-minification`` debug path).
    """
    base = files("scrolly.render").joinpath("assets")
    css = base.joinpath("canvas.css").read_text(encoding="utf-8")
    return rcssmin.cssmin(css) if minify else css


def bundled_js(*, minify: bool = True) -> str:
    """Return the canvas JS content as a string, minified by default.

    Args:
        minify: Strip comments and collapse whitespace via rjsmin.
            ``False`` returns the readable source verbatim (the
            ``--no-minification`` debug path).
    """
    base = files("scrolly.render").joinpath("assets")
    js = base.joinpath("canvas.js").read_text(encoding="utf-8")
    return rjsmin.jsmin(js) if minify else js


def _minify(name: str, content: str) -> str:
    """Minify an asset by file type; non-JS/CSS content passes through verbatim."""
    if name.endswith(".js"):
        return rjsmin.jsmin(content)
    if name.endswith(".css"):
        return rcssmin.cssmin(content)
    return content


def mermaid_asset(*, offline: bool = False) -> MermaidAsset:
    """Resolve mermaid.js via CDN-first-with-bundled-fallback.

    Tries jsdelivr first (``mermaid@11`` major-version pin); on network
    failure (or when offline mode is requested), falls back to the
    wheel-bundled copy and emits a one-line stderr notice.

    Args:
        offline: ``True`` to skip the CDN entirely. The
            ``SCROLLY_OFFLINE`` environment variable
            (``1``/``true``/``yes``/``on``, case-insensitive) is
            honored independently — set either to force offline mode.

    Returns:
        ``MermaidAsset`` with the resolved content, version string,
        and which tier of the fallback chain served it
        (``source="cdn"`` or ``source="bundled"``).
    """
    if offline or _offline_via_env():
        return _load_bundled()

    try:
        content = _fetch_cdn()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        bundled = _load_bundled()
        sys.stderr.write(
            f"scrolly: mermaid CDN unreachable ({type(exc).__name__}); using bundled mermaid {bundled.version}\n"
        )
        return bundled

    return MermaidAsset(
        name="mermaid.min.js",
        content=content,
        version=_extract_version(content),
        source="cdn",
    )


def _offline_via_env() -> bool:
    """Return ``True`` when ``SCROLLY_OFFLINE`` is set to a truthy value."""
    return os.environ.get(_OFFLINE_ENV_VAR, "").lower() in _OFFLINE_TRUTHY


def _fetch_cdn() -> bytes:
    """Download mermaid.min.js from the CDN.

    Raises:
        urllib.error.URLError: Network failure (connection refused,
            DNS failure, etc.).
        TimeoutError: Request exceeded ``_MERMAID_CDN_TIMEOUT_SECONDS``.
        OSError: Lower-level socket error.
    """
    with urllib.request.urlopen(_MERMAID_CDN_URL, timeout=_MERMAID_CDN_TIMEOUT_SECONDS) as resp:
        return resp.read()


def _load_bundled() -> MermaidAsset:
    """Load the wheel-bundled mermaid.min.js."""
    base = files("scrolly.render").joinpath("assets")
    content = base.joinpath("mermaid.min.js").read_bytes()
    return MermaidAsset(
        name="mermaid.min.js",
        content=content,
        version=_extract_version(content),
        source="bundled",
    )


def _extract_version(content: bytes) -> str:
    """Extract mermaid's version string from the minified blob.

    Args:
        content: Raw bytes of ``mermaid.min.js``.

    Returns:
        Version string like ``"11.15.0"``, or ``"unknown"`` if the
        embedded pattern isn't found (defensive — should not happen
        for a well-formed mermaid build).
    """
    match = _MERMAID_VERSION_RE.search(content)
    return match.group(1).decode("ascii") if match else "unknown"
