import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const { decompressBundle } = require("../../scrolly/render/assets/canvas.js");

// Build a synthetic compressed-payload JSON string the way the Python
// PayloadBundler would: concatenate raw payload bytes, gzip, base64.
function _packBundle({ payloads, targets }) {
  // Each payload entry carries { mode, length, mime? } and `bytes`.
  const stream = Buffer.concat(payloads.map((p) => p.bytes));
  const blob = Buffer.from(gzipSync(stream)).toString("base64");
  const manifestPayloads = payloads.map((p) => {
    const entry = { mode: p.mode, length: p.bytes.length };
    if (p.mime) entry.mime = p.mime;
    return entry;
  });
  return JSON.stringify({ payloads: manifestPayloads, targets, blob });
}

describe("decompressBundle", () => {
  it("decodes a single text payload into one Assignment", async () => {
    // --- arrange ---------------------------
    const scriptText = _packBundle({
      payloads: [{ mode: "text", bytes: Buffer.from("<p>hello</p>", "utf-8") }],
      targets: [{ id: "0", attr: "srcdoc", payload: 0 }],
    });

    // --- act -------------------------------
    const assignments = await decompressBundle(scriptText);

    // --- assert ----------------------------
    expect(assignments).toHaveLength(1);
    expect(assignments[0]).toEqual({
      target_id: "0",
      attr: "srcdoc",
      mode: "text",
      text: "<p>hello</p>",
    });
  });

  it("decodes a blob payload with mime", async () => {
    // --- arrange ---------------------------
    const svgBytes = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"/>', "utf-8");
    const scriptText = _packBundle({
      payloads: [{ mode: "blob", mime: "image/svg+xml", bytes: svgBytes }],
      targets: [{ id: "0", attr: "src", payload: 0 }],
    });

    // --- act -------------------------------
    const assignments = await decompressBundle(scriptText);

    // --- assert ----------------------------
    expect(assignments).toHaveLength(1);
    expect(assignments[0].target_id).toBe("0");
    expect(assignments[0].attr).toBe("src");
    expect(assignments[0].mode).toBe("blob");
    expect(assignments[0].mime).toBe("image/svg+xml");
    expect(Buffer.from(assignments[0].bytes).equals(svgBytes)).toBe(true);
  });

  it("decodes a mixed bundle with one dedup'd target", async () => {
    // --- arrange ---------------------------
    // Two text targets sharing one payload, plus one blob target.
    const sharedText = Buffer.from("<p>shared</p>", "utf-8");
    const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);
    const scriptText = _packBundle({
      payloads: [
        { mode: "text", bytes: sharedText },
        { mode: "blob", mime: "image/png", bytes: png },
      ],
      targets: [
        { id: "0", attr: "srcdoc", payload: 0 },
        { id: "1", attr: "srcdoc", payload: 0 },
        { id: "2", attr: "src", payload: 1 },
      ],
    });

    // --- act -------------------------------
    const assignments = await decompressBundle(scriptText);

    // --- assert ----------------------------
    expect(assignments).toHaveLength(3);
    expect(assignments[0].text).toBe("<p>shared</p>");
    expect(assignments[1].text).toBe("<p>shared</p>");
    expect(assignments[2].mode).toBe("blob");
    expect(assignments[2].mime).toBe("image/png");
    expect(Buffer.from(assignments[2].bytes).equals(png)).toBe(true);
  });

  it("slices the decompressed stream correctly per manifest length", async () => {
    // --- arrange ---------------------------
    const a = Buffer.from("alpha", "utf-8");
    const b = Buffer.from("bravo bravo bravo", "utf-8");
    const c = Buffer.from("c", "utf-8");
    const scriptText = _packBundle({
      payloads: [
        { mode: "text", bytes: a },
        { mode: "text", bytes: b },
        { mode: "text", bytes: c },
      ],
      targets: [
        { id: "0", attr: "srcdoc", payload: 0 },
        { id: "1", attr: "srcdoc", payload: 1 },
        { id: "2", attr: "srcdoc", payload: 2 },
      ],
    });

    // --- act -------------------------------
    const assignments = await decompressBundle(scriptText);

    // --- assert ----------------------------
    expect(assignments[0].text).toBe("alpha");
    expect(assignments[1].text).toBe("bravo bravo bravo");
    expect(assignments[2].text).toBe("c");
  });
});
