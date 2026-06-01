"""Unit tests for the output assembly: format selection + command builders.

These cover the pure logic in `composite.py` — which output blocks get
assembled, and the gifski / img2webp argv each produces. Neither Pillow
nor the encoder binaries are needed (subprocess is stubbed), so unlike
`test_composite` these run under the plain dev dependency set, guarding
the format wiring.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest
from animation_engine import composite
from animation_engine.composite import _gif_cmd, _webp_cmd
from animation_engine.recipe import Gif, Output, Recipe, Viewport, Webp


def _recipe(output: Output, fps: int = 20) -> Recipe:
    """A Recipe carrying just the fields the assembly builders read."""
    return Recipe(
        deck="d",
        viewport=Viewport(width=10, height=10, scale=1, output_scale=1),
        fps=fps,
        output=output,
        steps=(),
        overlays=(),
    )


# ==================================================================================================
#  Format selection — which blocks get assembled
# ==================================================================================================
def _capture_assembly(monkeypatch, tmp_path: Path, output: Output) -> tuple[list[list[str]], list[Path]]:
    """Run `_assemble` with subprocess stubbed; return the issued commands + output paths."""
    # --- arrange ----------------------
    cmds: list[list[str]] = []
    monkeypatch.setattr(composite.subprocess, "run", lambda cmd, check=True: cmds.append(cmd))
    monkeypatch.setattr(composite, "_frame_width", lambda path: 1282)  # frames are stubs, not real files
    plan = types.SimpleNamespace(total_frames=2)

    # --- act --------------------------
    outputs = composite._assemble(_recipe(output), plan, tmp_path)
    return cmds, outputs


def test_assemble_gif_only_runs_gifski(monkeypatch, tmp_path) -> None:
    # --- act --------------------------
    cmds, outputs = _capture_assembly(monkeypatch, tmp_path, Output(gif=Gif(path=str(tmp_path / "h.gif"))))

    # --- assert -----------------------
    assert [c[0] for c in cmds] == ["gifski"]
    assert [p.name for p in outputs] == ["h.gif"]


def test_assemble_webp_only_runs_img2webp(monkeypatch, tmp_path) -> None:
    # --- act --------------------------
    cmds, outputs = _capture_assembly(monkeypatch, tmp_path, Output(webp=Webp(path=str(tmp_path / "h.webp"))))

    # --- assert -----------------------
    assert [c[0] for c in cmds] == ["img2webp"]
    assert [p.name for p in outputs] == ["h.webp"]


def test_assemble_both_runs_gifski_then_img2webp(monkeypatch, tmp_path) -> None:
    # --- arrange ----------------------
    output = Output(gif=Gif(path=str(tmp_path / "h.gif")), webp=Webp(path=str(tmp_path / "h.webp")))

    # --- act --------------------------
    cmds, outputs = _capture_assembly(monkeypatch, tmp_path, output)

    # --- assert -----------------------
    assert [c[0] for c in cmds] == ["gifski", "img2webp"]
    assert [p.name for p in outputs] == ["h.gif", "h.webp"]


# ==================================================================================================
#  gifski command
# ==================================================================================================
def test_gif_cmd_basic() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(gif=Gif(path="hero.gif", quality=90)), fps=20)

    # --- act --------------------------
    cmd = _gif_cmd(recipe, Path("hero.gif"), ["a.png", "b.png"], 1282)

    # --- assert -----------------------
    # --width pins native resolution (no gifski downsize cap).
    assert cmd == [
        "gifski",
        "--fps",
        "20",
        "--quality",
        "90",
        "--width",
        "1282",
        "-o",
        "hero.gif",
        "a.png",
        "b.png",
    ]


def test_gif_cmd_no_loop_adds_repeat_flag() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(loop=False, gif=Gif(path="hero.gif")))

    # --- act --------------------------
    cmd = _gif_cmd(recipe, Path("hero.gif"), ["a.png"], 1000)

    # --- assert -----------------------
    assert cmd[-3:] == ["--repeat", "-1", "a.png"]


# ==================================================================================================
#  img2webp command
# ==================================================================================================
def test_webp_cmd_lossy_default() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(webp=Webp(path="hero.webp", quality=80.0, method=6)), fps=20)

    # --- act --------------------------
    cmd = _webp_cmd(recipe, Path("hero.webp"), ["a.png", "b.png"])

    # --- assert -----------------------
    # fps 20 -> 50 ms/frame; infinite loop; lossy q80, method 6; -o trails.
    assert cmd == [
        "img2webp",
        "-loop",
        "0",
        "-d",
        "50",
        "-m",
        "6",
        "-lossy",
        "-q",
        "80.0",
        "a.png",
        "b.png",
        "-o",
        "hero.webp",
    ]


def test_webp_cmd_no_loop() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(loop=False, webp=Webp(path="hero.webp")))

    # --- act --------------------------
    cmd = _webp_cmd(recipe, Path("hero.webp"), ["a.png"])

    # --- assert -----------------------
    assert cmd[:3] == ["img2webp", "-loop", "1"]


def test_webp_cmd_near_lossless_omits_quality_and_sets_file_flag() -> None:
    # --- arrange ----------------------
    webp = Webp(path="hero.webp", mode="near_lossless", near_lossless=40, method=5)
    recipe = _recipe(Output(webp=webp), fps=25)

    # --- act --------------------------
    cmd = _webp_cmd(recipe, Path("hero.webp"), ["a.png"])

    # --- assert -----------------------
    # File-level -near_lossless precedes the frame opts; no -lossy / -q (lossless coding).
    assert cmd == [
        "img2webp",
        "-loop",
        "0",
        "-near_lossless",
        "40",
        "-d",
        "40",
        "-m",
        "5",
        "a.png",
        "-o",
        "hero.webp",
    ]
    assert "-q" not in cmd and "-lossy" not in cmd


def test_webp_cmd_lossless_mode() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(webp=Webp(path="hero.webp", mode="lossless")))

    # --- act --------------------------
    cmd = _webp_cmd(recipe, Path("hero.webp"), ["a.png"])

    # --- assert -----------------------
    assert "-lossless" in cmd and "-lossy" not in cmd and "-q" not in cmd


def test_webp_cmd_mixed_keeps_quality_without_lossy_flag() -> None:
    # --- arrange ----------------------
    recipe = _recipe(Output(webp=Webp(path="hero.webp", mode="mixed", quality=70.0)))

    # --- act --------------------------
    cmd = _webp_cmd(recipe, Path("hero.webp"), ["a.png"])

    # --- assert -----------------------
    assert "-mixed" in cmd and "-q" in cmd and "70.0" in cmd and "-lossy" not in cmd
