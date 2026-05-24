"""Build orchestration — glues deck loading, slide rendering, and output writing.

Pipeline (driven by ``build_deck``):
    deck, slide_irs = load_deck(path)
    chunks = _render_slides(deck.slides, slide_irs, bundler=...)
    chunks = rewrite_asset_refs(chunks, inline=..., bundler=...)
    html = assemble(deck, chunks, ...)
    write_output(out_dir, html, ...)

``load_deck`` lives in ``scrolly.pipeline.loader`` and runs the
deck-level chain from ``scrolly.deck`` plus per-slide IR loading; the
remaining steps are orchestrated in ``scrolly.pipeline.orchestrator``,
which also threads the optional compressed-payload bundler through
the rendering and asset-rewriting stages.
"""

from scrolly.pipeline.loader import load_deck
from scrolly.pipeline.orchestrator import build_deck
from scrolly.pipeline.writer import write_output

__all__ = ["build_deck", "load_deck", "write_output"]
