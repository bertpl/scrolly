import { describe, it, expect } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { CanvasGeometry, ScrollManager, SnapManager, EdgeArrows, BezierOverlay, GroupLayout, ViewState, resolveTarget } = require("../../scrolly/render/assets/canvas.js");

function _geo(slides, fanSpacingFactor) {
  return new CanvasGeometry({
    slides: slides || {},
    fanSpacingFactor: fanSpacingFactor || 0.1,
  });
}

describe("CanvasGeometry", () => {
  // ---- Grid dimensions ----------------------------------------------------

  describe("grid dimensions", () => {
    it("returns 0x0 for empty slides", () => {
      const g = _geo({});
      expect(g.cols).toBe(0);
      expect(g.rows).toBe(0);
    });

    it("returns 1x1 for a single slide at origin", () => {
      const g = _geo({ a: [0, 0] });
      expect(g.cols).toBe(1);
      expect(g.rows).toBe(1);
    });

    it("computes bounding box from max positions", () => {
      const g = _geo({ a: [0, 0], b: [2, 1] });
      expect(g.cols).toBe(3);
      expect(g.rows).toBe(2);
    });
  });

  // ---- slidePosition ------------------------------------------------------

  describe("slidePosition", () => {
    it("returns position for known slide", () => {
      const g = _geo({ intro: [3, 5] });
      expect(g.slidePosition("intro")).toEqual({ x: 3, y: 5 });
    });

    it("returns null for unknown slide", () => {
      const g = _geo({ a: [0, 0] });
      expect(g.slidePosition("nope")).toBeNull();
    });
  });

  // ---- slideGapOffset ------------------------------------------------------

  describe("slideGapOffset", () => {
    it("returns accumulated dvmax gaps for known slide", () => {
      const g = _geo({ a: [0, 0], b: [2, 3] });
      g.refresh(1000, 1000);
      const gap = g.slideGapOffset("b");
      expect(gap.gapX).toBe(20);
      expect(gap.gapY).toBe(30);
    });

    it("returns zero gaps for origin slide", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const gap = g.slideGapOffset("a");
      expect(gap.gapX).toBe(0);
      expect(gap.gapY).toBe(0);
    });

    it("returns null for unknown slide", () => {
      const g = _geo({ a: [0, 0] });
      expect(g.slideGapOffset("nope")).toBeNull();
    });
  });

  // ---- slideAbstractPos ---------------------------------------------------

  describe("slideAbstractPos", () => {
    it("returns origin for slide at (0,0)", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const p = g.slideAbstractPos("a");
      expect(p.x).toBe(0);
      expect(p.y).toBe(0);
    });

    it("includes gap offset for non-origin slide", () => {
      const g = _geo({ a: [0, 0], b: [2, 1] });
      g.refresh(1000, 1000);
      const p = g.slideAbstractPos("b");
      // colGap = 0.1 on square; x = 2 * (1 + 0.1) = 2.2
      expect(p.x).toBeCloseTo(2.2);
      // rowGap = 0.1 on square; y = 1 * (1 + 0.1) = 1.1
      expect(p.y).toBeCloseTo(1.1);
    });

    it("gap scales with aspect ratio", () => {
      const g = _geo({ a: [0, 0], b: [1, 1] });
      g.refresh(1600, 900);
      const p = g.slideAbstractPos("b");
      // colGap = 0.1 * 1600/1600 = 0.1; x = 1.1
      expect(p.x).toBeCloseTo(1.1);
      // rowGap = 0.1 * 1600/900 ≈ 0.1778; y ≈ 1.1778
      expect(p.y).toBeGreaterThan(1.1);
    });

    it("returns null for unknown slide", () => {
      const g = _geo({ a: [0, 0] });
      expect(g.slideAbstractPos("nope")).toBeNull();
    });
  });

  // ---- Per-row gaps (group labels) ----------------------------------------

  describe("per-row gaps", () => {
    function _geoWithGroup(slides, groups) {
      return new CanvasGeometry({ slides, groups, fanSpacingFactor: 0.1 });
    }

    it("label row at row 0 adds LABEL_EXTRA above", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [1, 0] },
        [{ label: "G", slide_ids: ["a", "b"] }],
      );
      g.refresh(1000, 1000);
      // Row 0 gap = LABEL_EXTRA = 4 dvmax (not GAP, since nothing above row 0)
      const gap = g.slideGapOffset("a");
      expect(gap.gapY).toBe(4);
    });

    it("label row at row > 0 adds GAP + LABEL_EXTRA", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [0, 1], c: [1, 1] },
        [{ label: "G", slide_ids: ["b", "c"] }],
      );
      g.refresh(1000, 1000);
      // Row 0 gap = 0 (no label), row 1 gap = GAP + LABEL_EXTRA = 14
      const gapB = g.slideGapOffset("b");
      expect(gapB.gapY).toBe(14);
    });

    it("non-label rows get normal GAP", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [0, 1], c: [0, 2] },
        [{ label: "G", slide_ids: ["b"] }],
      );
      g.refresh(1000, 1000);
      // Row 0: 0, row 1: GAP + LABEL_EXTRA = 14, row 2: GAP = 10
      const gapC = g.slideGapOffset("c");
      expect(gapC.gapY).toBe(24);
    });

    it("effective grid size accounts for label extra", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [0, 1] },
        [{ label: "G", slide_ids: ["b"] }],
      );
      g.refresh(1000, 1000);
      const noGroup = _geoWithGroup({ a: [0, 0], b: [0, 1] }, []);
      noGroup.refresh(1000, 1000);
      const effGroup = g.effectiveGridSize();
      const effNoGroup = noGroup.effectiveGridSize();
      // Group version has 4dvmax extra = 0.04 cell-units on square viewport
      expect(effGroup.rows).toBeGreaterThan(effNoGroup.rows);
      expect(effGroup.rows - effNoGroup.rows).toBeCloseTo(0.04);
    });

    it("two groups sharing a top row get extra once", () => {
      const g = _geoWithGroup(
        { a: [0, 1], b: [1, 1] },
        [
          { label: "G1", slide_ids: ["a"] },
          { label: "G2", slide_ids: ["b"] },
        ],
      );
      g.refresh(1000, 1000);
      // Both groups start at row 1, but extra is applied once
      const gap = g.slideGapOffset("a");
      expect(gap.gapY).toBe(14); // GAP + LABEL_EXTRA, not GAP + 2*LABEL_EXTRA
    });

    it("rowGapAbove returns gap for valid row", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [0, 1] },
        [{ label: "G", slide_ids: ["b"] }],
      );
      expect(g.rowGapAbove(0)).toBe(0);
      expect(g.rowGapAbove(1)).toBe(14); // GAP + LABEL_EXTRA
    });

    it("rowGapAbove returns 0 for out-of-range row", () => {
      const g = _geoWithGroup({ a: [0, 0] }, []);
      expect(g.rowGapAbove(5)).toBe(0);
    });

    it("slideAbstractPos accounts for per-row gaps", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [1, 1], c: [0, 2] },
        [{ label: "G", slide_ids: ["b"] }],
      );
      g.refresh(1000, 1000);
      const posB = g.slideAbstractPos("b");
      const posC = g.slideAbstractPos("c");
      // Row 1 has GAP + LABEL_EXTRA = 14dvmax above it
      // Row 2 has GAP = 10dvmax above it
      // cumulative for row 1: 0 + 14 = 14 dvmax
      // cumulative for row 2: 0 + 14 + 10 = 24 dvmax
      expect(posB.y).toBeCloseTo(1 + 14 * 0.01);
      expect(posC.y).toBeCloseTo(2 + 24 * 0.01);
    });

    it("cellBounds accounts for per-row gaps", () => {
      const g = _geoWithGroup(
        { a: [0, 0], b: [0, 1] },
        [{ label: "G", slide_ids: ["b"] }],
      );
      g.refresh(1000, 1000);
      const pad = { top: 0.03, side: 0.03, bottom: 0.03 };
      const boundsRow0 = g.cellBounds(0, 0, 0, 0, pad);
      const boundsRow1 = g.cellBounds(0, 1, 0, 1, pad);
      // Row 1 starts further down due to GAP + LABEL_EXTRA above it
      const gapDiff = boundsRow1.top - (boundsRow0.top + boundsRow0.height);
      expect(gapDiff).toBeGreaterThan(0);
    });
  });

  // ---- Gaps and effective grid size -----------------------------------------

  describe("gaps and effective grid size", () => {
    it("gaps are equal on a square viewport", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const eff = g.effectiveGridSize();
      // 2 cols + 1 gap of 0.1 cell-units (10dvmax / 100dvw on square)
      expect(eff.cols).toBeCloseTo(2.1);
      expect(eff.rows).toBe(1);
    });

    it("row gap is larger on landscape", () => {
      const g = _geo({ a: [0, 0], b: [1, 0], c: [0, 1] });
      g.refresh(1600, 900);
      const eff = g.effectiveGridSize();
      // colGap = 0.1 * 1600/1600 = 0.1; rowGap = 0.1 * 1600/900 ≈ 0.178
      expect(eff.cols).toBeCloseTo(2.1);
      expect(eff.rows).toBeGreaterThan(2.1);
    });

    it("col gap is larger on portrait", () => {
      const g = _geo({ a: [0, 0], b: [1, 0], c: [0, 1] });
      g.refresh(900, 1600);
      const eff = g.effectiveGridSize();
      // colGap = 0.1 * 1600/900 ≈ 0.178; rowGap = 0.1 * 1600/1600 = 0.1
      expect(eff.cols).toBeGreaterThan(2.1);
      expect(eff.rows).toBeCloseTo(2.1);
    });
  });

  // ---- fitAllScale + deckCenter -------------------------------------------

  describe("fitAllScale", () => {
    it("returns 1 for empty grid", () => {
      const g = _geo({});
      expect(g.fitAllScale()).toBe(1);
    });

    it("scales down for multi-cell grids", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      // eff cols = 2.1, fitAll = 0.85 / 2.1
      expect(g.fitAllScale()).toBeCloseTo(0.85 / 2.1);
    });
  });

  describe("deckCenter", () => {
    it("centers on the effective grid", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const c = g.deckCenter();
      // eff cols = 2.1, center = 1.05
      expect(c.x).toBeCloseTo(1.05);
      expect(c.y).toBe(0.5);
    });
  });

  // ---- fanOffset ----------------------------------------------------------

  describe("fanOffset", () => {
    it("returns 0.5 for single-edge sides", () => {
      const g = _geo({}, 0.1);
      g.refresh(1000, 800);
      expect(g.fanOffset("top", 0, 1)).toBe(0.5);
    });

    it("spreads evenly for two edges on a big viewport", () => {
      const g = _geo({}, 0.1);
      g.refresh(2000, 1000);
      const o0 = g.fanOffset("top", 0, 2);
      const o1 = g.fanOffset("top", 1, 2);
      expect(o0).toBeCloseTo(0.45);
      expect(o1).toBeCloseTo(0.55);
    });

    it("applies MIN_FAN_SPACING_PX floor on small viewports", () => {
      const g = _geo({}, 0.1);
      g.refresh(200, 200);
      const o0 = g.fanOffset("top", 0, 2);
      const o1 = g.fanOffset("top", 1, 2);
      const spread = o1 - o0;
      expect(spread).toBeCloseTo(0.48);
    });

    it("uses viewport height for left/right sides", () => {
      const g = _geo({}, 0.1);
      g.refresh(1000, 2000);
      const o0 = g.fanOffset("left", 0, 2);
      const o1 = g.fanOffset("left", 1, 2);
      expect(o0).toBeCloseTo(0.45);
      expect(o1).toBeCloseTo(0.55);
    });

    it("returns 0.5 for zero-length side", () => {
      const g = _geo({}, 0.1);
      g.refresh(0, 0);
      expect(g.fanOffset("top", 0, 2)).toBe(0.5);
    });
  });

  // ---- cellBounds ---------------------------------------------------------

  describe("cellBounds", () => {
    it("computes pixel bounds on a square viewport", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const pad = { top: 0.06, side: 0.03, bottom: 0.03 };
      const r = g.cellBounds(0, 0, 1, 0, pad);
      // left = 0 * (1+0.1) * 1000 - 0.03*1000 = -30
      expect(r.left).toBeCloseTo(-30);
      // top = 0 * (1+0.1) * 1000 - 0.06*1000 = -60
      expect(r.top).toBeCloseTo(-60);
      // right = (1 * 1.1 + 1) * 1000 + 30 = 2130
      expect(r.width).toBeCloseTo(2160);
    });
  });

  // ---- attachmentPoint ------------------------------------------------------

  describe("attachmentPoint", () => {
    it("right side places at cell right edge", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const p = g.attachmentPoint(0, 0, "right", 0.5);
      expect(p.x).toBeCloseTo(1.0);
      expect(p.y).toBeCloseTo(0.5);
    });

    it("left side places at cell left edge with gap offset", () => {
      const g = _geo({ a: [1, 0] });
      g.refresh(1000, 1000);
      const p = g.attachmentPoint(1, 0, "left", 0.5);
      // x = 1 + 1 * 0.1 = 1.1
      expect(p.x).toBeCloseTo(1.1);
      expect(p.y).toBeCloseTo(0.5);
    });

    it("top side places at cell top edge", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const p = g.attachmentPoint(0, 0, "top", 0.5);
      expect(p.x).toBeCloseTo(0.5);
      expect(p.y).toBeCloseTo(0);
    });

    it("bottom side places at cell bottom edge", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const p = g.attachmentPoint(0, 0, "bottom", 0.5);
      expect(p.x).toBeCloseTo(0.5);
      expect(p.y).toBeCloseTo(1.0);
    });

    it("includes gap offset for non-origin cells", () => {
      const g = _geo({ a: [2, 1] });
      g.refresh(1600, 900);
      const p = g.attachmentPoint(2, 1, "right", 0.5);
      // colGap = 0.1 on landscape; x = 2 + 2*0.1 + 1.0 = 3.2
      expect(p.x).toBeCloseTo(3.2);
      // rowGap = 0.1 * 1600/900; y = 1 + 1*rowGap + 0.5
      expect(p.y).toBeGreaterThan(1.5);
    });
  });

  // ---- controlPoint ---------------------------------------------------------

  describe("controlPoint", () => {
    it("pushes control point along side normal", () => {
      const g = _geo({});
      const cp = g.controlPoint(0.95, 0.5, 1.05, 0.5, "right");
      // delta = |1.05 - 0.95| = 0.1; offset = 0.1 * 0.6 = 0.06
      expect(cp.x).toBeCloseTo(1.01);
      expect(cp.y).toBeCloseTo(0.5);
    });

    it("clamps at CONTROL_MAX", () => {
      const g = _geo({});
      const cp = g.controlPoint(0.95, 0.5, 10.05, 0.5, "right");
      // delta = 9.1; unclamped = 5.46; clamped to 1.0
      expect(cp.x).toBeCloseTo(1.95);
    });
  });

  // ---- buildPath ------------------------------------------------------------

  describe("buildPath", () => {
    it("produces a cubic bezier path for a horizontal edge", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const edge = {
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "b", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      };
      const d = g.buildPath(edge);
      expect(d).toContain("M ");
      expect(d).toContain(" C ");
      // Attachment points: a right at (1.0, 0.5), b left at (1.1, 0.5)
      expect(d).toMatch(/^M 1\.0000 0\.5000/);
      expect(d).toMatch(/1\.1000 0\.5000$/);
    });

    it("returns null for unknown slide", () => {
      const g = _geo({ a: [0, 0] });
      g.refresh(1000, 1000);
      const edge = {
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "nope", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      };
      expect(g.buildPath(edge)).toBeNull();
    });
  });

  // ---- groupBounds ----------------------------------------------------------

  describe("groupBounds", () => {
    it("computes bounding box from slide positions", () => {
      const g = _geo({ a: [1, 0], b: [3, 2] });
      const bounds = g.groupBounds({ label: "test", slide_ids: ["a", "b"] });
      expect(bounds).toEqual({ minX: 1, minY: 0, maxX: 3, maxY: 2 });
    });
  });
});

