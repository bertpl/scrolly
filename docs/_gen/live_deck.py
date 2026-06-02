"""Build the live homepage deck embed.

Pure-logic half of the live-embed gen-files step: builds scrolly's own
stacked-diffs hero deck and returns the resulting self-contained HTML as
a string. The thin ``mkdocs_gen_files`` wrapper (``gen_live_deck.py``)
writes that string into the site tree. Keeping the build here — free of
any ``mkdocs_gen_files`` dependency — lets it be unit-tested without the
docs toolchain installed, mirroring the ``reference_content`` /
``gen_reference`` split.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from scrolly.pipeline import build_deck

# --- source deck (repo-relative, resolved from this file) ---
_REPO_ROOT = Path(__file__).resolve().parents[2]
HERO_DECK = _REPO_ROOT / "examples" / "stacked-diffs" / "deck.deck.json"

# Path inside the site tree the wrapper writes to; the homepage embeds it.
SITE_DEST = "live/hero/index.html"


def build_hero_html() -> str:
    """Build the hero deck and return its self-contained ``index.html``.

    The deck is built into a throwaway directory with assets inlined and
    mermaid kept offline, so the result is one file with no external
    references — the invariant the homepage iframe relies on.

    Returns:
        The full ``index.html`` text of the built hero deck.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_deck(HERO_DECK, out, force=True, offline=True)
        return (out / "index.html").read_text(encoding="utf-8")
