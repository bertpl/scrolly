"""Tests for the live homepage deck embed build."""

from __future__ import annotations

from pathlib import Path

import live_deck

from scrolly.pipeline import build_deck


# --- hero html build --------------------------------
def test_build_hero_html_returns_populated_document():
    # --- act --------------------------
    html = live_deck.build_hero_html()

    # --- assert -----------------------
    assert html.lstrip().startswith("<!")
    assert "Stacked Diffs" in html


# --- self-contained invariant -----------------------
def test_hero_deck_builds_to_single_self_contained_file(tmp_path: Path):
    # The homepage iframe points at live/hero/index.html and nothing else,
    # so the hero deck must inline every asset into that one file.

    # --- act --------------------------
    build_deck(live_deck.HERO_DECK, tmp_path, force=True, offline=True)

    # --- assert -----------------------
    assert [p.name for p in tmp_path.iterdir()] == ["index.html"]