// ---- EdgeArrows (pure data accessors) -------------------------------------

describe("EdgeArrows", () => {
  function _arrows(edgesBySide, titles) {
    return new EdgeArrows(null, { edgesBySide, titles }, null);
  }

  describe("edgesForSide", () => {
    it("returns edges for a known slide and side", () => {
      const arrows = _arrows(
        { a: { right: [{ target: "b", fan_index: 0, fan_size: 1 }] } },
        { a: "A", b: "B" }
      );
      const edges = arrows.edgesForSide("a", "right");
      expect(edges).toEqual([{ target: "b", fan_index: 0, fan_size: 1 }]);
    });

    it("returns empty array for unknown slide", () => {
      const arrows = _arrows({}, {});
      expect(arrows.edgesForSide("nope", "left")).toEqual([]);
    });

    it("returns empty array for side with no edges", () => {
      const arrows = _arrows({ a: { right: [{ target: "b" }] } }, {});
      expect(arrows.edgesForSide("a", "left")).toEqual([]);
    });
  });

  describe("slideTitle", () => {
    it("returns title for known slide", () => {
      const arrows = _arrows({}, { intro: "Introduction" });
      expect(arrows.slideTitle("intro")).toBe("Introduction");
    });

    it("falls back to slide ID for unknown slide", () => {
      const arrows = _arrows({}, {});
      expect(arrows.slideTitle("mystery")).toBe("mystery");
    });
  });
});

