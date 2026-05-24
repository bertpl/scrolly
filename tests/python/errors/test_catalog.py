"""Catalog round-trip + framework smoke tests.

Two parity invariants enforced here:

* **Every registered code must be raised by at least one site.** A
  ``code=...`` value that appears in no source file is an orphan
  catalog entry — author docs without a corresponding emit path. The
  test walks every ``.py`` under ``scrolly/`` for ``code="EXXX"`` /
  ``code='EXXX'`` literals and asserts the union covers every code
  declared in ``scrolly/errors/catalog/``.

* **Every emitted code must be in the catalog.** Enforced at runtime
  by ``ValidationError.__init__`` (which rejects unknown codes via
  ``is_registered_code``), so any code path that constructs a
  ``ValidationError(code=...)`` with a missing ``<code>.md`` raises
  immediately. The unit test below pins that behaviour for the
  framework.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scrolly.errors import ValidationError, registered_codes

SCROLLY_ROOT = Path(__file__).resolve().parents[3] / "scrolly"

# Match either single- or double-quoted ``code="EXXX"`` / ``code='EXXX'``
# literals in source files; catches every emit site that constructs a
# ValidationError (or subclass) with a kwarg.
_EMIT_PATTERN = re.compile(r"""code\s*=\s*["'](E\d+)["']""")


def _collect_emitted_codes() -> set[str]:
    """Scan ``scrolly/`` for ``code="EXXX"`` literals.

    Returns:
        Set of all error codes referenced from emit sites under
        ``scrolly/`` (excluding ``scrolly/errors/`` itself, which is
        the framework, not an emit site).
    """
    emitted: set[str] = set()
    for path in SCROLLY_ROOT.rglob("*.py"):
        # Skip the errors framework itself — its self-references are
        # docstrings, not emit sites.
        if "errors" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        emitted.update(_EMIT_PATTERN.findall(text))
    return emitted


def test_every_catalog_entry_has_an_emit_site() -> None:
    """Every ``<code>.md`` in the catalog must be raised by at least one site."""
    # --- arrange ----------------------
    declared = registered_codes()
    emitted = _collect_emitted_codes()

    # --- act / assert -----------------
    orphans = declared - emitted
    assert not orphans, (
        f"catalog entries with no emit site: {sorted(orphans)}. Either remove the entry or wire it from a raise call."
    )


def test_every_emitted_code_is_in_the_catalog() -> None:
    """Every ``code="EXXX"`` literal in scrolly/ must resolve to a catalog entry."""
    # --- arrange ----------------------
    declared = registered_codes()
    emitted = _collect_emitted_codes()

    # --- act / assert -----------------
    undeclared = emitted - declared
    assert not undeclared, (
        f"emit sites use codes with no catalog entry: {sorted(undeclared)}. "
        f"Add a `<code>.md` file under scrolly/errors/catalog/ for each."
    )


def test_validation_error_rejects_unregistered_code() -> None:
    """Constructing a ``ValidationError`` with an unknown code raises ``ValueError``."""
    # --- arrange / act / assert -------
    with pytest.raises(ValueError, match="unknown error code 'E9999'"):
        ValidationError(code="E9999", message="should not construct")


def test_validation_error_render_with_all_fields() -> None:
    """``str(err)`` formats as ``file:line: [code] field: message`` when all fields are set."""
    # --- arrange ----------------------
    err = ValidationError(
        code="E001",
        message="could not parse JSON5",
        file="deck.deck.json",
        line=12,
        field="slides",
    )

    # --- act --------------------------
    rendered = str(err)

    # --- assert -----------------------
    assert rendered == "deck.deck.json:12: [E001] slides: could not parse JSON5"


def test_validation_error_render_with_minimal_fields() -> None:
    """``str(err)`` omits optional segments when their fields are None."""
    # --- arrange ----------------------
    err = ValidationError(code="E001", message="something failed")

    # --- act --------------------------
    rendered = str(err)

    # --- assert -----------------------
    assert rendered == "[E001] something failed"
