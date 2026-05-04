"""Exception hierarchy for scrolly.

`ScrollyError` is the base class for expected, user-facing failures — the CLI
catches it and renders a friendly message. Anything not inheriting from it
bubbles up as an unexpected error / bug.
"""


class ScrollyError(Exception):
    """Base class for expected, user-facing scrolly failures."""


class DeckParseError(ScrollyError):
    """Deck file could not be parsed (syntactic or shape error)."""


class DeckValidationError(ScrollyError):
    """Deck file is syntactically valid but violates a deck-level invariant."""


class DeckInferenceError(ScrollyError):
    """An edge's omitted side could not be inferred from slide positions."""


class SlideSourceError(ScrollyError):
    """A slide source file is missing, malformed, or invalid for its declared type."""


class UnknownSlideTypeError(ScrollyError):
    """A slide file declares a type that has no registered converter."""


class OutputError(ScrollyError):
    """Writing output files failed."""
