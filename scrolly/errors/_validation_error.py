"""Numbered, author-facing validation error.

``ValidationError`` is the base for every author-facing failure that
carries a catalog code. The constructor enforces catalog membership:
emit sites cannot use codes that don't have a matching ``<code>.md``
entry, so the catalog and the code base stay in lockstep.

Internal invariants (renderer bugs, registration conflicts, etc.) do
**not** subclass this — they raise plain ``ValueError`` / ``TypeError``
so that programmer bugs surface as Python tracebacks rather than as
numbered codes the author would try to look up. See the package
docstring for the full rationale.
"""

from __future__ import annotations

from scrolly.errors._codes import is_registered_code


class ScrollyError(Exception):
    """Base class for expected, user-facing scrolly failures.

    The CLI catches this and renders a friendly message; anything not
    inheriting from it bubbles as an unexpected error / bug.
    """


class ValidationError(ScrollyError):
    """Author-facing validation error with a registered catalog code.

    The code's matching ``scrolly/errors/catalog/<code>.md`` entry is
    the canonical reference for what the code means and how to fix it;
    authors look it up via ``scrolly errors <code>``.

    Default text rendering is ``[file:line:] [code] [field:] message``.
    Each bracketed segment is omitted when its field is ``None``.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        file: str | None = None,
        line: int | None = None,
        field: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        if not is_registered_code(code):
            raise ValueError(
                f"unknown error code '{code}' — every emitted code must have a "
                f"matching <code>.md entry in scrolly/errors/catalog/"
            )
        self.code = code
        self.message = message
        self.file = file
        self.line = line
        self.field = field
        self.suggestion = suggestion
        super().__init__(self._render())

    def _render(self) -> str:
        """Render the error as ``[file:line:] [code] [field:] message``."""
        parts: list[str] = []
        if self.file:
            loc = self.file if self.line is None else f"{self.file}:{self.line}"
            parts.append(f"{loc}:")
        parts.append(f"[{self.code}]")
        if self.field:
            parts.append(f"{self.field}:")
        parts.append(self.message)
        return " ".join(parts)


class DeckParseError(ValidationError):
    """Deck or slide file could not be parsed (syntactic or schema error)."""


class DeckValidationError(ValidationError):
    """Deck file is syntactically valid but violates a deck-level invariant."""


class DeckInferenceError(ValidationError):
    """An edge's omitted side could not be inferred from slide positions."""


class SlideSourceError(ValidationError):
    """A slide source file is missing, malformed, or invalid for its declared type."""


class UnknownSlideTypeError(ValidationError):
    """A slide file declares a type that has no registered converter."""


class OutputError(ValidationError):
    """Writing output files failed."""
