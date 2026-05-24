"""Exception hierarchy and numbered error-code framework for scrolly.

Numbered codes are for **author-facing** validation failures — anything
an author encounters while writing or building a deck. The author looks
the code up via ``scrolly errors <code>`` (or the v0.2.2+ docs site)
to get cause / example / how-to-fix.

Internal invariants — renderer bugs, registration conflicts, internal
API contracts — deliberately raise plain ``ValueError`` / ``TypeError``
instead of going through this framework. Tracebacks are the intended
UX for programmer bugs; numbered codes would only invite the author to
"fix" something that isn't theirs to fix. Do not retrofit codes onto
internal assertions because "every error should have a code" — they
shouldn't.

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
