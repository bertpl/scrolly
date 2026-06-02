"""``mkdocs-gen-files`` entry point for the live homepage deck embed.

Runs in-process during ``mkdocs build`` (Mechanism B), so local and Read
the Docs builds produce identical output. Builds scrolly's own
stacked-diffs hero deck (via :mod:`live_deck`) and writes the resulting
self-contained file to ``live/hero/index.html`` in the site tree, where
the homepage iframe-embeds it. Gitignored and regenerated every build —
the deck under ``examples/stacked-diffs/`` is the source of truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_deck  # noqa: E402
import mkdocs_gen_files  # noqa: E402

with mkdocs_gen_files.open(live_deck.SITE_DEST, "w") as f:
    f.write(live_deck.build_hero_html())
