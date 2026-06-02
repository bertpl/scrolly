"""MkDocs build hooks for the docs site.

Keeps the generated literate-nav ``SUMMARY.md`` out of the built site.
literate-nav reads ``reference/SUMMARY.md`` to assemble the Reference
nav but only marks it ``NOT_IN_NAV`` (still built, still searchable);
core ``exclude_docs`` runs too early to catch a gen-files-generated
file. This hook runs after literate-nav and drops it from the build so
it isn't an orphan URL or search hit.
"""

from __future__ import annotations

from mkdocs.plugins import event_priority
from mkdocs.structure.files import Files, InclusionLevel


@event_priority(-200)  # after gen-files (creates it) and literate-nav (reads it)
def on_files(files: Files, config: object) -> Files:
    """Exclude the generated reference nav file from the built site."""
    nav_file = files.get_file_from_path("reference/SUMMARY.md")
    if nav_file is not None:
        nav_file.inclusion = InclusionLevel.EXCLUDED
    return files
