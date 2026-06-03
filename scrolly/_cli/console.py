"""Shared stderr console and error-reporting helpers for the CLI commands.

Every command surfaces failures the same way — a red ``error:`` line on a
stderr-only Rich console, followed (for terminal failures) by a non-zero
exit. Centralizing the console instance and that idiom here keeps the
formatting identical across ``build``, ``validate``, ``schema``,
``errors``, and the ``introspect`` subcommands.
"""

from __future__ import annotations

import sys
from typing import NoReturn

from rich.console import Console

err_console = Console(stderr=True, highlight=False)


def print_error(message: str) -> None:
    """Print a red ``error:`` line to stderr without exiting."""
    err_console.print(f"[red]error:[/red] {message}")


def error_exit(message: str) -> NoReturn:
    """Print a red ``error:`` line to stderr and exit non-zero."""
    print_error(message)
    sys.exit(1)
