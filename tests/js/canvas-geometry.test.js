import { describe, it, expect, vi } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { AxisGeometry, CanvasGeometry, ScrollManager, SnapManager, EdgeArrows, BezierOverlay, GroupLayout, ViewState, IdleTimer, resolveTarget, evaluatePiecewiseLinear } = require("../../scrolly/render/assets/canvas.js");

function _geo(slides, fanSpacingFactor) {
  return new CanvasGeometry({
    slides: slides || {},
    fanSpacingFactor: fanSpacingFactor || 0.1,
  });
}

function _geoWithGroup(slides, groups) {
  return new CanvasGeometry({ slides, groups, fanSpacingFactor: 0.1 });
}

describe("AxisGeometry", () => {
  function _axis(min, max, extras) {
    // baseGap = CanvasGeometry.GAP = 10.
    return new AxisGeometry(min, max, 10, extras || new Map());
  }

  describe("span", () => {
    it("is 0 for an empty axis (max < min)", () => {
      expect(_axis(0, -1).span).toBe(0);
    });

    it("is 1 for a single cell", () => {
      expect(_axis(3, 3).span).toBe(1);
    });

    it("counts inclusively across positive bounds", () => {
      expect(_axis(0, 2).span).toBe(3);
    });

    it("counts inclusively across negative bounds", () => {
      expect(_axis(-2, 1).span).toBe(4);
    });
  });

  describe("gapBefore", () => {
    it("has no base gap on the leading cell (even when negative)", () => {
      expect(_axis(-2, 1).gapBefore(-2)).toBe(0);
    });

    it("is the base gap above the leading cell", () => {
      expect(_axis(-2, 1).gapBefore(-1)).toBe(10);
    });

    it("adds the per-cell extra to the base gap", () => {
      expect(_axis(0, 2, new Map([[1, 4]])).gapBefore(1)).toBe(14);
    });

    it("is extra-only when the extra falls on the leading cell", () => {
      expect(_axis(0, 2, new Map([[0, 4]])).gapBefore(0)).toBe(4);
    });
  });

  describe("cumulativeGap", () => {
    it("is 0 at the leading cell with no extra", () => {
      expect(_axis(-2, 1).cumulativeGap(-2)).toBe(0);
    });

    it("accumulates the base gap relative to min, not 0", () => {
      // Cell 0 in a [-2, 1] axis is two steps from min → 2 * GAP.
      expect(_axis(-2, 1).cumulativeGap(0)).toBe(20);
    });

    it("counts extras only within [min, i]", () => {
      const a = _axis(0, 3, new Map([[1, 4], [3, 4]]));
      // up to cell 2: base 2*10 + extra at 1 only (extra at 3 excluded) = 24
      expect(a.cumulativeGap(2)).toBe(24);
    });

    it("reads out-of-range indices as 0", () => {
      const a = _axis(0, 1);
      expect(a.cumulativeGap(-5)).toBe(0);
      expect(a.cumulativeGap(5)).toBe(0);
    });
  });

  describe("abstractStart and factor", () => {
    it("ignores gaps before setFactor (factor defaults to 0)", () => {
      expect(_axis(-2, 1).abstractStart(1)).toBe(1);
    });

    it("applies the factor to the cumulative gap", () => {
      const a = _axis(-2, 1);
      a.setFactor(0.01);
      // cell 0 is 2*GAP = 20 gap-units from min → 0 + 20*0.01 = 0.2
      expect(a.abstractStart(0)).toBeCloseTo(0.2);
    });
  });

  describe("deck edges", () => {
    it("leading edge sits on the bare min cell line", () => {
      const a = _axis(-2, 1);
      a.setFactor(0.01);
      expect(a.deckLeadingEdge()).toBeCloseTo(-2);
    });

    it("pulls a leading-cell extra back out of the leading edge", () => {
      // A label/extra on the leading cell must not push the bbox edge in.
      const a = _axis(0, 2, new Map([[0, 4]]));
      a.setFactor(0.01);
      expect(a.deckLeadingEdge()).toBeCloseTo(0);
    });

    it("extent is shift-invariant and center tracks the shift", () => {
      const atOrigin = _axis(0, 2);
      atOrigin.setFactor(0.01);
      const negative = _axis(-5, -3);
      negative.setFactor(0.01);
      expect(negative.deckExtent()).toBeCloseTo(atOrigin.deckExtent());
      // origins differ by 5 → centers differ by 5
      expect(atOrigin.deckCenter() - negative.deckCenter()).toBeCloseTo(5);
    });
  });
});

// ---- CanvasGeometry — negative & off-origin coordinates -------------------

