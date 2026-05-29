"""Recipe-driven engine that turns a built scrolly deck into an animation.

The engine runs in two stages from a single committed recipe file:

1. **Capture** (`capture.py`) — Playwright drives the deck's automation
   hook and screenshots raw frames to a cache directory.
2. **Composite** (`composite.py`) — Pillow burns the recipe's overlays
   (captions, cursor, click / key cues) onto the cached frames, then
   gifski assembles the result.

Stage 1 and the heavy Pillow/Playwright dependencies are isolated in
`capture.py` / `composite.py` and imported lazily, so the pure logic in
`recipe.py` (parsing / validation) and `plan.py` (frame planning) can be
imported and unit-tested without the optional ``capture`` dependency
group installed.
"""

from __future__ import annotations

from .plan import build_frame_plan
from .recipe import Recipe, load_recipe

__all__ = ["Recipe", "load_recipe", "build_frame_plan"]
