"""Loader for catalog markdown entries.

Each catalog file is a small markdown document with a heading + Cause /
Example / How to fix sections. This module exposes two reads:

* ``load_summary(code)`` — the one-line title after the ``# E... -``
  heading, used by the ``scrolly errors`` index view.
* ``load_body(code)`` — the full markdown body, used by
  ``scrolly errors <code>`` for the long-form catalog entry.
"""

from __future__ import annotations

from importlib.resources import files

from scrolly.errors._codes import is_registered_code


def load_body(code: str) -> str:
    """Return the full markdown body for ``code``.

    Args:
        code: The error code (e.g. ``"E001"``).

    Returns:
        The markdown file contents as a string.

    Raises:
        ValueError: If the code is not registered in the catalog.
    """
    if not is_registered_code(code):
        raise ValueError(f"unknown error code '{code}'")
    return files("scrolly.errors.catalog").joinpath(f"{code}.md").read_text(encoding="utf-8")


def load_summary(code: str) -> str:
    """Return the one-line summary from the catalog entry's heading.

    Reads the first non-empty line of the entry, expected to be of the
    form ``# E<digits> - <summary text>``, and returns just the summary
    text. Falls back to the bare code if the heading is malformed.

    Args:
        code: The error code (e.g. ``"E001"``).

    Returns:
        The summary text without the leading code or hyphen.

    Raises:
        ValueError: If the code is not registered in the catalog.
    """
    body = load_body(code)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Expected: "# <code> - <summary>"
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if " - " in heading:
                return heading.split(" - ", 1)[1].strip()
            return heading
        break
    return code
