"""PayloadBundler — pools compressible inline payloads into one gzipped bundle.

Collects iframe srcdoc HTML and image-asset bytes into a deduplicated
list, gzip-compresses the concatenated stream once, and emits a single
JSON payload combining the manifest and the base64-encoded blob. The
result is consumed by the orchestrator and injected into the page as a
single ``<script type="application/json">`` block.

The bundler is instantiated whenever the build is producing an inlined
output (``inline=True``), regardless of whether compression was
requested — its :meth:`PayloadBundler.stats` snapshot drives the
help-screen statistics in every mode. Whether the bundle is actually
emitted into the page is a separate decision made by the orchestrator
based on the ``compress`` flag and the holistic 5% gate.
"""

from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass
from html import escape as html_escape
from typing import Literal

GZIP_LEVEL = 9
MIN_SAVING = 0.05


# ==================================================================================================
#  Value types
# ==================================================================================================
@dataclass(frozen=True)
class BundleStats:
    """Snapshot of what the bundler holds, with per-mime breakdowns.

    Always available via :meth:`PayloadBundler.stats` (independent of
    whether the bundle was emitted) and as the second element of
    :meth:`PayloadBundler.build`'s return tuple (when the gate passes).

    Counts are split into:

    - **target** counts (per ``add()`` call — pre-dedup, equals the number
      of DOM markers in the chunks);
    - **payload** counts (unique entries after dedup — what ends up in
      the bundle stream).

    Text-mode payloads (iframe srcdoc HTML) have no mime; they're
    counted separately as scalars. Blob-mode payloads are broken down
    per mime so the help screen can label them as SVG / PNG / etc.

    ``compressed`` is ``True`` only when the bundle was actually emitted
    (gate passed and the caller opted in to compression). When ``False``,
    ``compressed_bytes`` is ``0`` and so is ``bytes_saved``.
    """

    text_targets: int
    text_payloads: int
    blob_targets_by_mime: dict[str, int]
    blob_payloads_by_mime: dict[str, int]
    baseline_bytes: int
    compressed_bytes: int
    compressed: bool

    @property
    def total_targets(self) -> int:
        """Total target bindings across text and blob modes (pre-dedup)."""
        return self.text_targets + sum(self.blob_targets_by_mime.values())

    @property
    def total_payloads(self) -> int:
        """Total unique payloads across text and blob modes (post-dedup)."""
        return self.text_payloads + sum(self.blob_payloads_by_mime.values())

    @property
    def bytes_saved(self) -> int:
        """Bytes saved vs. plain inlining; zero when no bundle was emitted."""
        return self.baseline_bytes - self.compressed_bytes if self.compressed else 0


@dataclass(frozen=True)
class _Payload:
    """A unique compressible payload registered with the bundler."""

    payload: bytes
    mode: str
    mime: str | None


@dataclass(frozen=True)
class _Target:
    """A binding from a DOM target to a registered payload index."""

    target_id: str
    attr: str
    payload_index: int


# ==================================================================================================
#  Gate
# ==================================================================================================
def _gate_passes(compressed_len: int, baseline_len: int) -> bool:
    """Check whether the bundle clears the 5% holistic savings gate.

    Args:
        compressed_len: Length of the final JSON payload that would be
            emitted into the page (manifest + blob).
        baseline_len: Summed length of the inline forms that would
            otherwise be emitted (sum of ``baseline_len`` arguments
            passed to :meth:`PayloadBundler.add`).

    Returns:
        ``True`` when emitting the bundle would save at least 5% vs.
        plain inlining. The 95% boundary is inclusive — exactly 5%
        savings passes.
    """
    if baseline_len <= 0:
        return False
    return compressed_len <= baseline_len * (1.0 - MIN_SAVING)


