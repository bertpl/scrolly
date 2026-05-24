"""Registry of declared error codes — backed by the ``catalog/`` directory.

The catalog directory is the canonical source of truth for "which codes
exist". This module scans it once on first access, caches the result,
and exposes a single ``is_registered_code()`` predicate that the
``ValidationError`` constructor consults to reject undeclared codes.

Catalog parity is enforced in two directions:

* Emit-side: ``ValidationError(code=...)`` rejects any code without a
  matching ``<code>.md`` file (raised at construction time, so the
  failure surfaces in tests as soon as any code path that emits the
  unknown code runs).
* Catalog-side: a round-trip test in ``tests/python/errors/`` walks
  the catalog and asserts every declared code is referenced at least
  once from an emit site, so the catalog cannot accumulate orphan
  entries.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

CODE_PATTERN = re.compile(r"^E\d{3,}$")


@lru_cache(maxsize=1)
def registered_codes() -> frozenset[str]:
    """Return the set of codes declared in ``scrolly/errors/catalog/``.

    Computed once and cached for the process lifetime; the catalog is
    shipped with the wheel and does not change at runtime.

    Returns:
        Frozen set of code strings (e.g. ``{"E001", "E002", ...}``).
    """
    catalog_dir = files("scrolly.errors.catalog")
    codes: set[str] = set()
    for entry in catalog_dir.iterdir():
        name = entry.name
        if not name.endswith(".md"):
            continue
        code = name[:-3]
        if not CODE_PATTERN.match(code):
            raise ValueError(f"catalog entry '{name}' does not match expected pattern E<digits>.md (e.g. E001.md)")
        codes.add(code)
    return frozenset(codes)


def is_registered_code(code: str) -> bool:
    """Return True if ``code`` has a matching catalog entry."""
    return code in registered_codes()
