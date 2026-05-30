import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { labelContrastColor } = require("../../scrolly/render/assets/canvas.js");

describe("labelContrastColor", () => {
  it("returns black on light and mid-tone backgrounds", () => {
    expect(labelContrastColor("#ffffff")).toBe("#000000");
    expect(labelContrastColor("#dcdcdc")).toBe("#000000"); // default group bg
    expect(labelContrastColor("#a8d8ea")).toBe("#000000"); // light pastel
    expect(labelContrastColor("#9DBAD2")).toBe("#000000"); // hero "Main Content" (lightest blue, lum 0.47 — black wins)
    expect(labelContrastColor("#9DD2BA")).toBe("#000000"); // hero "Details" (lightest green)
  });

  it("returns white on dark backgrounds", () => {
    expect(labelContrastColor("#000000")).toBe("#ffffff"); // pure black
    expect(labelContrastColor("#8B2F2F")).toBe("#ffffff"); // regression "Backdoor"
    expect(labelContrastColor("#4A6FA5")).toBe("#ffffff"); // hero "Introduction" / title blue
    expect(labelContrastColor("#3E7D5A")).toBe("#ffffff"); // dark green
  });

  it("accepts #RGB short form", () => {
    expect(labelContrastColor("#fff")).toBe("#000000");
    expect(labelContrastColor("#000")).toBe("#ffffff");
  });

  it("falls back to black on unparseable input", () => {
    expect(labelContrastColor("red")).toBe("#000000");
    expect(labelContrastColor("")).toBe("#000000");
    expect(labelContrastColor(null)).toBe("#000000");
    expect(labelContrastColor(undefined)).toBe("#000000");
  });
});
