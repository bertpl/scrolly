/*
 * scrolly bootstrap loader — inflates the compressed document.
 *
 * The only JavaScript shipped in plain text on a compressed build. The
 * page it lives in is a minimal black bootstrap document whose body
 * holds one base64 blob (`#scrolly-document`): a single gzip stream of
 * the full inner HTML document followed by the raw asset payload bytes.
 * The block's `data-doc-length` attribute says where the document ends
 * and the asset bytes begin.
 *
 * The loader base64-decodes the blob, inflates it with
 * DecompressionStream("gzip"), stashes the asset remainder on
 * `window.__scrollyPayloadBytes` (the window object survives a
 * document.open/write/close cycle, so this is the hand-off to
 * canvas.js's payload populator), and replaces the document via
 * document.write — which re-runs the parser, so the inner document's
 * scripts execute natively and in order.
 *
 * Must stay dependency-free and small: it pays full plain-text price in
 * every compressed build. Failure paths (no DecompressionStream, a
 * corrupt blob) replace the black screen with a readable message —
 * there is no degraded-but-working mode once the whole document lives
 * in the blob.
 */
(function (exports) {
  // ---- inflate (pure — no DOM access) ----------------------------------------
  //
  // base64 → gunzip → split at docLength. Returns { html, payloadBytes }.
  // Pure so Vitest can round-trip it against synthetic gzip streams.
  async function inflate(b64, docLength) {
    const gz = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const buf = new Uint8Array(
      await new Response(
        new Blob([gz]).stream().pipeThrough(new DecompressionStream("gzip"))
      ).arrayBuffer()
    );
    return {
      html: new TextDecoder().decode(buf.subarray(0, docLength)),
      payloadBytes: buf.subarray(docLength),
    };
  }

  if (typeof exports !== "undefined") {
    exports.inflate = inflate;
  }

  // ---- DOM boot (skipped in Node.js) ------------------------------------------

  if (typeof document === "undefined") return;

  function fail(message) {
    document.body.innerHTML =
      '<p style="color: #fff; font-family: sans-serif; padding: 2rem;">' + message + "</p>";
  }

  (async function () {
    if (!("DecompressionStream" in window)) {
      fail(
        "This presentation needs a browser with DecompressionStream support " +
          "(Chrome/Edge 80+, Firefox 113+, Safari 16.4+)."
      );
      return;
    }
    const block = document.getElementById("scrolly-document");
    try {
      const result = await inflate(block.textContent, Number(block.dataset.docLength));
      window.__scrollyPayloadBytes = result.payloadBytes;
      document.open();
      document.write(result.html);
      document.close();
    } catch (err) {
      console.error("scrolly: failed to unpack the compressed document", err);
      fail("Failed to unpack this presentation: " + err);
    }
  })();
})(typeof module !== "undefined" ? module.exports : {});
