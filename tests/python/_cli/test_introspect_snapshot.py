"""Tests for ``scrolly introspect snapshot``."""

from __future__ import annotations

import json

from click.testing import CliRunner

from scrolly._cli._cli import cli
from tests.python.conftest import PROJECT_ROOT

REGRESSION_DECK = PROJECT_ROOT / "examples" / "_regression" / "deck.deck.json"


def test_snapshot_returns_resolved_substrate_properties() -> None:
    """Snapshot resolves position, width, height, anchor, opacity, scale, angle + visible."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "capability", "--scroll", "500"],
    )

    # --- assert -----------------------
    assert result.exit_code == 0
    payload = json.loads(result.output)
    snap = payload["slides"]["capability"]["snapshots"][0]
    assert snap["scroll"] == 500.0
    el = snap["elements"][0]
    expected_keys = {
        "index",
        "name",
        "type",
        "position",
        "width",
        "height",
        "anchor",
        "opacity",
        "scale",
        "angle",
        "visible",
    }
    assert expected_keys <= set(el.keys())


def test_snapshot_multiple_scrolls_returns_one_snapshot_per_value() -> None:
    """``--scroll 0 --scroll 750`` returns two snapshots in order."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        [
            "introspect",
            "snapshot",
            str(REGRESSION_DECK),
            "--slide",
            "capability",
            "--scroll",
            "0",
            "--scroll",
            "750",
        ],
    )

    # --- assert -----------------------
    payload = json.loads(result.output)
    snaps = payload["slides"]["capability"]["snapshots"]
    assert [s["scroll"] for s in snaps] == [0.0, 750.0]


def test_snapshot_missing_slide_arg_errors() -> None:
    """``--slide`` is mandatory; missing it exits with a Click usage error."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "snapshot", str(REGRESSION_DECK), "--scroll", "0"])

    # --- assert -----------------------
    assert result.exit_code != 0
    assert "--slide" in result.output or "Missing option" in result.output


def test_snapshot_missing_scroll_arg_errors() -> None:
    """``--scroll`` is mandatory; missing it exits with a Click usage error."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(cli, ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "capability"])

    # --- assert -----------------------
    assert result.exit_code != 0
    assert "--scroll" in result.output or "Missing option" in result.output


def test_snapshot_scroll_beyond_range_rejected() -> None:
    """Scroll exceeding the slide's scroll_range exits with a clear error."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "capability", "--scroll", "99999"],
    )

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "out-of-range" in result.output
    assert "99999" in result.output


def test_snapshot_negative_scroll_rejected() -> None:
    """Negative scroll values are physically unreachable and rejected."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "capability", "--scroll", "-10"],
    )

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "out-of-range" in result.output


def test_snapshot_unknown_slide_id_rejected() -> None:
    """Unknown slide id exits with a clear message naming the unknown id."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "ghost", "--scroll", "0"],
    )

    # --- assert -----------------------
    assert result.exit_code == 1
    assert "ghost" in result.output


def test_snapshot_visible_flag_tracks_opacity() -> None:
    """Every element has ``visible`` derived from ``opacity > 0``."""
    # --- arrange ----------------------
    runner = CliRunner()

    # --- act --------------------------
    result = runner.invoke(
        cli,
        ["introspect", "snapshot", str(REGRESSION_DECK), "--slide", "capability", "--scroll", "0"],
    )

    # --- assert -----------------------
    payload = json.loads(result.output)
    for snap in payload["slides"]["capability"]["snapshots"]:
        for el in snap["elements"]:
            assert el["visible"] == (el["opacity"] > 0)
