"""Tests for ``--json`` on ``scrolly validate``."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scrolly._cli.cli import cli


def _write_valid_deck(tmp_path: Path) -> Path:
    """Write a minimal valid deck + slide and return the deck path."""
    slide = tmp_path / "only.slide.json"
    slide.write_text(
        '{ title: "Only", elements: [{ markdown: "# Only", position: [0, 0], width: 100, height: "auto" }] }'
    )
    deck = tmp_path / "deck.deck.json"
    deck.write_text('{ slides: [{ id: "only", position: [0, 0], source: "only.slide.json" }], edges: [] }')
    return deck


def test_validate_json_ok_on_valid_deck(tmp_path: Path) -> None:
    """``--json`` on a valid deck emits ``{"ok": true, "errors": []}``."""
    # --- arrange ----------------------
    runner = CliRunner()
    deck = _write_valid_deck(tmp_path)

    # --- act --------------------------
    result = runner.invoke(cli, ["validate", str(deck), "--json"])

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"ok": True, "errors": []}


def test_validate_json_emits_code_on_failure(tmp_path: Path) -> None:
    """``--json`` on a broken deck emits ``{"ok": false, "errors": [{code, message, ...}]}``."""
    # --- arrange ----------------------
    runner = CliRunner()
    # Deck references a slide id that doesn't exist in slides — cross-ref failure (E501).
    deck = tmp_path / "deck.deck.json"
    deck.write_text(
        '{ slides: [{ id: "a", position: [0, 0], source: "a.slide.json" }], edges: [["a|right", "ghost|left"]] }'
    )
    (tmp_path / "a.slide.json").write_text(
        '{ title: "A", elements: [{ markdown: "# A", position: [0, 0], width: 100, height: "auto" }] }'
    )

    # --- act --------------------------
    result = runner.invoke(cli, ["validate", str(deck), "--json"])

    # --- assert -----------------------
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert len(payload["errors"]) == 1
    err = payload["errors"][0]
    assert err["code"] == "E501"
    assert "ghost" in err["message"]
