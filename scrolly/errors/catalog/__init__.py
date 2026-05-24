"""Catalog of registered scrolly error codes — one ``<code>.md`` per code.

Codes follow the pattern ``E<digits>`` (3+ digits), grouped into
phase-banded numbering so the band of a code communicates *where* in
the pipeline the failure was detected:

* **E0xx** — Parse / file-level syntax (JSON5 parsing, manual deck-shape
  checks, slide-source loading).
* **E1xx** — Deck-schema invariants on the parsed object (uniqueness,
  grid geometry, edge/group structure).
* **E2xx** — Slide-schema validation (``SlideIR`` field constraints,
  custom ``@model_validator`` checks). E299 is the umbrella for any
  Pydantic-internal ``ValidationError`` raised while loading a
  ``.slide.json`` — covering both slide-level and element-level
  type/shape failures.
* **E3xx** — Element-schema validation (per-element custom validators
  on ``SlideElement`` subtypes + animated keyframes). Pydantic-internal
  failures at the element level fall under E299, not here — E3xx is
  exclusively for our hand-written ``@model_validator`` checks.
* **E4xx** — Asset resolution (missing asset files, invalid filenames,
  unsupported formats).
* **E5xx** — Cross-reference (slide refs in deck → declared slides,
  edge endpoints → real slides, group members → declared, slide source
  files missing or with unknown suffix).
* **E6xx** — Element compile (no compiler/renderer registered for an
  IR type, conversion cycles, missing slide renderer).
* **E7xx** — Output (writer-side failures: output path is not a
  directory, output directory non-empty without ``--force``).

Higher bands are reserved for future categories.
"""