// ---- SnapManager (pure static methods) ------------------------------------

describe("SnapManager", () => {
  describe("_nearest", () => {
    it("returns the closest snap position", () => {
      expect(SnapManager._nearest(45, [0, 50, 100])).toBe(50);
    });

    it("returns first when equidistant", () => {
      expect(SnapManager._nearest(50, [0, 100])).toBe(0);
    });

    it("returns exact match", () => {
      expect(SnapManager._nearest(100, [0, 50, 100, 150])).toBe(100);
    });

    it("returns single snap position", () => {
      expect(SnapManager._nearest(999, [42])).toBe(42);
    });
  });
});

// ---- resolveTarget (pure navigation resolution) ---------------------------

describe("resolveTarget", () => {
  function _edgesFn(edgeMap) {
    return (slideId, side) => {
      const slide = edgeMap[slideId];
      if (!slide) return [];
      return slide[side] || [];
    };
  }

  it("returns null for non-arrow keys", () => {
    expect(resolveTarget("Enter", _edgesFn({}), "a")).toBeNull();
  });

  it("returns target for single edge on pressed side", () => {
    const fn = _edgesFn({ a: { right: [{ target: "b" }] } });
    const r = resolveTarget("ArrowRight", fn, "a");
    expect(r).toEqual({ target: "b", shouldGlow: false, ambiguous: false });
  });

  it("returns shouldGlow for no edges on pressed side", () => {
    const fn = _edgesFn({ a: {} });
    const r = resolveTarget("ArrowRight", fn, "a");
    expect(r).toEqual({ target: null, shouldGlow: true, ambiguous: false });
  });

  it("returns ambiguous for two edges on pressed side", () => {
    const fn = _edgesFn({ a: { right: [{ target: "b" }, { target: "c" }] } });
    const r = resolveTarget("ArrowRight", fn, "a");
    expect(r).toEqual({ target: null, shouldGlow: false, ambiguous: true });
  });

  describe("linearization", () => {
    it("ArrowLeft falls back to top when left is empty", () => {
      const fn = _edgesFn({ a: { top: [{ target: "b" }] } });
      const r = resolveTarget("ArrowLeft", fn, "a");
      expect(r).toEqual({ target: "b", shouldGlow: false, ambiguous: false });
    });

    it("ArrowRight falls back to bottom when right is empty", () => {
      const fn = _edgesFn({ a: { bottom: [{ target: "b" }] } });
      const r = resolveTarget("ArrowRight", fn, "a");
      expect(r).toEqual({ target: "b", shouldGlow: false, ambiguous: false });
    });

    it("no linearization for ArrowUp or ArrowDown", () => {
      const fn = _edgesFn({ a: { left: [{ target: "b" }] } });
      const r = resolveTarget("ArrowUp", fn, "a");
      expect(r).toEqual({ target: null, shouldGlow: true, ambiguous: false });
    });

    it("linearization does not fire when strict side has edges", () => {
      const fn = _edgesFn({ a: { left: [{ target: "x" }], top: [{ target: "y" }] } });
      const r = resolveTarget("ArrowLeft", fn, "a");
      expect(r).toEqual({ target: "x", shouldGlow: false, ambiguous: false });
    });

    it("linearization pool with two entries does not resolve", () => {
      const fn = _edgesFn({ a: { top: [{ target: "b" }, { target: "c" }] } });
      const r = resolveTarget("ArrowLeft", fn, "a");
      expect(r).toEqual({ target: null, shouldGlow: true, ambiguous: false });
    });
  });
});

