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
