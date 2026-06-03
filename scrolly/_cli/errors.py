"""``scrolly errors`` — look up registered error codes from the CLI.

Three forms, mirroring the progressive-disclosure pattern used by
``scrolly schema``:

* ``scrolly errors``              — formatted index of all codes with summaries.
* ``scrolly errors <code>``       — long-form catalog entry for ``<code>``.
* ``scrolly errors --list-codes`` — bare codes, one per line (scripting use).
"""

from __future__ import annotations

import click

from scrolly._cli.console import error_exit
from scrolly.errors import is_registered_code, registered_codes
from scrolly.errors._catalog import load_body, load_summary


@click.command(name="errors")
@click.argument("code", required=False)
@click.option(
    "--list-codes",
    "list_codes",
    is_flag=True,
    help="Print bare codes one per line (no summaries) for scripting use.",
)
def errors_command(code: str | None, list_codes: bool) -> None:
    """Look up registered error codes.

    \b
    scrolly errors              → formatted index of all codes with summaries
    scrolly errors <code>       → long-form catalog entry for <code>
    scrolly errors --list-codes → bare codes, one per line (agent / scripting)
    """
    if list_codes:
        for c in sorted(registered_codes()):
            click.echo(c)
        return

    if code is None:
        for c in sorted(registered_codes()):
            click.echo(f"  {c:<6}  {load_summary(c)}")
        return

    if not is_registered_code(code):
        error_exit(f"unknown error code '{code}'")

    click.echo(load_body(code))
