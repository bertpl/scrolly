"""Accumulator for ``ValidationError`` instances.

Validators that want to surface every problem at once (rather than
fail-fast on the first) collect them into a ``ValidationReport`` and
hand it to a downstream consumer (CLI, introspection command, …) which
decides how to render. Today's pipeline still raises on first error;
the report exists for callers that need batched validation.
"""

from __future__ import annotations

from scrolly.errors._validation_error import ValidationError


class ValidationReport:
    """Append-only accumulator for ``ValidationError`` instances.

    Methods:
        add: Append a single error.
        errors: Defensive-copy tuple of all accumulated errors.
        is_clean: True iff no errors have been added.
    """

    def __init__(self) -> None:
        self._errors: list[ValidationError] = []

    def add(self, error: ValidationError) -> None:
        """Append ``error`` to the report."""
        self._errors.append(error)

    @property
    def errors(self) -> tuple[ValidationError, ...]:
        """Return all accumulated errors as a defensive-copy tuple."""
        return tuple(self._errors)

    def is_clean(self) -> bool:
        """Return True iff no errors have been added."""
        return not self._errors

    def __len__(self) -> int:
        return len(self._errors)
