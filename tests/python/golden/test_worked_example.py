"""Golden-HTML lock on the worked-example deck.

Builds ``examples/worked-example/`` with ``compress=False`` (inline,
mini-map zoom control, plain inline payloads) and asserts the produced
``index.html`` matches the committed golden fixture. This is the safety
net for refactors that must not change rendered output — any byte
difference fails the test and points at the exact diff to inspect.

Compression is deliberately disabled: gzip output is sensitive to the
underlying zlib version and to a platform-dependent OS byte in the gzip
header, so a compressed golden would be brittle across the CI matrix.
The element-mechanism work this safety net guards touches HTML / CSS /
asset wiring — not the compression pass — so the uncompressed form
covers the relevant surface in full.

Two transient substrings are normalised before comparison so the
golden survives orthogonal events that aren't about rendering:

- The scrolly version embedded in the ``scrolly-meta`` payload, which
  bumps on every release.
- The ``file_size`` value in that same payload, which is the serialised
  length of the surrounding HTML — a one-byte change in the version
  string ripples one byte into ``file_size``.

Regeneration is gated behind an opt-in env var to keep accidental updates
out of CI: set ``SCROLLY_UPDATE_GOLDENS=1`` when output legitimately
changes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from scrolly.pipeline import build_deck
from tests.python.conftest import PROJECT_ROOT

EXAMPLE_DECK = PROJECT_ROOT / "examples" / "worked-example" / "deck.deck.json"
FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_FILE = FIXTURE_DIR / "worked_example.html"

# Substring patterns whose contents vary independently of rendering.
# Normalised on both sides before equality check.
_NORMALISE_PATTERNS: tuple[tuple[bytes, bytes], ...] = (
    (rb'"version": "[^"]*"', b'"version": "<NORMALISED>"'),
    (rb'"file_size": \d+', b'"file_size": <NORMALISED>'),
)


def _normalise(html: bytes) -> bytes:
    """Mask transient substrings in the rendered HTML for stable comparison."""
    for pattern, replacement in _NORMALISE_PATTERNS:
        html = re.sub(pattern, replacement, html)
    return html


def test_worked_example_golden(tmp_path: Path) -> None:
    """Normalised inline build of the worked example matches the committed golden.

    Args:
        tmp_path: pytest's per-test temp directory; receives the build output.
    """
    # --- arrange ----------------------
    out_dir = tmp_path / "out"

    # --- act --------------------------
    build_deck(EXAMPLE_DECK, out_dir, compress=False)
    actual = (out_dir / "index.html").read_bytes()
    actual_normalised = _normalise(actual)

    # --- assert -----------------------
    if os.environ.get("SCROLLY_UPDATE_GOLDENS") == "1":
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_bytes(actual_normalised)
        return

    if not GOLDEN_FILE.exists():
        pytest.fail(
            f"Golden fixture missing: {GOLDEN_FILE.relative_to(PROJECT_ROOT)}.\n"
            f"Regenerate with: SCROLLY_UPDATE_GOLDENS=1 uv run pytest tests/python/golden/"
        )

    expected = GOLDEN_FILE.read_bytes()
    if actual_normalised == expected:
        return

    debug_path = FIXTURE_DIR / "worked_example.actual.html"
    debug_path.write_bytes(actual_normalised)
    pytest.fail(
        f"Worked-example HTML diverged from golden (after version / file_size normalisation).\n"
        f"  golden: {GOLDEN_FILE.relative_to(PROJECT_ROOT)} ({len(expected)} bytes)\n"
        f"  actual: {debug_path.relative_to(PROJECT_ROOT)} ({len(actual_normalised)} bytes)\n"
        f"Inspect with: diff {GOLDEN_FILE.relative_to(PROJECT_ROOT)} {debug_path.relative_to(PROJECT_ROOT)}\n"
        f"If the change is intentional, regenerate with:\n"
        f"  SCROLLY_UPDATE_GOLDENS=1 uv run pytest tests/python/golden/"
    )