describe("CanvasGeometry — negative & off-origin coordinates", () => {
  it("cols/rows count inclusively across a negative bounding box", () => {
    const g = _geo({ a: [-1, -1], b: [0, 0] });
    expect(g.cols).toBe(2);
    expect(g.rows).toBe(2);
  });

  it("leaves a real inter-row gap between row -1 and row 0 (regression)", () => {
    // The bug this PR fixes: a slide at row -1 used to abut row 0 with no
    // gap, because the row-gap array was indexed from absolute 0.
    const g = _geo({ a: [0, -1], b: [0, 0] });
    g.refresh(1000, 1000);
    expect(g.slideGapOffset("a").gapY).toBe(0);   // top row, no gap above
    expect(g.slideGapOffset("b").gapY).toBe(10);  // one GAP above row 0
    // b's top edge sits a full GAP*factor below a's bottom edge.
    const aPos = g.slideAbstractPos("a");
    const bPos = g.slideAbstractPos("b");
    expect(bPos.y - (aPos.y + 1)).toBeCloseTo(0.1);  // GAP(10) * factor(0.01)
  });

  it("leaves a real inter-column gap between col -1 and col 0", () => {
    const g = _geo({ a: [-1, 0], b: [0, 0] });
    g.refresh(1000, 1000);
    expect(g.slideGapOffset("a").gapX).toBe(0);
    expect(g.slideGapOffset("b").gapX).toBe(10);
    const aPos = g.slideAbstractPos("a");
    const bPos = g.slideAbstractPos("b");
    expect(bPos.x - (aPos.x + 1)).toBeCloseTo(0.1);
  });

  it("deckBounds sits on the bare cell lines for a negative-origin deck", () => {
    const g = _geo({ a: [-2, -1], b: [-1, -1] });
    g.refresh(1000, 1000);
    const b = g.deckBounds();
    expect(b.left).toBeCloseTo(-2);   // minX
    expect(b.top).toBeCloseTo(-1);    // minY
    expect(b.right).toBeCloseTo(0.1); // -1 + 1*GAP*0.01 + 1
    expect(b.bottom).toBeCloseTo(0);  // -1 + 1 (single row)
  });

  it("is shift-invariant into negative space (size + fit scale)", () => {
    const atOrigin = _geo({ a: [0, 0], b: [1, 0] });
    atOrigin.refresh(1000, 1000);
    const negative = _geo({ a: [-3, -2], b: [-2, -2] });
    negative.refresh(1000, 1000);
    expect(negative.effectiveGridSize().cols).toBeCloseTo(atOrigin.effectiveGridSize().cols);
    expect(negative.effectiveGridSize().rows).toBeCloseTo(atOrigin.effectiveGridSize().rows);
    expect(negative.fitAllScale()).toBeCloseTo(atOrigin.fitAllScale());
  });

  it("builds a bezier path inside overlayBounds for negative-coord slides", () => {
    const geo = new CanvasGeometry({
      slides: { a: [-2, -1], b: [-1, -1] },
      edges: [{
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "b", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      }],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const o = geo.overlayBounds(BezierOverlay.MARGIN);
    const d = geo.buildPath(geo.edges[0]);
    const m = d.match(/^M ([\d.-]+) ([\d.-]+) .* ([\d.-]+) ([\d.-]+)$/);
    const mx = Number(m[1]), my = Number(m[2]);
    expect(mx).toBeGreaterThanOrEqual(o.left);
    expect(mx).toBeLessThanOrEqual(o.left + o.width);
    expect(my).toBeGreaterThanOrEqual(o.top);
    expect(my).toBeLessThanOrEqual(o.top + o.height);
  });

  it("applies LABEL_EXTRA on a negative top row", () => {
    const noLabel = _geoWithGroup({ a: [0, -1], b: [1, -1] }, []);
    noLabel.refresh(1000, 1000);
    const labeled = _geoWithGroup(
      { a: [0, -1], b: [1, -1] },
      [{ label: "G", slide_ids: ["a", "b"] }],
    );
    labeled.refresh(1000, 1000);
    const nl = noLabel.deckBounds();
    const l = labeled.deckBounds();
    expect(l.top).toBeCloseTo(nl.top);  // top edge stays on the cell line (-1)
    expect((l.bottom - l.top) - (nl.bottom - nl.top)).toBeCloseTo(0.04);  // LABEL_EXTRA
  });

  it("is symmetric under transpose (columns behave as rows do)", () => {
    // Same shape rotated 90° on a square viewport, no labels: the column
    // axis and the row axis must produce identical geometry.
    const horizontal = _geo({ a: [0, 0], b: [2, 0] });
    horizontal.refresh(1000, 1000);
    const vertical = _geo({ a: [0, 0], b: [0, 2] });
    vertical.refresh(1000, 1000);
    expect(horizontal.effectiveGridSize().cols).toBeCloseTo(vertical.effectiveGridSize().rows);
    expect(horizontal.slideGapOffset("b").gapX).toBe(vertical.slideGapOffset("b").gapY);
  });
});

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

    it("returns the occupied span, not the extent from (0, 0)", () => {
      // Leftmost slide at col 2, topmost at row 1 — span is 2x1, not 4x3.
      const g = _geo({ a: [2, 1], b: [3, 1] });
      expect(g.cols).toBe(2);
      expect(g.rows).toBe(1);
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
      // Both groups start at row 1, but the label extra is applied once.
      // Row 1 is the deck's topmost row, so it carries no inter-row GAP —
      // only LABEL_EXTRA once (not 2*LABEL_EXTRA).
      const gap = g.slideGapOffset("a");
      expect(gap.gapY).toBe(4);
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

    it("is shift-invariant — same shape at any origin gives the same size", () => {
      // A 2x1 deck has the same effective size whether it sits at (0,0)
      // or (2,1) — the leading empty columns/rows must not be counted.
      const atOrigin = _geo({ a: [0, 0], b: [1, 0] });
      atOrigin.refresh(1000, 1000);
      const shifted = _geo({ a: [2, 1], b: [3, 1] });
      shifted.refresh(1000, 1000);
      const effOrigin = atOrigin.effectiveGridSize();
      const effShifted = shifted.effectiveGridSize();
      expect(effShifted.cols).toBeCloseTo(effOrigin.cols);
      expect(effShifted.rows).toBeCloseTo(effOrigin.rows);
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

    it("is shift-invariant — origin doesn't affect the fit scale", () => {
      const atOrigin = _geo({ a: [0, 0], b: [1, 0] });
      atOrigin.refresh(1000, 1000);
      const shifted = _geo({ a: [3, 2], b: [4, 2] });
      shifted.refresh(1000, 1000);
      expect(shifted.fitAllScale()).toBeCloseTo(atOrigin.fitAllScale());
    });
  });

  // ---- deckBounds ---------------------------------------------------------

  describe("deckBounds", () => {
    it("returns all zeros for an empty deck", () => {
      const g = _geo({});
      g.refresh(1000, 1000);
      expect(g.deckBounds()).toEqual({ left: 0, top: 0, right: 0, bottom: 0 });
    });

    it("returns the visible abstract bounding box for a deck at origin", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const b = g.deckBounds();
      // colGap = 0.1 on square; left = 0, right = 1*1.1 + 1 = 2.1
      expect(b.left).toBeCloseTo(0);
      expect(b.right).toBeCloseTo(2.1);
      // No label, no leading rows; top = 0, bottom = 1
      expect(b.top).toBeCloseTo(0);
      expect(b.bottom).toBeCloseTo(1);
    });

    it("shifts left/top/right/bottom with the deck's origin", () => {
      const g = _geo({ a: [3, 2], b: [4, 2] });
      g.refresh(1000, 1000);
      const b = g.deckBounds();
      // Bbox-relative: the leading edges sit on the bare min cell lines
      // (left = minX = 3, top = minY = 2), with gaps accumulating toward
      // the trailing edges. left = 3; right = 4 + 1*GAP*0.01 + 1 = 5.1.
      expect(b.left).toBeCloseTo(3);
      expect(b.right).toBeCloseTo(5.1);
      // Single row: top = 2; bottom = 2 + 1 = 3.
      expect(b.top).toBeCloseTo(2);
      expect(b.bottom).toBeCloseTo(3);
    });

    it("grows the deck by LABEL_EXTRA when the topmost row carries a label", () => {
      // The labeled version inflates cumulativeRowGap above the topmost
      // slide; the label-extra subtraction in deckBounds.top compensates
      // so the visible top stays put, and the visible bottom shifts down
      // by LABEL_EXTRA — net effect: the deck is taller by that amount.
      const noLabel = _geoWithGroup({ a: [0, 0], b: [1, 0] }, []);
      noLabel.refresh(1000, 1000);
      const labeled = _geoWithGroup(
        { a: [0, 0], b: [1, 0] },
        [{ label: "G", slide_ids: ["a", "b"] }],
      );
      labeled.refresh(1000, 1000);
      const nlBounds = noLabel.deckBounds();
      const lBounds = labeled.deckBounds();
      expect(lBounds.top).toBeCloseTo(nlBounds.top);
      // LABEL_EXTRA = 4 dvmax → 0.04 in row units on a square viewport.
      expect((lBounds.bottom - lBounds.top) - (nlBounds.bottom - nlBounds.top)).toBeCloseTo(0.04);
    });

    it("effectiveGridSize and deckCenter are derived from deckBounds", () => {
      const g = _geo({ a: [2, 1], b: [3, 1] });
      g.refresh(1000, 1000);
      const b = g.deckBounds();
      const size = g.effectiveGridSize();
      const c = g.deckCenter();
      expect(size.cols).toBeCloseTo(b.right - b.left);
      expect(size.rows).toBeCloseTo(b.bottom - b.top);
      expect(c.x).toBeCloseTo((b.left + b.right) / 2);
      expect(c.y).toBeCloseTo((b.top + b.bottom) / 2);
    });
  });

  // ---- overlayBounds ------------------------------------------------------

  describe("overlayBounds", () => {
    it("equals deckBounds when margin is 0", () => {
      const g = _geo({ a: [2, 1], b: [3, 1] });
      g.refresh(1000, 1000);
      const b = g.deckBounds();
      const o = g.overlayBounds(0);
      expect(o.left).toBeCloseTo(b.left);
      expect(o.top).toBeCloseTo(b.top);
      expect(o.width).toBeCloseTo(b.right - b.left);
      expect(o.height).toBeCloseTo(b.bottom - b.top);
    });

    it("inflates by `margin` on every side", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const b = g.deckBounds();
      const o = g.overlayBounds(2);
      expect(o.left).toBeCloseTo(b.left - 2);
      expect(o.top).toBeCloseTo(b.top - 2);
      expect(o.width).toBeCloseTo((b.right - b.left) + 4);
      expect(o.height).toBeCloseTo((b.bottom - b.top) + 4);
    });

    it("viewBox string carries the same numbers", () => {
      const g = _geo({ a: [0, 0], b: [1, 0] });
      g.refresh(1000, 1000);
      const o = g.overlayBounds(2);
      expect(o.viewBox).toBe(
        o.left + " " + o.top + " " + o.width + " " + o.height,
      );
    });

    it("tracks the deck origin — off-origin decks shift correspondingly", () => {
      // Same shape, different origin. The overlay box should track the
      // deck's bounding box; the size stays the same.
      const atOrigin = _geo({ a: [0, 0], b: [1, 0] });
      atOrigin.refresh(1000, 1000);
      const shifted = _geo({ a: [3, 2], b: [4, 2] });
      shifted.refresh(1000, 1000);
      const oOrigin = atOrigin.overlayBounds(2);
      const oShift = shifted.overlayBounds(2);
      expect(oShift.width).toBeCloseTo(oOrigin.width);
      expect(oShift.height).toBeCloseTo(oOrigin.height);
      expect(oShift.left).toBeGreaterThan(oOrigin.left);
      expect(oShift.top).toBeGreaterThan(oOrigin.top);
    });

    it("inherits the LABEL_EXTRA top-row tab from deckBounds", () => {
      // Group on the topmost row → deckBounds adds LABEL_EXTRA to bottom;
      // overlayBounds inherits the taller box.
      const noLabel = _geoWithGroup({ a: [0, 0], b: [1, 0] }, []);
      noLabel.refresh(1000, 1000);
      const labeled = _geoWithGroup(
        { a: [0, 0], b: [1, 0] },
        [{ label: "G", slide_ids: ["a", "b"] }],
      );
      labeled.refresh(1000, 1000);
      const oNo = noLabel.overlayBounds(2);
      const oLab = labeled.overlayBounds(2);
      expect(oLab.top).toBeCloseTo(oNo.top);
      expect(oLab.height - oNo.height).toBeCloseTo(0.04);  // LABEL_EXTRA = 4 dvmax
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

    it("tracks the bounding-box centroid for off-origin decks", () => {
      // Same shape as above but shifted by (+3, +2). Center is the midpoint
      // of the bbox-relative bounds, not ((maxX+1)/2, (maxY+1)/2).
      const g = _geo({ a: [3, 2], b: [4, 2] });
      g.refresh(1000, 1000);
      const c = g.deckCenter();
      // left = 3; right = 4 + 1*GAP*0.01 + 1 = 5.1; cx = 4.05
      expect(c.x).toBeCloseTo(4.05);
      // top = 2; bottom = 3 (single row, no gap); cy = 2.5
      expect(c.y).toBeCloseTo(2.5);
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

    it("applies FAN_MIN_SPACING_PX floor on small viewports", () => {
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
      // Anchor at origin so col 1 is genuinely offset from the deck min.
      const g = _geo({ o: [0, 0], a: [1, 0] });
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
      // Anchor at origin so (2, 1) is genuinely offset from the deck min.
      const g = _geo({ o: [0, 0], a: [2, 1] });
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
  it("returns SVG box + viewBox + path strings for a deck at origin", () => {
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
    // deckBounds {left:0, top:0, right:2.1, bottom:1}; MARGIN=2 expands on all sides.
    expect(result.viewBox).toBe("-2 -2 6.1 5");
    expect(result.left).toBe("-200dvw");
    expect(result.top).toBe("-200dvh");
    expect(result.width).toBe("610dvw");
    expect(result.height).toBe("500dvh");
    expect(result.paths).toHaveLength(1);
    expect(result.paths[0]).toContain("M ");
    expect(result.paths[0]).toContain(" C ");
  });

  it("shifts the SVG box and viewBox to enclose an off-origin deck", () => {
    // The bug this fix addresses: when the deck doesn't start at (0, 0)
    // the overlay must shift its CSS box and viewBox so absolute-coord
    // paths near the right/bottom slides stay inside the clipping box.
    const geo = new CanvasGeometry({
      slides: { a: [2, 1], b: [3, 1] },
      edges: [{
        a_slide: "a", a_side: "right", a_fan_index: 0, a_fan_size: 1,
        b_slide: "b", b_side: "left", b_fan_index: 0, b_fan_size: 1,
      }],
      fanSpacingFactor: 0.1,
    });
    geo.refresh(1000, 1000);
    const result = new BezierOverlay(geo, null).computePaths();
    // Bbox-relative deckBounds: left = minX = 2; right = 3 + 1*GAP*0.01 + 1
    // = 4.1; cols = 2.1. top = minY = 1; bottom = 1 + 1 = 2; rows = 1.
    // MARGIN=2 → SVG left=0, top=-1, width=6.1, height=5.
    expect(result.viewBox).toBe("0 -1 6.1 5");
    expect(result.left).toBe("0dvw");
    expect(result.top).toBe("-100dvh");
    expect(result.width).toBe("610dvw");
    expect(result.height).toBe("500dvh");
    // Path endpoints stay in absolute-grid coords; under the new viewBox
    // they fall inside the SVG's clipping box.
    const m = result.paths[0].match(/^M ([\d.-]+) ([\d.-]+) .* ([\d.-]+) ([\d.-]+)$/);
    const [, mx, my, , ] = m;
    expect(Number(mx)).toBeCloseTo(3);    // abstractStart(2)=2 (deck min) + 1.0
    expect(Number(my)).toBeCloseTo(1.5);  // abstractStart(1)=1 (deck min) + fanOff=0.5
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

// ---- SnapManager.setIdleSnap --------------------------------------------

describe("SnapManager.setIdleSnap", () => {
  function _snap() {
    const scrollManager = { position: () => 0 };
    return new SnapManager(scrollManager, { a: { snapPositions: [0, 50, 100] } }, () => null);
  }

  it("arms the idle-snap timer by default", () => {
    const snap = _snap();
    snap.schedule("a");
    expect(snap._timer).not.toBeNull();
    snap.cancel();
  });

  it("does not arm the timer when idle-snap is off", () => {
    const snap = _snap();
    snap.setIdleSnap(false);
    snap.schedule("a");
    expect(snap._timer).toBeNull();
  });

  it("leaves the snap feature enabled (control/manual nav) when idle-snap is off", () => {
    const snap = _snap();
    snap.setIdleSnap(false);
    expect(snap.enabled).toBe(true); // dots + up()/down() stay available
  });

  it("re-arms after idle-snap is turned back on", () => {
    const snap = _snap();
    snap.setIdleSnap(false);
    snap.setIdleSnap(true);
    snap.schedule("a");
    expect(snap._timer).not.toBeNull();
    snap.cancel();
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

function _mockContainer() {
  // Minimal container stub: setRange touches classList; setPosition touches
  // style.setProperty + classList; syncScrollbar queries the scrollbar element.
  return {
    querySelector: () => null,
    classList: { add: () => {}, remove: () => {} },
    style: { setProperty: () => {} },
  };
}

describe("ScrollManager position <-> offset mapping", () => {
  function _mgr(reverse) {
    const cfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0, reverse } };
    const scrollbarEl = { clientHeight: 300, querySelector: () => null };
    const mgr = new ScrollManager(cfg, () => _mockContainer(), scrollbarEl);
    mgr.setRange("s1", 1000);
    return mgr;
  }

  const geo = { maxOffset: 200 };

  it("non-reverse: position 0 maps to offset 0", () => {
    expect(_mgr(false)._positionToOffset("s1", 0, geo)).toBeCloseTo(0);
  });

  it("non-reverse: position == range maps to maxOffset", () => {
    expect(_mgr(false)._positionToOffset("s1", 1000, geo)).toBeCloseTo(200);
  });

  it("non-reverse: half position maps to half offset", () => {
    expect(_mgr(false)._positionToOffset("s1", 500, geo)).toBeCloseTo(100);
  });

  it("reverse: position 0 maps to maxOffset (thumb at bottom)", () => {
    expect(_mgr(true)._positionToOffset("s1", 0, geo)).toBeCloseTo(200);
  });

  it("reverse: position == range maps to 0 (thumb at top)", () => {
    expect(_mgr(true)._positionToOffset("s1", 1000, geo)).toBeCloseTo(0);
  });

  it("reverse: half position maps to half offset (symmetric)", () => {
    expect(_mgr(true)._positionToOffset("s1", 500, geo)).toBeCloseTo(100);
  });

  it("non-reverse: _offsetToPosition is the inverse of _positionToOffset", () => {
    const mgr = _mgr(false);
    for (const p of [0, 250, 500, 750, 1000]) {
      const off = mgr._positionToOffset("s1", p, geo);
      expect(mgr._offsetToPosition("s1", off, geo)).toBeCloseTo(p);
    }
  });

  it("reverse: _offsetToPosition is the inverse of _positionToOffset", () => {
    const mgr = _mgr(true);
    for (const p of [0, 250, 500, 750, 1000]) {
      const off = mgr._positionToOffset("s1", p, geo);
      expect(mgr._offsetToPosition("s1", off, geo)).toBeCloseTo(p);
    }
  });

  it("returns 0 when range is 0", () => {
    const mgr = _mgr(false);
    mgr.setRange("s1", 0);
    expect(mgr._positionToOffset("s1", 100, geo)).toBe(0);
    expect(mgr._offsetToPosition("s1", 100, geo)).toBe(0);
  });

  it("returns 0 when maxOffset is 0", () => {
    const mgr = _mgr(false);
    expect(mgr._positionToOffset("s1", 100, { maxOffset: 0 })).toBe(0);
    expect(mgr._offsetToPosition("s1", 100, { maxOffset: 0 })).toBe(0);
  });
});

describe("ScrollManager.applyScrollDelta", () => {
  function _mgr(reverse) {
    const cfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0, reverse } };
    const scrollbarEl = { clientHeight: 300, querySelector: () => null };
    const mgr = new ScrollManager(cfg, () => _mockContainer(), scrollbarEl);
    mgr.setRange("s1", 1000);
    mgr.setPosition("s1", 500);
    return mgr;
  }

  it("non-reverse: positive delta increases position", () => {
    const mgr = _mgr(false);
    mgr.applyScrollDelta("s1", 100);
    expect(mgr.position("s1")).toBeCloseTo(600);
  });

  it("non-reverse: negative delta decreases position", () => {
    const mgr = _mgr(false);
    mgr.applyScrollDelta("s1", -100);
    expect(mgr.position("s1")).toBeCloseTo(400);
  });

  it("reverse: positive delta decreases position (sign flip)", () => {
    const mgr = _mgr(true);
    mgr.applyScrollDelta("s1", 100);
    expect(mgr.position("s1")).toBeCloseTo(400);
  });

  it("reverse: negative delta increases position (sign flip)", () => {
    const mgr = _mgr(true);
    mgr.applyScrollDelta("s1", -100);
    expect(mgr.position("s1")).toBeCloseTo(600);
  });

  it("clamps to [0, range] in either mode", () => {
    const fwd = _mgr(false);
    fwd.applyScrollDelta("s1", 9999);
    expect(fwd.position("s1")).toBe(1000);
    const rev = _mgr(true);
    rev.applyScrollDelta("s1", 9999);
    expect(rev.position("s1")).toBe(0);
  });
});

describe("ScrollManager.isReverse", () => {
  it("returns false when reverse is unset", () => {
    const mgr = new ScrollManager({ s1: {} }, () => null, null);
    expect(mgr.isReverse("s1")).toBe(false);
  });

  it("returns true when reverse is true", () => {
    const mgr = new ScrollManager({ s1: { reverse: true } }, () => null, null);
    expect(mgr.isReverse("s1")).toBe(true);
  });

  it("returns false for unknown slide", () => {
    const mgr = new ScrollManager({}, () => null, null);
    expect(mgr.isReverse("unknown")).toBe(false);
  });
});

describe("SnapManager up/down (visual direction)", () => {
  function _make(reverse, position) {
    const scrollCfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0, reverse } };
    const snapCfg = { s1: { snapPositions: [0, 100, 200, 300] } };
    const scrollbarEl = { clientHeight: 300, querySelector: () => null };
    const container = _mockContainer();
    const scrollMgr = new ScrollManager(scrollCfg, () => container, scrollbarEl);
    scrollMgr.setRange("s1", 1000);
    scrollMgr.setPosition("s1", position);
    const snapMgr = new SnapManager(scrollMgr, snapCfg, () => container);
    return { scrollMgr, snapMgr };
  }

  it("non-reverse: upTarget == prevTarget", () => {
    const { snapMgr } = _make(false, 150);
    expect(snapMgr.upTarget("s1")).toBe(100);
    expect(snapMgr.upTarget("s1")).toBe(snapMgr.prevTarget("s1"));
  });

  it("non-reverse: downTarget == nextTarget", () => {
    const { snapMgr } = _make(false, 150);
    expect(snapMgr.downTarget("s1")).toBe(200);
    expect(snapMgr.downTarget("s1")).toBe(snapMgr.nextTarget("s1"));
  });

  it("reverse: upTarget == nextTarget (visually up = larger scroll value)", () => {
    const { snapMgr } = _make(true, 150);
    expect(snapMgr.upTarget("s1")).toBe(200);
    expect(snapMgr.upTarget("s1")).toBe(snapMgr.nextTarget("s1"));
  });

  it("reverse: downTarget == prevTarget", () => {
    const { snapMgr } = _make(true, 150);
    expect(snapMgr.downTarget("s1")).toBe(100);
    expect(snapMgr.downTarget("s1")).toBe(snapMgr.prevTarget("s1"));
  });

  it("non-reverse: upTarget is null at position 0 (no prev)", () => {
    const { snapMgr } = _make(false, 0);
    expect(snapMgr.upTarget("s1")).toBeNull();
  });

  it("reverse: upTarget is null at max position (no next)", () => {
    const { snapMgr } = _make(true, 300);
    expect(snapMgr.upTarget("s1")).toBeNull();
  });
});

describe("ScrollManager.trackGeometry snap-aware thumb", () => {
  it("uses snapManager to determine numSnaps for thumb sizing", () => {
    const scrollCfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0 } };
    const snapCfg = { s1: { snapPositions: [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000] } };

    const scrollbarEl = { clientHeight: 300 };
    const container = { querySelector: () => null };

    const scrollMgr = new ScrollManager(scrollCfg, () => container, scrollbarEl);
    const snapMgr = new SnapManager(scrollMgr, snapCfg, () => container);
    scrollMgr.setSnapManager(snapMgr);

    const geo = scrollMgr.trackGeometry("s1");
    // 11 snaps, track 300px → cap = (2/3) * (300/11) ≈ 18.18
    const expected = (2 / 3) * (300 / 11);
    expect(geo.thumbHeight).toBeCloseTo(expected);
  });

  it("uses default thumb height when no snapManager is set", () => {
    const scrollCfg = { s1: { scrollRange: 1000, scrollSpeed: 1, initialScrollPosition: 0 } };

    const scrollbarEl = { clientHeight: 300 };

    const scrollMgr = new ScrollManager(scrollCfg, () => null, scrollbarEl);

    const geo = scrollMgr.trackGeometry("s1");
    expect(geo.thumbHeight).toBe(ScrollManager.DEFAULT_THUMB_HEIGHT);
  });
});

// ---- evaluatePiecewiseLinear --------------------------------------------

describe("evaluatePiecewiseLinear", () => {
  const kf = [[0, 0], [200, 1], [400, 1], [600, 0]];

  it("holds first value before first keyframe", () => {
    expect(evaluatePiecewiseLinear(kf, -100)).toBe(0);
  });

  it("holds last value after last keyframe", () => {
    expect(evaluatePiecewiseLinear(kf, 800)).toBe(0);
  });

  it("returns exact keyframe values", () => {
    expect(evaluatePiecewiseLinear(kf, 0)).toBe(0);
    expect(evaluatePiecewiseLinear(kf, 200)).toBe(1);
    expect(evaluatePiecewiseLinear(kf, 400)).toBe(1);
    expect(evaluatePiecewiseLinear(kf, 600)).toBe(0);
  });

  it("interpolates linearly between keyframes", () => {
    expect(evaluatePiecewiseLinear(kf, 100)).toBeCloseTo(0.5);
    expect(evaluatePiecewiseLinear(kf, 500)).toBeCloseTo(0.5);
    expect(evaluatePiecewiseLinear(kf, 300)).toBeCloseTo(1.0);
  });

  it("returns 1 for empty keyframes", () => {
    expect(evaluatePiecewiseLinear([], 50)).toBe(1);
  });
});

// ---- IdleTimer ------------------------------------------------------------

describe("IdleTimer", () => {
  function _target() {
    // Minimal classList stub.
    const classes = new Set();
    return {
      classList: {
        add: (c) => { classes.add(c); },
        remove: (c) => { classes.delete(c); },
        has: (c) => classes.has(c),
      },
      _classes: classes,
    };
  }

  it("starts without the idle class", () => {
    const t = _target();
    new IdleTimer(t, "idle", 100);
    expect(t.classList.has("idle")).toBe(false);
  });

  it("reset removes the class immediately if present", () => {
    const t = _target();
    t.classList.add("idle");
    const timer = new IdleTimer(t, "idle", 100);
    timer.reset();
    expect(t.classList.has("idle")).toBe(false);
  });

  it("reset adds the class after the delay", () => {
    vi.useFakeTimers();
    const t = _target();
    const timer = new IdleTimer(t, "idle", 500);
    timer.reset();
    expect(t.classList.has("idle")).toBe(false);
    vi.advanceTimersByTime(499);
    expect(t.classList.has("idle")).toBe(false);
    vi.advanceTimersByTime(1);
    expect(t.classList.has("idle")).toBe(true);
    vi.useRealTimers();
  });

  it("reset called twice restarts the delay", () => {
    vi.useFakeTimers();
    const t = _target();
    const timer = new IdleTimer(t, "idle", 500);
    timer.reset();
    vi.advanceTimersByTime(400);
    timer.reset();  // restart
    vi.advanceTimersByTime(400);  // total elapsed 800, but only 400 since restart
    expect(t.classList.has("idle")).toBe(false);
    vi.advanceTimersByTime(100);
    expect(t.classList.has("idle")).toBe(true);
    vi.useRealTimers();
  });

  it("clear cancels a pending add", () => {
    vi.useFakeTimers();
    const t = _target();
    const timer = new IdleTimer(t, "idle", 500);
    timer.reset();
    timer.clear();
    vi.advanceTimersByTime(1000);
    expect(t.classList.has("idle")).toBe(false);
    vi.useRealTimers();
  });

  it("clear removes the class if already added", () => {
    vi.useFakeTimers();
    const t = _target();
    const timer = new IdleTimer(t, "idle", 100);
    timer.reset();
    vi.advanceTimersByTime(100);
    expect(t.classList.has("idle")).toBe(true);
    timer.clear();
    expect(t.classList.has("idle")).toBe(false);
    vi.useRealTimers();
  });

  it("tolerates a null target", () => {
    const timer = new IdleTimer(null, "idle", 100);
    expect(() => timer.reset()).not.toThrow();
    expect(() => timer.clear()).not.toThrow();
  });
});

// Step-function support in evaluatePiecewiseLinear.
//
// The ImageSequenceElement "overlay" compositing mode emits keyframes with
// two entries at the same scroll position to express an instantaneous
// opacity step (1 → 0 at the instant the next frame reaches full opacity).
// The evaluator already handles this correctly via its early-outs and the
// "<=" loop comparison; these tests pin that behavior so it cannot
// regress silently.
describe("evaluatePiecewiseLinear — step functions", () => {
  it("returns post-step value when the step is at the end of the keyframes", () => {
    // Step at end: [..., (T, 1), (T, 0)]. At position >= T the second
    // early-out matches and returns the last keyframe's value.
    const kfs = [[0, 0], [10, 1], [10, 0]];
    expect(evaluatePiecewiseLinear(kfs, 10)).toBe(0);
    expect(evaluatePiecewiseLinear(kfs, 10.5)).toBe(0);
  });

  it("returns pre-step value at exactly the step and post-step value just past it", () => {
    // Step in the middle: [..., (T, 1), (T, 0), ...].
    const kfs = [[0, 0], [10, 1], [10, 0], [20, 0]];
    // At position 10 exactly: loop matches the pre-step keyframe → 1.
    expect(evaluatePiecewiseLinear(kfs, 10)).toBe(1);
    // Just past 10: loop skips both tied keyframes naturally → 0.
    expect(evaluatePiecewiseLinear(kfs, 10.0001)).toBeCloseTo(0, 5);
  });

  it("interpolates correctly on either side of a step", () => {
    const kfs = [[0, 0], [10, 1], [10, 0], [20, 0]];
    // Mid-ramp before the step: linear interpolation 0 → 1.
    expect(evaluatePiecewiseLinear(kfs, 5)).toBeCloseTo(0.5, 5);
    // Past the step: flat 0.
    expect(evaluatePiecewiseLinear(kfs, 15)).toBe(0);
  });

  it("does not divide by zero when tied keyframes appear", () => {
    // Critical property: the loop can never land on a tied pair as
    // (x0, x1), so x1 - x0 is never 0. Spot-check around several step
    // locations.
    const kfs = [[0, 0], [10, 1], [10, 0], [20, 1], [20, 0], [30, 0]];
    for (const pos of [-1, 0, 5, 10, 15, 20, 25, 30, 35]) {
      const y = evaluatePiecewiseLinear(kfs, pos);
      expect(Number.isFinite(y)).toBe(true);
    }
  });
});
