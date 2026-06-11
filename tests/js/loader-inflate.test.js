import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const { inflate } = require("../../scrolly/render/assets/loader.js");

// Build a synthetic blob the way the Python bootstrap builder would:
// document bytes + asset bytes in one gzip stream, base64-encoded.
function _packBlob(docText, assetBytes) {
  const docBytes = Buffer.from(docText, "utf-8");
  const blob = Buffer.from(gzipSync(Buffer.concat([docBytes, assetBytes]))).toString("base64");
  return { blob, docLength: docBytes.length };
}

describe("loader inflate", () => {
  it("round-trips a document with no asset bytes", async () => {
    // --- arrange ---------------------------
    const docText = "<!DOCTYPE html><html><body><p>inner</p></body></html>";
    const { blob, docLength } = _packBlob(docText, Buffer.alloc(0));

    // --- act -------------------------------
    const result = await inflate(blob, docLength);

    // --- assert ----------------------------
    expect(result.html).toBe(docText);
    expect(result.payloadBytes.length).toBe(0);
  });

  it("splits document text from asset bytes at docLength", async () => {
    // --- arrange ---------------------------
    const docText = "<html><body>doc with ünïcödé</body></html>";
    const assets = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0, 1, 2, 255]);
    const { blob, docLength } = _packBlob(docText, assets);

    // --- act -------------------------------
    const result = await inflate(blob, docLength);

    // --- assert ----------------------------
    expect(result.html).toBe(docText);
    expect(Buffer.from(result.payloadBytes).equals(assets)).toBe(true);
  });

  it("handles a large highly-repetitive document", async () => {
    // --- arrange ---------------------------
    const docText = "<div class='slide'>repetitive slide markup</div>".repeat(5000);
    const { blob, docLength } = _packBlob(docText, Buffer.alloc(0));

    // --- act -------------------------------
    const result = await inflate(blob, docLength);

    // --- assert ----------------------------
    expect(result.html).toBe(docText);
  });
});