# ==================================================================================================
#  PayloadBundler
# ==================================================================================================
class PayloadBundler:
    """Collects compressible inline payloads into a single gzipped bundle.

    Acts as a sink during slide rendering and asset rewriting (via
    :meth:`add`), and as a source during page assembly (via
    :meth:`build`). Dedups payloads with identical ``(mode, mime,
    bytes)`` so a deck reusing the same asset N times emits one payload
    entry referenced by N target bindings.

    A single bundler is instantiated per build and discarded when the
    page is written. Not thread-safe.
    """

    # --------------------------------------------------------
    #  Constructor
    # --------------------------------------------------------
    def __init__(self) -> None:
        """Initialise an empty bundler."""
        self._payloads: list[_Payload] = []
        self._targets: list[_Target] = []
        self._payload_dedup: dict[tuple[str, str | None, bytes], int] = {}
        self._next_target_id: int = 0
        self._baseline_total: int = 0

    # --------------------------------------------------------
    #  Public API — sink
    # --------------------------------------------------------
    def add(
        self,
        *,
        payload: bytes,
        mode: Literal["text", "blob"],
        attr: str,
        baseline_len: int,
        mime: str | None = None,
    ) -> str:
        """Register a payload + target binding with the bundle.

        Args:
            payload: Raw bytes to bundle. For ``mode="text"`` payloads,
                UTF-8 encoded source text; for ``mode="blob"`` payloads,
                the raw asset bytes.
            mode: How the JS will populate the DOM target from this
                payload — ``"text"`` (decoded UTF-8 string assigned to
                ``el[attr]``) or ``"blob"`` (Blob URL assigned to
                ``el[attr]``).
            attr: DOM attribute the JS will assign the decoded value to
                (e.g. ``"srcdoc"`` for iframes, ``"src"`` for images).
            baseline_len: Length of the inline form this binding would
                have produced without bundling (e.g.
                ``len(html_escape(srcdoc))`` for text,
                ``len(base64(raw_bytes))`` for blob). Summed across all
                ``add`` calls to evaluate the gate at build time.
            mime: Required when ``mode="blob"``; used as the ``Blob``
                type. Must be ``None`` when ``mode="text"``.

        Returns:
            An opaque target id (a stringified incrementing integer)
            that the caller must emit on the DOM element as
            ``data-scrolly-target="<id>"``. Distinct bindings sharing
            identical ``(mode, mime, payload)`` dedup to one entry in
            the payload list but each receive a unique target id.

        Raises:
            ValueError: If ``mode="blob"`` without ``mime``, or
                ``mode="text"`` with ``mime`` set.
        """
        if mode == "blob" and mime is None:
            raise ValueError('mime is required when mode="blob"')
        if mode == "text" and mime is not None:
            raise ValueError('mime must be None when mode="text"')

        key = (mode, mime, payload)
        payload_idx = self._payload_dedup.get(key)
        if payload_idx is None:
            payload_idx = len(self._payloads)
            self._payloads.append(_Payload(payload=payload, mode=mode, mime=mime))
            self._payload_dedup[key] = payload_idx

        target_id = str(self._next_target_id)
        self._next_target_id += 1
        self._targets.append(_Target(target_id=target_id, attr=attr, payload_index=payload_idx))

        self._baseline_total += baseline_len

        return target_id

    # --------------------------------------------------------
    #  Public API — source
    # --------------------------------------------------------
    def stats(self) -> BundleStats:
        """Snapshot the bundler's counts without building the bundle.

        Useful when the caller wants to populate stats UI without
        emitting (e.g. ``--no-compress`` builds, or a build whose gate
        fails). The returned ``BundleStats`` has ``compressed=False``
        and ``compressed_bytes=0``.

        Returns:
            A ``BundleStats`` reflecting the current ``add()``-call
            history. ``baseline_bytes`` is the running total. Per-mime
            breakdowns are populated.
        """
        return self._make_stats(compressed_bytes=0, compressed=False)

    def build(self) -> tuple[str, BundleStats] | None:
        """Build the combined JSON payload and evaluate the gate.

        Concatenates all unique payloads (in registration order) into
        one binary stream, gzip-compresses it once, base64-encodes the
        result, and packages it with the manifest into a single JSON
        object of the shape ``{"payloads": […], "targets": […],
        "blob": "…"}``. The gate then compares the emitted JSON's
        length to the summed inline baseline.

        Returns:
            Tuple of ``(compressed_payload_json, BundleStats)`` when
            the gate passes (``stats.compressed`` is ``True``), or
            ``None`` when it doesn't (no payloads registered, or
            insufficient savings). When ``None``, the caller should
            fall back to inline forms via :meth:`inline_fallback`.
        """
        if not self._payloads:
            return None

        stream = b"".join(p.payload for p in self._payloads)
        compressed = gzip.compress(stream, GZIP_LEVEL)
        blob_b64 = base64.b64encode(compressed).decode("ascii")

        manifest_obj = {
            "payloads": [_payload_entry(p) for p in self._payloads],
            "targets": [{"id": t.target_id, "attr": t.attr, "payload": t.payload_index} for t in self._targets],
            "blob": blob_b64,
        }
        compressed_json = json.dumps(manifest_obj, separators=(",", ":"))

        if not _gate_passes(len(compressed_json), self._baseline_total):
            return None

        return compressed_json, self._make_stats(
            compressed_bytes=len(compressed_json),
            compressed=True,
        )

    # --------------------------------------------------------
    #  Internal — stats construction
    # --------------------------------------------------------
    def _make_stats(self, *, compressed_bytes: int, compressed: bool) -> BundleStats:
        """Assemble a ``BundleStats`` from current internal state."""
        text_targets = 0
        text_payloads = 0
        blob_targets_by_mime: dict[str, int] = {}
        blob_payloads_by_mime: dict[str, int] = {}

        for payload in self._payloads:
            if payload.mode == "text":
                text_payloads += 1
            else:
                blob_payloads_by_mime[payload.mime] = blob_payloads_by_mime.get(payload.mime, 0) + 1

        for target in self._targets:
            payload = self._payloads[target.payload_index]
            if payload.mode == "text":
                text_targets += 1
            else:
                blob_targets_by_mime[payload.mime] = blob_targets_by_mime.get(payload.mime, 0) + 1

        return BundleStats(
            text_targets=text_targets,
            text_payloads=text_payloads,
            blob_targets_by_mime=blob_targets_by_mime,
            blob_payloads_by_mime=blob_payloads_by_mime,
            baseline_bytes=self._baseline_total,
            compressed_bytes=compressed_bytes,
            compressed=compressed,
        )

    def inline_fallback(self) -> dict[str, str]:
        """Return per-target inline-attribute substitutes.

        Used by the orchestrator when :meth:`build` returns ``None``:
        each ``data-scrolly-target="<id>"`` marker in the chunk HTML is
        replaced with the corresponding ``<attr>="<value>"`` substitute,
        restoring the uncompressed v0.1.12-equivalent output for that
        target.

        Returns:
            Dict mapping target id to a fully-formed attribute fragment
            (e.g. ``'srcdoc="&lt;p&gt;…&lt;/p&gt;"'`` or
            ``'src="data:image/svg+xml;base64,…"'``).
        """
        result: dict[str, str] = {}
        for target in self._targets:
            payload = self._payloads[target.payload_index]
            if payload.mode == "text":
                escaped = html_escape(payload.payload.decode("utf-8"))
                result[target.target_id] = f'{target.attr}="{escaped}"'
            else:
                encoded = base64.b64encode(payload.payload).decode("ascii")
                result[target.target_id] = f'{target.attr}="data:{payload.mime};base64,{encoded}"'
        return result


# ==================================================================================================
#  Helpers
# ==================================================================================================
def _payload_entry(p: _Payload) -> dict:
    """Build the manifest entry for a payload with stable field order."""
    if p.mime is not None:
        return {"mode": p.mode, "mime": p.mime, "length": len(p.payload)}
    return {"mode": p.mode, "length": len(p.payload)}
