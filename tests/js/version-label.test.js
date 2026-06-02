import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { resolveVersionLabel } = require("../../scrolly/render/assets/canvas.js");

// resolveVersionLabel builds the " vX.Y.Z" fragment after "scrolly" in the
// help About panel. The first argument is the `scrolly-version` URL override
// (null when the param is absent); the second is the built-in deck version.
describe("resolveVersionLabel", () => {
  it("shows the built-in version when no override is present", () => {
    expect(resolveVersionLabel(null, "0.2.3")).toBe(" v0.2.3");
  });

  it("hides the version when the override is an empty string", () => {
    expect(resolveVersionLabel("", "0.2.3")).toBe("");
  });

  it("uses a non-empty override in place of the built-in version", () => {
    expect(resolveVersionLabel("0.2.4", "0.2.3")).toBe(" v0.2.4");
  });

  it("shows nothing when there is no version at all", () => {
    expect(resolveVersionLabel(null, "")).toBe("");
  });
});
