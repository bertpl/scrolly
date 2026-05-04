"""Base class for all slide IR models.

Each ``SlideIR`` subclass *is* a slide type: it declares a filename
suffix, carries the validated data model, and provides a ``from_file``
factory classmethod that parses a source file into a validated instance.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel


class SlideIR(BaseModel, frozen=True):
    """Base for all slide IR models."""

    SUFFIX: ClassVar[str]
    DESCRIPTION: ClassVar[str]

    @property
    def slide_type(self) -> str:
        """CSS-safe type name derived from SUFFIX."""
        return self.SUFFIX.lstrip(".").replace(".", "-")

    @classmethod
    def source_schema(cls) -> dict:
        """Return a JSON-serialisable description of the source file format."""
        return cls.model_json_schema()

    @classmethod
    @abc.abstractmethod
    def from_file(cls, source_path: Path) -> Self: ...
