import { describe, it, expect, vi } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { buildAutomationHook } = require("../../scrolly/render/assets/canvas.js");

// Build a hook with stub dependencies. Tests inject vi.fn() spies via
// `viewStateSpies` / `scrollManagerSpies` so each test asserts against the
// exact call shape the factory produced. `selectedSlide` defaults to a
// non-empty id so setScroll() exercises a realistic call path.
function _hook({ selectedSlide = "intro", isAnimating = () => false } = {}) {
  const viewState = { selectedSlide, setView: vi.fn() };
  const scrollManager = { setPosition: vi.fn() };
  const hook = buildAutomationHook({ viewState, scrollManager, isAnimating });
  return { hook, viewState, scrollManager };
}

describe("buildAutomationHook", () => {
  // ---- API surface --------------------------------------------------------

  it("exposes exactly four methods", () => {
    // --- arrange ---------------------------
    const { hook } = _hook();

    // --- act / assert ----------------------
    expect(Object.keys(hook).sort()).toEqual(
      ["isAnimating", "selectSlide", "setScroll", "setView"],
    );
    expect(typeof hook.selectSlide).toBe("function");
    expect(typeof hook.setView).toBe("function");
    expect(typeof hook.setScroll).toBe("function");
    expect(typeof hook.isAnimating).toBe("function");
  });

  // ---- selectSlide --------------------------------------------------------

  it("selectSlide routes through viewState.setView with the new slide id", () => {
    // --- arrange ---------------------------
    const { hook, viewState } = _hook();

    // --- act -------------------------------
    hook.selectSlide("conclusion");

    // --- assert ----------------------------
    expect(viewState.setView).toHaveBeenCalledTimes(1);
    expect(viewState.setView).toHaveBeenCalledWith({ selectedSlide: "conclusion" });
  });

  // ---- setView ------------------------------------------------------------

  it("setView('deck') maps to zoomLevel 0", () => {
    // --- arrange ---------------------------
    const { hook, viewState } = _hook();

    // --- act -------------------------------
    hook.setView("deck");

    // --- assert ----------------------------
    expect(viewState.setView).toHaveBeenCalledWith({ zoomLevel: 0 });
  });

  it("setView('slide') maps to zoomLevel 1", () => {
    // --- arrange ---------------------------
    const { hook, viewState } = _hook();

    // --- act -------------------------------
    hook.setView("slide");

    // --- assert ----------------------------
    expect(viewState.setView).toHaveBeenCalledWith({ zoomLevel: 1 });
  });

  // ---- setScroll ----------------------------------------------------------

  it("setScroll routes through scrollManager.setPosition on the current slide", () => {
    // --- arrange ---------------------------
    const { hook, scrollManager } = _hook({ selectedSlide: "parallax" });

    // --- act -------------------------------
    hook.setScroll(450);

    // --- assert ----------------------------
    expect(scrollManager.setPosition).toHaveBeenCalledTimes(1);
    expect(scrollManager.setPosition).toHaveBeenCalledWith("parallax", 450);
  });

  // ---- isAnimating --------------------------------------------------------

  it("isAnimating delegates to the injected predicate", () => {
    // --- arrange ---------------------------
    let inFlight = false;
    const { hook } = _hook({ isAnimating: () => inFlight });

    // --- act / assert ----------------------
    expect(hook.isAnimating()).toBe(false);
    inFlight = true;
    expect(hook.isAnimating()).toBe(true);
  });
});
