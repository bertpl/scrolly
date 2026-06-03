"""Exception hierarchy and numbered error-code framework for scrolly.

Numbered codes are for **author-facing** validation failures — anything
an author encounters while writing or building a deck. The author looks
the code up via ``scrolly errors <code>`` to get cause / example /
how-to-fix.

Two categories are deliberately **out** of the framework:

* **Internal invariants** — renderer bugs, registration conflicts,
  internal API contracts — raise plain ``ValueError`` / ``TypeError``
  instead. Tracebacks are the intended UX for programmer bugs;
  numbered codes would only invite the author to "fix" something that
  isn't theirs to fix. Do not retrofit codes onto internal assertions
  because "every error should have a code" — they shouldn't.
* **CLI invocation errors** — unknown ``--slide`` ids, out-of-range
  ``--scroll`` values, missing required options — surface as plain
  stderr messages with a non-zero exit code. They describe how the
  tool was invoked, not what's in the deck; numbering them would
  dilute the catalog from "deck content errors" into "every Click-level
  usage failure," which is the wrong category.

Module layout:
    _validation_error.py — ``ScrollyError`` base + ``ValidationError`` +
        the existing semantic subclasses (``DeckParseError``,
        ``DeckValidationError``, …) which inherit from ``ValidationError``.
    _codes.py            — catalog scan + ``is_registered_code`` predicate.
    _catalog.py          — markdown loader (``load_body``, ``load_summary``).
    _report.py           — ``ValidationReport`` accumulator.
    catalog/<code>.md    — one file per registered code (see the catalog
        package docstring for the phase-band numbering scheme).
"""

from scrolly.errors._codes import is_registered_code, registered_codes
from scrolly.errors._report import ValidationReport
from scrolly.errors._validation_error import (
    DeckInferenceError,
    DeckParseError,
    DeckValidationError,
    OutputError,
    ScrollyError,
    SlideSourceError,
    UnknownSlideTypeError,
    ValidationError,
)

__all__ = [
    "DeckInferenceError",
    "DeckParseError",
    "DeckValidationError",
    "OutputError",
    "ScrollyError",
    "SlideSourceError",
    "UnknownSlideTypeError",
    "ValidationError",
    "ValidationReport",
    "is_registered_code",
    "registered_codes",
]
