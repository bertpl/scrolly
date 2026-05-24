"""``scrolly introspect <sub>`` — build-time introspection of a resolved deck.

Each subcommand surfaces some aspect of what the renderer / browser will
see, scoped to the agent's biggest blind spot: visual output is unreadable
to a non-browser consumer, so introspection commands close the loop by
returning structured JSON describing the deck's resolved state.

Common conventions enforced via ``_common.run_introspect_command``:

* **JSON-only output**, default to stdout, ``-o PATH`` for a file
  destination.
* **Validation gate first** — broken decks emit error messages to stderr
  and exit non-zero with no JSON, so consumers never parse stale state.
* **``--slide <id>``** (repeatable) on subcommands that produce per-slide
  output, restricting the result to the named slides. Unknown ids exit
  non-zero with a clear message.

Output format may change before scrolly v1.0 — pin a version when caching
the schema.
"""

from __future__ import annotations

import click

from scrolly._cli._introspect._assets import assets_command
from scrolly._cli._introspect._elements import elements_command
from scrolly._cli._introspect._slides import slides_command
from scrolly._cli._introspect._snaps import snaps_command
from scrolly._cli._introspect._snapshot import snapshot_command
from scrolly._cli._introspect._timeline import timeline_command


@click.group(name="introspect")
def introspect() -> None:
    """Inspect a resolved deck — JSON-only views for downstream consumers."""


introspect.add_command(slides_command)
introspect.add_command(elements_command)
introspect.add_command(snaps_command)
introspect.add_command(timeline_command)
introspect.add_command(snapshot_command)
introspect.add_command(assets_command)
