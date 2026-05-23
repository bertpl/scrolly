"""Tests for the lint module (--strict checks)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrolly.pipeline.lint import Diagnostic, lint_deck
from scrolly.pipeline.orchestrator import validate_deck_sources

# --------------------------------------------------------------------------
#  Helpers
# --------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).parents[3] / "examples"


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _make_deck(tmp_path: Path, slide_content: str, slide_name: str = "s.scrollimation.json"):
    """Create a minimal deck with one scrollimation slide and return the validated Deck."""
    _write(tmp_path / "slides" / slide_name, slide_content)
    deck_json = f"""{{
  title: "Test",
  slides: [{{ id: "s", position: [0, 0], source: "slides/{slide_name}" }}],
  edges: [],
}}"""
    _write(tmp_path / "deck.deck.json", deck_json)
    return validate_deck_sources(tmp_path / "deck.deck.json")


# --------------------------------------------------------------------------
#  Tests
# --------------------------------------------------------------------------
class TestOutOfRangeKeyframes:
    """Tests for the out-of-range keyframe lint rule."""

    def test_no_warnings_for_in_range_keyframes(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 1000,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      opacity: { keyframes: [[0, 1], [1000, 0]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert diagnostics == []

    def test_warns_on_keyframe_beyond_scroll_range(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 1000,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      opacity: { keyframes: [[0, 1], [1200, 0]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert len(diagnostics) == 1
        assert diagnostics[0].level == "warning"
        assert "1200" in diagnostics[0].message
        assert "opacity" in diagnostics[0].location

    def test_warns_on_negative_keyframe(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 1000,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      opacity: { keyframes: [[-100, 0], [500, 1]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert len(diagnostics) == 1
        assert "-100" in diagnostics[0].message

    def test_warns_on_animated_position_out_of_range(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 500,
  elements: [
    { html: "<p>hi</p>", position: { keyframes: [[0, [0, 0]], [600, [50, 50]]] },
      width: 100, height: 100 },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert len(diagnostics) == 1
        assert "position" in diagnostics[0].location

    def test_warns_on_animated_anchor_out_of_range(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 1000,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      anchor: { keyframes: [[0, [0, 0]], [1500, [50, 50]]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert len(diagnostics) == 1
        assert "anchor" in diagnostics[0].location

    def test_multiple_fields_produce_multiple_warnings(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 100,
  elements: [
    { html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      opacity: { keyframes: [[0, 1], [200, 0]] },
      scale: { keyframes: [[-50, 1], [100, 2]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert len(diagnostics) == 2

    def test_uses_element_name_in_location(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        deck = _make_deck(
            tmp_path,
            """{
  title: "T",
  scroll_range: 100,
  elements: [
    { name: "my-element", html: "<p>hi</p>", position: [0, 0], width: 100, height: 100,
      opacity: { keyframes: [[0, 1], [200, 0]] } },
  ],
}""",
        )

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert "'my-element'" in diagnostics[0].location

    def test_no_warnings_for_storyboard_slides(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        _write(
            tmp_path / "slides" / "s.storyboard.json",
            """{
  title: "T",
  scene_distance: 300,
  scenes: [
    { elements: [{ html: "<p>A</p>", position: [0, 0], width: 100, height: "auto" }] },
    { elements: [{ html: "<p>B</p>", position: [0, 0], width: 100, height: "auto" }] },
  ],
}""",
        )
        deck_json = """{
  title: "Test",
  slides: [{ id: "s", position: [0, 0], source: "slides/s.storyboard.json" }],
  edges: [],
}"""
        _write(tmp_path / "deck.deck.json", deck_json)
        deck = validate_deck_sources(tmp_path / "deck.deck.json")

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert diagnostics == []

    def test_no_warnings_on_worked_example(self) -> None:
        # --- arrange ----------------------
        deck = validate_deck_sources(EXAMPLES_DIR / "worked-example" / "deck.deck.json")

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert diagnostics == []


class TestImageSequenceTimeline:
    """Tests for the image-sequence timeline lint rule."""

    def _seq_slide(self, scroll_range: int, **fields) -> str:
        extra = "".join(f"      {k}: {v},\n" for k, v in fields.items())
        return (
            "{\n"
            '  title: "T",\n'
            f"  scroll_range: {scroll_range},\n"
            "  elements: [\n"
            "    {\n"
            '      image_sequence: ["a.svg", "b.svg"],\n'
            "      frame_distance: 400,\n"
            "      hold: 200,\n"
            "      position: [0, 0],\n"
            "      width: 80,\n"
            '      height: "auto",\n'
            f"{extra}"
            "    },\n"
            "  ],\n"
            "}\n"
        )

    def test_no_warning_when_timeline_fits(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / "slides" / name, "<svg/>")
        deck = _make_deck(tmp_path, self._seq_slide(scroll_range=1000))

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert diagnostics == []

    def test_warns_when_fade_in_pushes_below_zero(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / "slides" / name, "<svg/>")
        deck = _make_deck(tmp_path, self._seq_slide(scroll_range=1000, scroll_offset=100, fade_in=300))

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        assert any("starts at -200" in d.message for d in diagnostics)

    def test_warns_when_fade_out_pushes_past_scroll_range(self, tmp_path: Path) -> None:
        # --- arrange ----------------------
        for name in ("a.svg", "b.svg"):
            _write(tmp_path / "slides" / name, "<svg/>")
        deck = _make_deck(tmp_path, self._seq_slide(scroll_range=500, fade_out=200))

        # --- act --------------------------
        diagnostics = lint_deck(deck)

        # --- assert -----------------------
        # Timeline ends at 0 + 1*400 + 200 + 200 = 800, past scroll_range=500.
        assert any("ends at 800" in d.message for d in diagnostics)


class TestDiagnosticDataclass:
    """Tests for the Diagnostic dataclass."""

    def test_frozen(self) -> None:
        d = Diagnostic(level="warning", message="test", location="here")
        with pytest.raises(AttributeError):
            d.level = "info"

    def test_equality(self) -> None:
        d1 = Diagnostic(level="warning", message="x", location="y")
        d2 = Diagnostic(level="warning", message="x", location="y")
        assert d1 == d2
