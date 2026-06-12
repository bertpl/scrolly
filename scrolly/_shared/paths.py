"""Deck-root path confinement for authored file references.

Every file an authored source references — ``*_file`` content fields,
``container_file`` includes, image assets, slide ``source:`` entries —
must be a relative path whose resolved target stays inside the deck
root (the ``.deck.json`` directory). ``..`` and symlink escapes are
both rejected: symlinks arrive via untrusted git clones and archives,
so they are not reliable user intent. The person running the build can
whitelist additional roots explicitly (``--allow-path``); deck content
and filesystem state cannot.

Confinement is activated as a context (``confine_paths``) by the deck
loader. Outside the context — direct API use, unit tests of individual
models — ``resolve_reference`` degrades to a plain join, preserving
historical behavior.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from scrolly.errors import SlideSourceError

_CONFINEMENT: ContextVar[tuple[Path, ...] | None] = ContextVar("scrolly_path_confinement", default=None)


@contextmanager
def confine_paths(root: Path, extra_roots: Sequence[Path] = ()) -> Iterator[None]:
    """Activate path confinement to ``root`` (plus ``extra_roots``) for the duration."""
    roots = (root.resolve(), *(r.resolve() for r in extra_roots))
    token = _CONFINEMENT.set(roots)
    try:
        yield
    finally:
        _CONFINEMENT.reset(token)


def resolve_reference(authored: str | Path, base_dir: Path, *, what: str) -> Path:
    """Resolve an authored file reference against ``base_dir``, enforcing confinement.

    Args:
        authored: The path exactly as written in the source file.
        base_dir: Directory of the file the reference appears in.
        what: Reference kind for error messages (e.g. ``"markdown_file"``).

    Returns:
        The joined path (confinement inactive) or the fully resolved
        path (confinement active).

    Raises:
        SlideSourceError: ``E506`` when confinement is active and the
            path is absolute or its resolved target escapes every
            allowed root.
    """
    roots = _CONFINEMENT.get()
    if roots is None:
        return base_dir / authored

    authored_path = Path(authored)
    if authored_path.is_absolute():
        raise SlideSourceError(
            code="E506",
            message=f"{what} path must be relative, got absolute path: {authored_path}",
        )
    resolved = (base_dir / authored_path).resolve()
    if not any(resolved.is_relative_to(root) for root in roots):
        raise SlideSourceError(
            code="E506",
            message=(
                f"{what} path escapes the deck root: {authored!s} resolves to {resolved}. "
                f"Move the file inside the deck directory, or whitelist its root "
                f"explicitly with --allow-path."
            ),
        )
    return resolved
