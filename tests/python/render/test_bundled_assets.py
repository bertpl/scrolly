"""Tests for `scrolly.render.bundled_assets`: mermaid resolution chain and JS minification."""

from __future__ import annotations

import shutil
import subprocess
import urllib.error
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from scrolly.render import bundled_assets
from scrolly.render.bundled_assets import MermaidAsset, mermaid_asset

# ---- offline mode -----------------------------------


def test_offline_flag_forces_bundled(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    # Clear env so the explicit flag is what drives the path.
    monkeypatch.delenv("SCROLLY_OFFLINE", raising=False)
    _fail_cdn(monkeypatch)  # would explode if CDN was tried

    # --- act --------------------------
    asset = mermaid_asset(offline=True)

    # --- assert -----------------------
    assert asset.source == "bundled"
    assert asset.name == "mermaid.min.js"
    assert asset.version != "unknown"
    assert asset.content.startswith(b'"use strict"')


def test_env_var_forces_bundled(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    monkeypatch.setenv("SCROLLY_OFFLINE", "1")
    _fail_cdn(monkeypatch)

    # --- act --------------------------
    asset = mermaid_asset()  # offline=False default; env var should still win

    # --- assert -----------------------
    assert asset.source == "bundled"


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_env_var_truthy_values(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    monkeypatch.setenv("SCROLLY_OFFLINE", value)
    _fail_cdn(monkeypatch)

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    assert asset.source == "bundled"


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "anything-else"])
def test_env_var_falsy_values_let_cdn_run(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    # Any non-truthy value (including "0" / "false") lets the CDN path run.
    # Mock the CDN so we don't actually hit jsdelivr.
    monkeypatch.setenv("SCROLLY_OFFLINE", value)
    _mock_cdn_success(monkeypatch)

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    assert asset.source == "cdn"


# ---- CDN success path -------------------------------


def test_cdn_success_returns_cdn_source(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    monkeypatch.delenv("SCROLLY_OFFLINE", raising=False)
    _mock_cdn_success(monkeypatch)

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    assert asset.source == "cdn"
    assert asset.version == "11.99.0"  # version embedded in mock content
    assert asset.name == "mermaid.min.js"


# ---- CDN failure → bundled fallback ----------------


def test_cdn_failure_falls_back_to_bundled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # --- arrange ----------------------
    monkeypatch.delenv("SCROLLY_OFFLINE", raising=False)
    _fail_cdn(monkeypatch)

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    assert asset.source == "bundled"
    assert asset.version != "unknown"
    err = capsys.readouterr().err
    assert "mermaid CDN unreachable" in err
    assert f"using bundled mermaid {asset.version}" in err


@pytest.mark.parametrize(
    "exception",
    [
        urllib.error.URLError("no route"),
        TimeoutError("slow CDN"),
        OSError("socket dead"),
    ],
)
def test_cdn_failure_handles_each_expected_exception(
    exception: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --- arrange ----------------------
    monkeypatch.delenv("SCROLLY_OFFLINE", raising=False)

    def _boom(*_a: Any, **_kw: Any) -> None:
        raise exception

    monkeypatch.setattr(bundled_assets.urllib.request, "urlopen", _boom)

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    assert asset.source == "bundled"


# ---- bundled asset shape ---------------------------


def test_bundled_asset_carries_version(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- arrange ----------------------
    monkeypatch.setenv("SCROLLY_OFFLINE", "1")

    # --- act --------------------------
    asset = mermaid_asset()

    # --- assert -----------------------
    # Bundled file must always have a parseable version (the regex would
    # surface "unknown" only on a malformed mermaid blob — not the case
    # for an MIT-licensed jsdelivr download).
    assert asset.version != "unknown"
    # Sanity: SemVer-ish shape.
    parts = asset.version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_mermaid_asset_dataclass_is_frozen() -> None:
    # --- arrange / act ----------------
    asset = MermaidAsset(name="x.js", content=b"abc", version="1.2.3", source="bundled")

    # --- assert -----------------------
    with pytest.raises(AttributeError):
        asset.version = "9.9.9"  # type: ignore[misc]


# ---- _extract_version corner cases -----------------


def test_extract_version_finds_embedded_version() -> None:
    # --- arrange ----------------------
    content = b'unrelated...version:"12.34.567"...more'

    # --- act --------------------------
    version = bundled_assets._extract_version(content)

    # --- assert -----------------------
    assert version == "12.34.567"


def test_extract_version_returns_unknown_when_pattern_missing() -> None:
    # --- arrange ----------------------
    content = b"no version string here"

    # --- act --------------------------
    version = bundled_assets._extract_version(content)

    # --- assert -----------------------
    assert version == "unknown"


# ---- helpers ---------------------------------------


def _fail_cdn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace urlopen with one that always raises a URLError."""

    def _boom(*_a: Any, **_kw: Any) -> None:
        raise urllib.error.URLError("test: network disabled")

    monkeypatch.setattr(bundled_assets.urllib.request, "urlopen", _boom)


def _mock_cdn_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace urlopen with one that returns a fake mermaid blob."""
    fake_content = b'"use strict";...version:"11.99.0"...more code'

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

    def _open(*_a: Any, **_kw: Any) -> _FakeResponse:
        return _FakeResponse(fake_content)

    monkeypatch.setattr(bundled_assets.urllib.request, "urlopen", _open)


# ---- JS/CSS minification ----------------------------


def test_bundled_js_minified_by_default() -> None:
    # --- act --------------------------
    minified = bundled_assets.bundled_js()
    source = bundled_assets.bundled_js(minify=False)

    # --- assert -----------------------
    assert len(minified) < len(source)
    assert "/*" not in minified
    assert "// ----" not in minified
    # Load-bearing identifiers survive (rjsmin never renames).
    assert "ScrollManager" in minified
    assert "mapBundleAssignments" in minified


def test_bundled_js_unminified_is_source_verbatim() -> None:
    # --- arrange ----------------------
    raw = files("scrolly.render").joinpath("assets", "canvas.js").read_text(encoding="utf-8")

    # --- act / assert -----------------
    assert bundled_assets.bundled_js(minify=False) == raw


def test_bundled_css_minified_by_default() -> None:
    # --- act --------------------------
    minified = bundled_assets.bundled_css()
    source = bundled_assets.bundled_css(minify=False)

    # --- assert -----------------------
    assert len(minified) < len(source)
    assert "/*" not in minified
    # Load-bearing selectors survive (rcssmin never rewrites them).
    assert ".canvas" in minified
    assert ".slide-element" in minified


def test_bundled_css_unminified_is_source_verbatim() -> None:
    # --- arrange ----------------------
    raw = files("scrolly.render").joinpath("assets", "canvas.css").read_text(encoding="utf-8")

    # --- act / assert -----------------
    assert bundled_assets.bundled_css(minify=False) == raw


def test_iter_assets_minifies_js_and_css() -> None:
    # --- act --------------------------
    minified = dict(bundled_assets.iter_assets())
    verbatim = dict(bundled_assets.iter_assets(minify=False))

    # --- assert -----------------------
    for name in ("canvas.js", "canvas.css"):
        assert len(minified[name]) < len(verbatim[name])
    assert b"// ----" not in minified["canvas.js"]
    assert b"// ----" in verbatim["canvas.js"]
    assert b"/*" not in minified["canvas.css"]
    assert b"/*" in verbatim["canvas.css"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_minified_js_is_valid_syntax(tmp_path: Path) -> None:
    # --- arrange ----------------------
    minified_file = tmp_path / "canvas.min.js"
    minified_file.write_text(bundled_assets.bundled_js())

    # --- act --------------------------
    result = subprocess.run(["node", "--check", str(minified_file)], capture_output=True, text=True)

    # --- assert -----------------------
    assert result.returncode == 0, result.stderr
