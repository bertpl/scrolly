from pathlib import Path

import pytest


def _find_project_root() -> Path:
    d = Path(__file__).resolve().parent
    while d != d.parent:
        if (d / "pyproject.toml").exists():
            return d
        d = d.parent
    raise RuntimeError("Could not find project root (no pyproject.toml in ancestors)")


PROJECT_ROOT = _find_project_root()


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(autouse=True)
def _force_offline_mermaid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default every test to ``SCROLLY_OFFLINE=1``.

    Tests run deterministic + offline — no jsdelivr requests during a
    normal ``pytest`` run. Specific tests that want to exercise the
    CDN path can clear the env var with
    ``monkeypatch.delenv("SCROLLY_OFFLINE", raising=False)`` and
    monkeypatch ``urllib.request.urlopen`` to return controlled bytes.
    """
    monkeypatch.setenv("SCROLLY_OFFLINE", "1")


def inflate_compressed_page(html: str) -> str:
    """Inflate a compressed bootstrap page back to its inner document.

    Returns ``html`` unchanged when it isn't a compressed page (plain
    and ``--no-compress`` builds), so assertions on document content
    work against either build flavor.
    """
    doc, _ = inflate_compressed_stream(html)
    return doc


def inflate_compressed_stream(html: str) -> tuple[str, bytes]:
    """Split a compressed page into (inner document, asset payload bytes).

    Returns ``(html, b"")`` for plain pages.
    """
    import base64
    import gzip
    import re

    match = re.search(
        r'<script type="application/octet-stream" id="scrolly-document" data-doc-length="(\d+)">([^<]*)</script>',
        html,
    )
    if match is None:
        return html, b""
    doc_length = int(match.group(1))
    buf = gzip.decompress(base64.b64decode(match.group(2)))
    return buf[:doc_length].decode("utf-8"), buf[doc_length:]
