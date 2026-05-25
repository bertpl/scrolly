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