// ---- EdgeArrows.computeArrowData ----------------------------------------

describe("EdgeArrows.computeArrowData", () => {
  function _arrows(geo, edgesBySide, titles) {
    return new EdgeArrows(geo, { edgesBySide, titles }, null);
  }

  it("returns arrow data with fan offsets for selected slide", () => {
    const geo = _geo({ a: [0, 0], b: [1, 0] }, 0.1);
    geo.refresh(1000, 1000);
    const arrows = _arrows(geo,
      { a: { right: [{ target: "b", fan_index: 0, fan_size: 1 }] } },
      { a: "A", b: "B" },
    );
    const data = arrows.computeArrowData("a");
    expect(data).toHaveLength(1);
    expect(data[0].side).toBe("right");
    expect(data[0].target).toBe("b");
    expect(data[0].title).toBe("B");
    expect(data[0].fanOffset).toBeCloseTo(0.5);
  });

  it("returns empty array for slide with no edges", () => {
    const geo = _geo({ a: [0, 0] }, 0.1);
    geo.refresh(1000, 1000);
    const arrows = _arrows(geo, {}, {});
    expect(arrows.computeArrowData("a")).toEqual([]);
  });

  it("includes all four sides", () => {
    const geo = _geo({ a: [1, 1] }, 0.1);
    geo.refresh(1000, 1000);
    const arrows = _arrows(geo,
      { a: {
        top: [{ target: "t", fan_index: 0, fan_size: 1 }],
        bottom: [{ target: "b", fan_index: 0, fan_size: 1 }],
        left: [{ target: "l", fan_index: 0, fan_size: 1 }],
        right: [{ target: "r", fan_index: 0, fan_size: 1 }],
      } },
      { t: "Top", b: "Bottom", l: "Left", r: "Right" },
    );
    const data = arrows.computeArrowData("a");
    expect(data).toHaveLength(4);
    const sides = data.map((d) => d.side);
    expect(sides).toEqual(["top", "bottom", "left", "right"]);
  });

  it("falls back to slide ID when title is missing", () => {
    const geo = _geo({ a: [0, 0], b: [1, 0] }, 0.1);
    geo.refresh(1000, 1000);
    const arrows = _arrows(geo,
      { a: { right: [{ target: "b", fan_index: 0, fan_size: 1 }] } },
      {},
    );
    const data = arrows.computeArrowData("a");
    expect(data[0].title).toBe("b");
  });
});

