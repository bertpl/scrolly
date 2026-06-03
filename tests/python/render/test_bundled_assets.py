"""Tests for the mermaid resolution chain in `scrolly.render.bundled_assets`."""

from __future__ import annotations

import urllib.error
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
