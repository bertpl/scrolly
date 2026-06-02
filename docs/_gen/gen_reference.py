"""``mkdocs-gen-files`` entry point for the auto-generated reference.

Run in-process during ``mkdocs build`` (Mechanism B), so local and Read
the Docs builds produce identical output. Writes the element-schema and
error-code reference pages plus their literate-nav ``SUMMARY.md`` files,
all derived from the installed scrolly — delete a generated page and it
reappears on the next build. The CLI reference is handled separately by
the ``mkdocs-click`` directive in ``reference/cli.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mkdocs_gen_files  # noqa: E402
import reference_content as rc  # noqa: E402

# --- file schemas -----------------------------------
with mkdocs_gen_files.open("reference/files/index.md", "w") as f:
    f.write(rc.file_index_page())
for _key in rc.file_schema_keys():
    with mkdocs_gen_files.open(f"reference/files/{_key}.md", "w") as f:
        f.write(rc.file_schema_page(_key))

# --- element schemas --------------------------------
with mkdocs_gen_files.open("reference/elements/index.md", "w") as f:
    f.write(rc.element_index_page())
for _key in rc.element_keys():
    with mkdocs_gen_files.open(f"reference/elements/{_key}.md", "w") as f:
        f.write(rc.element_page(_key))

# --- error codes ------------------------------------
with mkdocs_gen_files.open("reference/errors/index.md", "w") as f:
    f.write(rc.error_index_page())
for _code in rc.error_codes():
    with mkdocs_gen_files.open(f"reference/errors/{_code}.md", "w") as f:
        f.write(rc.error_page(_code))

# --- nav (one literate-nav file for the whole Reference section) ---
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as f:
    f.write(rc.reference_summary())