// ---- BezierOverlay.computePaths -----------------------------------------

describe("BezierOverlay.computePaths", () => {
  it("returns path strings and viewBox for all edges", () => {
    const geo = new CanvasGeometry({
      slides: { a: [0, 0], b: [1, 0] },
      edges: [{
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "b", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      }],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const overlay = new BezierOverlay(geo, null);
    const result = overlay.computePaths();
    expect(result.viewBox).toBe("0 0 2.1 1");
    expect(result.width).toBe("210dvw");
    expect(result.height).toBe("100dvh");
    expect(result.paths).toHaveLength(1);
    expect(result.paths[0]).toContain("M ");
    expect(result.paths[0]).toContain(" C ");
  });

  it("skips edges with unknown slides", () => {
    const geo = new CanvasGeometry({
      slides: { a: [0, 0] },
      edges: [{
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "nope", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      }],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const overlay = new BezierOverlay(geo, null);
    const result = overlay.computePaths();
    expect(result.paths).toHaveLength(0);
  });

  it("returns null for empty grid", () => {
    const geo = new CanvasGeometry({ slides: {}, edges: [], fanSpacingFactor: 0.1 });
    geo.refresh(1000, 1000);
    const overlay = new BezierOverlay(geo, null);
    expect(overlay.computePaths()).toBeNull();
  });
});

// ---- GroupLayout.computeLayout ------------------------------------------

describe("GroupLayout.computeLayout", () => {
  it("returns pixel bounds and label positions for each group", () => {
    const geo = new CanvasGeometry({
      slides: { a: [0, 0], b: [1, 0] },
      groups: [{ label: "Test", slide_ids: ["a", "b"] }],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const layout = new GroupLayout(geo, null);
    layout._labelWidths = [100];
    const data = layout.computeLayout();
    expect(data).toHaveLength(1);
    expect(data[0].label).toBe("Test");
    expect(data[0].svgLeft).toBeCloseTo(-30);
    expect(data[0].svgWidth).toBeGreaterThan(0);
    expect(data[0].path).toContain("M ");
    expect(data[0].path).toContain("A ");
    expect(data[0].path).toContain("Z");
    expect(data[0].labelX).toBeCloseTo(data[0].svgLeft + data[0].svgWidth / 2);
  });

  it("returns empty array when no groups", () => {
    const geo = new CanvasGeometry({
      slides: { a: [0, 0] },
      groups: [],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const layout = new GroupLayout(geo, null);
    expect(layout.computeLayout()).toEqual([]);
  });
});

// ---- GroupLayout.buildTabPath --------------------------------------------

describe("GroupLayout.buildTabPath", () => {
  it("produces a closed SVG path with arcs", () => {
    const d = GroupLayout.buildTabPath(200, 100, 80, 30, 10);
    expect(d).toContain("M ");
    expect(d).toContain("A ");
    expect(d).toContain("Z");
  });

  it("tab is centered on the body top edge", () => {
    const d = GroupLayout.buildTabPath(200, 100, 80, 30, 10);
    // Tab center = 200/2 = 100; tab left = 60, tab right = 140
    // Path should go up to y=0 (tab top) between x ~60..140
    expect(d).toContain(" 0"); // y=0 appears in tab top coordinates
  });

  it("falls back to plain rounded rect when tabH is 0", () => {
    const d = GroupLayout.buildTabPath(200, 100, 80, 0, 10);
    expect(d).toContain("M ");
    expect(d).toContain("Z");
    const arcCount = (d.match(/A /g) || []).length;
    expect(arcCount).toBe(4);
  });

  it("uses cubic beziers for tab sides", () => {
    const d = GroupLayout.buildTabPath(400, 200, 120, 40, 10);
    const cubicCount = (d.match(/C /g) || []).length;
    expect(cubicCount).toBe(2);
  });

  it("clamps margin to available space", () => {
    const d = GroupLayout.buildTabPath(100, 80, 60, 30, 5);
    expect(d).toContain("M ");
    expect(d).toContain("Z");
  });
});

// ---- ViewState.computeViewCSS -------------------------------------------

describe("ViewState.computeViewCSS", () => {
  function _viewState(slides, selectedSlide, zoomLevel) {
    const geo = new CanvasGeometry({ slides, fanSpacingFactor: 0.1 });
    geo.refresh(1000, 1000);
    const vs = new ViewState(geo, null, null, null, selectedSlide, null, () => null);
    if (zoomLevel !== undefined) vs.zoomLevel = zoomLevel;
    return vs;
  }

  it("returns slide center and scale 1 at full zoom", () => {
    const vs = _viewState({ a: [0, 0], b: [1, 0] }, "a", 1);
    const css = vs.computeViewCSS();
    expect(css.cx).toBeCloseTo(0.5);
    expect(css.cy).toBeCloseTo(0.5);
    expect(css.scale).toBeCloseTo(1);
    expect(css.zoom).toBe(1);
  });

  it("returns deck center and fitAll scale at zero zoom", () => {
    const vs = _viewState({ a: [0, 0], b: [1, 0] }, "a", 0);
    const css = vs.computeViewCSS();
    // deckCenter = (2.1/2, 1/2) = (1.05, 0.5)
    expect(css.cx).toBeCloseTo(1.05);
    expect(css.cy).toBeCloseTo(0.5);
    expect(css.scale).toBeCloseTo(0.85 / 2.1);
    expect(css.zoom).toBe(0);
  });

  it("returns null for unknown slide", () => {
    const vs = _viewState({ a: [0, 0] }, "nope", 1);
    expect(vs.computeViewCSS()).toBeNull();
  });

  it("returns null for empty grid", () => {
    const vs = _viewState({}, "a", 1);
    expect(vs.computeViewCSS()).toBeNull();
  });
});

// ---- SnapManager.prevTarget / nextTarget --------------------------------

describe("SnapManager.prevTarget / nextTarget", () => {
  function _snap(snapConfig, positions) {
    const scrollManager = { position: (id) => positions[id] || 0 };
    return new SnapManager(scrollManager, snapConfig, () => null);
  }

  describe("prevTarget", () => {
    it("returns previous snap position", () => {
      const snap = _snap({ a: { snapPositions: [0, 50, 100] } }, { a: 60 });
      expect(snap.prevTarget("a")).toBe(50);
    });

    it("returns null when before first snap", () => {
      const snap = _snap({ a: { snapPositions: [0, 50, 100] } }, { a: 0 });
      expect(snap.prevTarget("a")).toBeNull();
    });

    it("returns null when no snap positions configured", () => {
      const snap = _snap({}, { a: 50 });
      expect(snap.prevTarget("a")).toBeNull();
    });
  });

  describe("nextTarget", () => {
    it("returns next snap position", () => {
      const snap = _snap({ a: { snapPositions: [0, 50, 100] } }, { a: 40 });
      expect(snap.nextTarget("a")).toBe(50);
    });

    it("returns null when after last snap", () => {
      const snap = _snap({ a: { snapPositions: [0, 50, 100] } }, { a: 100 });
      expect(snap.nextTarget("a")).toBeNull();
    });

    it("returns null when no snap positions configured", () => {
      const snap = _snap({}, { a: 50 });
      expect(snap.nextTarget("a")).toBeNull();
    });
  });
});

// ---- SnapManager.easeOutQuad --------------------------------------------

describe("SnapManager.easeOutQuad", () => {
  it("returns 0 at t=0", () => {
    expect(SnapManager.easeOutQuad(0)).toBe(0);
  });

  it("returns 1 at t=1", () => {
    expect(SnapManager.easeOutQuad(1)).toBe(1);
  });

  it("returns 0.75 at t=0.5", () => {
    expect(SnapManager.easeOutQuad(0.5)).toBeCloseTo(0.75);
  });
});

describe("ScrollManager.computeThumbHeight", () => {
  it("returns base height when no snaps", () => {
    expect(ScrollManager.computeThumbHeight(60, 400, 0)).toBe(60);
  });

  it("returns base height with 1 snap (no cap applies)", () => {
    expect(ScrollManager.computeThumbHeight(60, 400, 1)).toBe(60);
  });

  it("caps at 2/3 * trackHeight/numSnaps for many snaps", () => {
    // 20 snaps, track 400px → cap = (2/3) * (400/20) = 13.33
    const result = ScrollManager.computeThumbHeight(60, 400, 20);
    expect(result).toBeCloseTo((2 / 3) * (400 / 20));
  });

  it("floors at MIN_THUMB_HEIGHT", () => {
    // 100 snaps, track 400px → cap = (2/3) * (400/100) = 2.67 → clamped to 10
    const result = ScrollManager.computeThumbHeight(60, 400, 100);
    expect(result).toBe(ScrollManager.MIN_THUMB_HEIGHT);
  });

  it("clamps to trackHeight when track is very short", () => {
    const result = ScrollManager.computeThumbHeight(60, 30, 0);
    expect(result).toBe(30);
  });
});

describe("SnapManager.getNumSnaps", () => {
  it("returns 0 for unknown slideId", () => {
    const snap = new SnapManager(null, {}, () => null);
    expect(snap.getNumSnaps("unknown")).toBe(0);
  });

  it("returns 0 when snapPositions is empty", () => {
    const snap = new SnapManager(null, { s1: { snapPositions: [] } }, () => null);
    expect(snap.getNumSnaps("s1")).toBe(0);
  });

  it("returns count of snap positions", () => {
    const snap = new SnapManager(null, { s1: { snapPositions: [0, 100, 200, 300] } }, () => null);
    expect(snap.getNumSnaps("s1")).toBe(4);
  });
});

describe("ScrollManager.trackGeometry snap-aware thumb", () => {
  it("uses snapManager to determine numSnaps for thumb sizing", () => {
    const scrollCfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0 } };
    const snapCfg = { s1: { snapPositions: [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000] } };

    const trackEl = { clientHeight: 300 };
    const container = { querySelector: (sel) => sel === ".slide-scrollbar" ? trackEl : null };

    const scrollMgr = new ScrollManager(scrollCfg, () => container);
    const snapMgr = new SnapManager(scrollMgr, snapCfg, () => container);
    scrollMgr.setSnapManager(snapMgr);

    const geo = scrollMgr.trackGeometry(container, "s1");
    // 11 snaps, track 300px → cap = (2/3) * (300/11) ≈ 18.18
    const expected = (2 / 3) * (300 / 11);
    expect(geo.thumbHeight).toBeCloseTo(expected);
  });

  it("uses default thumb height when no snapManager is set", () => {
    const scrollCfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0 } };

    const trackEl = { clientHeight: 300 };
    const container = { querySelector: (sel) => sel === ".slide-scrollbar" ? trackEl : null };

    const scrollMgr = new ScrollManager(scrollCfg, () => container);

    const geo = scrollMgr.trackGeometry(container, "s1");
    expect(geo.thumbHeight).toBe(ScrollManager.DEFAULT_THUMB_HEIGHT);
  });
});
