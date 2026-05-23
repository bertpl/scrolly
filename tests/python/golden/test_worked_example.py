"""Golden-HTML lock on the worked-example deck.

Builds ``examples/worked-example/`` with default flags (inline, compressed,
mini-map zoom control) and asserts the produced ``index.html`` is
byte-identical to the committed golden fixture. This is the safety net
for refactors that must not change rendered output — any byte difference
fails the test and points at the exact diff to inspect.

Regeneration is gated behind an opt-in env var to keep accidental updates
out of CI: set ``SCROLLY_UPDATE_GOLDENS=1`` when output legitimately
changes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scrolly.pipeline import build_deck
from tests.python.conftest import PROJECT_ROOT

EXAMPLE_DECK = PROJECT_ROOT / "examples" / "worked-example" / "deck.deck.json"
FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_FILE = FIXTURE_DIR / "worked_example.html"


def test_worked_example_golden(tmp_path: Path) -> None:
    """Default-flags build of the worked example is byte-identical to the committed golden.

    Args:
        tmp_path: pytest's per-test temp directory; receives the build output.
    """
    # --- arrange ----------------------
    out_dir = tmp_path / "out"

    # --- act --------------------------
    build_deck(EXAMPLE_DECK, out_dir)
    actual = (out_dir / "index.html").read_bytes()

    # --- assert -----------------------
    if os.environ.get("SCROLLY_UPDATE_GOLDENS") == "1":
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_bytes(actual)
        return

    if not GOLDEN_FILE.exists():
        pytest.fail(
            f"Golden fixture missing: {GOLDEN_FILE.relative_to(PROJECT_ROOT)}.\n"
            f"Regenerate with: SCROLLY_UPDATE_GOLDENS=1 uv run pytest tests/python/golden/"
        )

    expected = GOLDEN_FILE.read_bytes()
    if actual == expected:
        return

    debug_path = FIXTURE_DIR / "worked_example.actual.html"
    debug_path.write_bytes(actual)
    pytest.fail(
        f"Worked-example HTML diverged from golden.\n"
        f"  golden: {GOLDEN_FILE.relative_to(PROJECT_ROOT)} ({len(expected)} bytes)\n"
        f"  actual: {debug_path.relative_to(PROJECT_ROOT)} ({len(actual)} bytes)\n"
        f"Inspect with: diff {GOLDEN_FILE.relative_to(PROJECT_ROOT)} {debug_path.relative_to(PROJECT_ROOT)}\n"
        f"If the change is intentional, regenerate with:\n"
        f"  SCROLLY_UPDATE_GOLDENS=1 uv run pytest tests/python/golden/"
    )
