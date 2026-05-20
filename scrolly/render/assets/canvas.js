/*
 * scrolly canvas — Layer A navigation.
 *
 * Reads the embedded #scrolly-deck JSON, listens for arrow keys, resolves a
 * navigation target via the strict per-side rule + linearization, and
 * updates the canvas transform or pulses a no-target glow. Also handles
 * the slide ↔ deck view toggle (zoom-out control, click-slide-to-focus,
 * Escape to return) and delegates clicks on the edge-arrow affordances.
 *
 * View state is a single (selected_slide, zoom_level) tuple. setView() is
 * the one authoritative mutation: it writes three CSS custom properties
 * feeding the unified transform formula in canvas.css, toggles the body
 * view-* class (view-slide / view-deck / view-transitioning), and
 * rebuilds the navigation layer's edge arrows if selected_slide changed.
 * Every input handler routes through setView() or toggleView().
 */

(function (exports) {
  "use strict";

  // ---- CanvasGeometry (pure — no DOM access) --------------------------------

  class CanvasGeometry {
    static DECK_MARGIN_FACTOR = 0.85;
    static FAN_ARROW_SIZE_PX = 48;
    static FAN_MIN_SPACING_PX = 2 * CanvasGeometry.FAN_ARROW_SIZE_PX;

    static GAP = 10;
    static LABEL_EXTRA = 4;
    static CONTROL_FRACTION = 0.6;
    static CONTROL_MAX = 1.0;

    constructor({ slides, edges, groups, fanSpacingFactor }) {
      this._slides = slides;
      this._edges = edges || [];
      this._groups = groups || [];
      this._fanSpacingFactor = fanSpacingFactor;

      // Bounding box of occupied (col, row) cells. Slide positions stay
      // absolute everywhere — only the deck-view fit/centre math reads
      // the bounding box so an off-origin deck (leftmost/topmost slide
      // not at column 0 / row 0) centres on its occupied region instead
      // of on [0, maxCol] × [0, maxRow].
      const positions = Object.values(slides);
      if (positions.length === 0) {
        this._bbox = { minX: 0, minY: 0, maxX: -1, maxY: -1 };
      } else {
        this._bbox = {
          minX: Math.min(...positions.map((p) => p[0])),
          minY: Math.min(...positions.map((p) => p[1])),
          maxX: Math.max(...positions.map((p) => p[0])),
          maxY: Math.max(...positions.map((p) => p[1])),
        };
      }

      this._colGap = 0;
      this._labelRows = this._computeLabelRows();
      this._rowGaps = this._computeRowGaps();
      this._dvmaxToRow = 0;
    }

    get cols() { return Math.max(0, this._bbox.maxX - this._bbox.minX + 1); }
    get rows() { return Math.max(0, this._bbox.maxY - this._bbox.minY + 1); }
    get vw() { return this._vw; }
    get vh() { return this._vh; }

    slidePosition(slideId) {
      const p = this._slides[slideId];
      return p ? { x: p[0], y: p[1] } : null;
    }

    slideGapOffset(slideId) {
      const p = this._slides[slideId];
      if (!p) return null;
      return { gapX: p[0] * CanvasGeometry.GAP, gapY: this._cumulativeRowGap(p[1]) };
    }

    slideAbstractPos(slideId) {
      const p = this._slides[slideId];
      if (!p) return null;
      return {
        x: p[0] * (1 + this._colGap),
        y: p[1] + this._cumulativeRowGap(p[1]) * this._dvmaxToRow,
      };
    }

    refresh(viewportWidth, viewportHeight) {
      this._vw = viewportWidth;
      this._vh = viewportHeight;
      const vmax = Math.max(viewportWidth, viewportHeight);
      this._colGap = CanvasGeometry.GAP / 100 * vmax / viewportWidth;
      this._dvmaxToRow = vmax / (100 * viewportHeight);
    }

    effectiveGridSize() {
      const { minX, minY, maxX, maxY } = this._bbox;
      if (maxX < minX || maxY < minY) return { cols: 0, rows: 0 };
      const colSpan = maxX - minX + 1;
      const rowSpan = maxY - minY + 1;
      let rowGapSum = this._topRowGapDvmax(minY);
      for (let i = minY + 1; i <= maxY; i++) rowGapSum += this._rowGaps[i];
      rowGapSum *= this._dvmaxToRow;
      return {
        cols: colSpan + Math.max(0, colSpan - 1) * this._colGap,
        rows: rowSpan + rowGapSum,
      };
    }

    fitAllScale() {
      const { cols, rows } = this.effectiveGridSize();
      if (cols === 0 || rows === 0) return 1;
      return Math.min(1 / cols, 1 / rows) * CanvasGeometry.DECK_MARGIN_FACTOR;
    }

    deckCenter() {
      const { minX, minY, maxX, maxY } = this._bbox;
      if (maxX < minX || maxY < minY) return { x: 0, y: 0 };
      const leftX = minX * (1 + this._colGap);
      const rightX = maxX * (1 + this._colGap) + 1;
      // Slide top edge of the topmost occupied row, with the label-tab
      // extension subtracted to land at the visible top of the deck.
      const slideTopY = minY + this._cumulativeRowGap(minY) * this._dvmaxToRow;
      const topY = slideTopY - this._topRowGapDvmax(minY) * this._dvmaxToRow;
      const bottomY = maxY + this._cumulativeRowGap(maxY) * this._dvmaxToRow + 1;
      return { x: (leftX + rightX) / 2, y: (topY + bottomY) / 2 };
    }

    fanOffset(side, fanIndex, fanSize) {
      if (fanSize <= 1) return 0.5;
      const sideLen = (side === "top" || side === "bottom") ? this._vw : this._vh;
      if (sideLen <= 0) return 0.5;
      const spacing = Math.max(this._fanSpacingFactor * sideLen, CanvasGeometry.FAN_MIN_SPACING_PX);
      return 0.5 + (fanIndex - (fanSize - 1) / 2) * spacing / sideLen;
    }

    cellBounds(minX, minY, maxX, maxY, padding) {
      const vw = this._vw;
      const vh = this._vh;
      const vmax = Math.max(vw, vh);

      const topPad = padding.top * vmax;
      const sidePad = padding.side * vmax;
      const bottomPad = padding.bottom * vmax;

      const minGapY = this._cumulativeRowGap(minY) * this._dvmaxToRow;
      const maxGapY = this._cumulativeRowGap(maxY) * this._dvmaxToRow;

      const left = (minX + minX * this._colGap) * vw - sidePad;
      const top = (minY + minGapY) * vh - topPad;
      const right = (maxX + maxX * this._colGap + 1) * vw + sidePad;
      const bottom = (maxY + maxGapY + 1) * vh + bottomPad;

      return { left, top, width: right - left, height: bottom - top, topPad };
    }

    get edges() { return this._edges; }
    get groups() { return this._groups; }
    rowGapAbove(row) { return row < this._rowGaps.length ? this._rowGaps[row] : 0; }

    groupBounds(group) {
      const xs = group.slide_ids.map((id) => this._slides[id][0]);
      const ys = group.slide_ids.map((id) => this._slides[id][1]);
      return {
        minX: Math.min(...xs),
        minY: Math.min(...ys),
        maxX: Math.max(...xs),
        maxY: Math.max(...ys),
      };
    }

    _computeLabelRows() {
      // Set of absolute row indices that carry a group label (the
      // minimum row of each group). Each labelled row gets extra height
      // for its tab via _computeRowGaps + _topRowGapDvmax.
      const set = new Set();
      for (const group of this._groups) {
        const ys = group.slide_ids.map((id) => this._slides[id][1]);
        set.add(Math.min(...ys));
      }
      return set;
    }

    _computeRowGaps() {
      // _rowGaps is indexed by absolute row number, so its length must
      // reach maxY + 1 even when the deck doesn't start at row 0 —
      // _cumulativeRowGap(r) traverses gaps[0..r] regardless of minY.
      const { maxY } = this._bbox;
      if (maxY < 0) return [];
      const gaps = [];
      for (let i = 0; i <= maxY; i++) {
        if (i === 0) {
          gaps.push(this._labelRows.has(0) ? CanvasGeometry.LABEL_EXTRA : 0);
        } else {
          gaps.push(this._labelRows.has(i)
            ? CanvasGeometry.GAP + CanvasGeometry.LABEL_EXTRA
            : CanvasGeometry.GAP);
        }
      }
      return gaps;
    }

    _topRowGapDvmax(row) {
      // Effective gap above the TOPMOST occupied row, in dvmax units.
      // Only the LABEL_EXTRA portion is meaningful — the inter-row GAP
      // is empty space when the row above is unoccupied, so it doesn't
      // contribute to the deck's visible bounding box.
      return this._labelRows.has(row) ? CanvasGeometry.LABEL_EXTRA : 0;
    }

    _cumulativeRowGap(row) {
      let total = 0;
      for (let i = 0; i <= row; i++) total += this._rowGaps[i];
      return total;
    }

    attachmentPoint(gridX, gridY, side, fanOff) {
      const ox = gridX * this._colGap;
      const oy = this._cumulativeRowGap(gridY) * this._dvmaxToRow;
      let x, y;
      if (side === "top")         { x = gridX + ox + fanOff; y = gridY + oy; }
      else if (side === "bottom") { x = gridX + ox + fanOff; y = gridY + oy + 1.0; }
      else if (side === "left")   { x = gridX + ox;          y = gridY + oy + fanOff; }
      else                        { x = gridX + ox + 1.0;    y = gridY + oy + fanOff; }
      return { x, y };
    }

    controlPoint(selfX, selfY, otherX, otherY, side) {
      let delta;
      if (side === "left" || side === "right") {
        delta = Math.abs(otherX - selfX);
      } else {
        delta = Math.abs(otherY - selfY);
      }
      const offset = Math.min(delta * CanvasGeometry.CONTROL_FRACTION, CanvasGeometry.CONTROL_MAX);
      const nx = side === "left" ? -1 : side === "right" ? 1 : 0;
      const ny = side === "top" ? -1 : side === "bottom" ? 1 : 0;
      return { x: selfX + nx * offset, y: selfY + ny * offset };
    }

    buildPath(edge) {
      const aPos = this._slides[edge.a_slide];
      const bPos = this._slides[edge.b_slide];
      if (!aPos || !bPos) return null;

      const aFan = this.fanOffset(edge.a_side, edge.a_fan_index, edge.a_fan_size);
      const bFan = this.fanOffset(edge.b_side, edge.b_fan_index, edge.b_fan_size);

      const a = this.attachmentPoint(aPos[0], aPos[1], edge.a_side, aFan);
      const b = this.attachmentPoint(bPos[0], bPos[1], edge.b_side, bFan);

      const c1 = this.controlPoint(a.x, a.y, b.x, b.y, edge.a_side);
      const c2 = this.controlPoint(b.x, b.y, a.x, a.y, edge.b_side);

      const r = (n) => n.toFixed(4);
      return "M " + r(a.x) + " " + r(a.y) + " C " +
             r(c1.x) + " " + r(c1.y) + ", " +
             r(c2.x) + " " + r(c2.y) + ", " +
             r(b.x) + " " + r(b.y);
    }

  }

  // ---- ScrollManager --------------------------------------------------------

  class ScrollManager {
    static DEFAULT_THUMB_HEIGHT = 60;
    static MIN_THUMB_HEIGHT = 10;

    static computeThumbHeight(baseHeight, trackHeight, numSnaps) {
      let h = baseHeight;
      if (numSnaps > 1) {
        h = Math.min(h, (2 / 3) * (trackHeight / numSnaps));
      }
      h = Math.max(h, ScrollManager.MIN_THUMB_HEIGHT);
      h = Math.min(h, trackHeight);
      return h;
    }

    constructor(scrollConfig, containerFn, scrollbarEl) {
      this._config = scrollConfig;
      this._containerFn = containerFn;
      this._scrollbarEl = scrollbarEl;
      this._positions = new Map();
      this._ranges = new Map();
      this._drag = null;
      this._observer = null;
      this._snapManager = null;
      this.onPositionChange = null;
    }

    setSnapManager(snapManager) { this._snapManager = snapManager; }

    position(slideId) { return this._positions.get(slideId) || 0; }
    range(slideId) { return this._ranges.get(slideId) || 0; }
    scrollSpeed(slideId) { return (this._config[slideId] && this._config[slideId].scrollSpeed) || 1.0; }
    isReverse(slideId) { return !!(this._config[slideId] && this._config[slideId].reverse); }

    // ---- position <-> track-offset mapping -----------------------------
    // The scrollbar thumb's top-edge offset on the track and the slide's
    // scroll value are linked by a single mapping. Non-reverse mode maps
    // position=0 to offset=0 (thumb at top); reverse mode maps position=0
    // to offset=maxOffset (thumb at bottom). Both helpers handle the flip
    // so every call site can stay direction-agnostic. The same formula
    // applies to deltas: dragging the thumb by dy pixels translates to the
    // same dPosition via `_offsetToPosition(slideId, dy, geo)` (with the
    // appropriate sign in reverse mode).
    _positionToOffset(slideId, position, geo) {
      const range = this._ranges.get(slideId) || 0;
      if (range <= 0 || geo.maxOffset <= 0) return 0;
      const base = (position / range) * geo.maxOffset;
      return this.isReverse(slideId) ? geo.maxOffset - base : base;
    }
    _offsetToPosition(slideId, offset, geo) {
      const range = this._ranges.get(slideId) || 0;
      if (range <= 0 || geo.maxOffset <= 0) return 0;
      const base = this.isReverse(slideId) ? geo.maxOffset - offset : offset;
      return (base / geo.maxOffset) * range;
    }

    applyScrollDelta(slideId, delta) {
      const sign = this.isReverse(slideId) ? -1 : 1;
      this.setPosition(slideId, this.position(slideId) + sign * delta);
    }

    setPosition(slideId, position) {
      const range = this._ranges.get(slideId) || 0;
      const clamped = Math.max(0, Math.min(range, position));
      this._positions.set(slideId, clamped);
      const container = this._containerFn(slideId);
      if (!container) return;
      container.style.setProperty("--scroll-position", String(clamped));
      this.syncScrollbar(slideId);
      if (this.onPositionChange) this.onPositionChange(slideId);
    }

    setRange(slideId, range) {
      this._ranges.set(slideId, range);
      const container = this._containerFn(slideId);
      if (!container) return;
      if (range > 0) {
        container.classList.add("has-scroll");
      } else {
        container.classList.remove("has-scroll");
      }
      const current = this._positions.get(slideId);
      if (current !== undefined) {
        this.setPosition(slideId, current);
      } else {
        const cfg = this._config[slideId];
        this.setPosition(slideId, (cfg && cfg.initialScrollPosition) || 0);
      }
    }

    trackGeometry(slideId) {
      const trackEl = this._scrollbarEl;
      if (!trackEl) return null;
      const trackHeight = trackEl.clientHeight;
      if (trackHeight <= 0) return null;

      const container = this._containerFn(slideId);
      const cfg = this._config[slideId];
      let thumbHeight;
      if (cfg && cfg.scrollRange === null) {
        if (!container) return null;
        const subcanvas = container.querySelector(".subcanvas");
        const chunk = container.querySelector(".chunk");
        if (!subcanvas || !chunk) return null;
        const ratio = subcanvas.clientHeight / chunk.scrollHeight;
        thumbHeight = Math.max(ScrollManager.DEFAULT_THUMB_HEIGHT, trackHeight * ratio);
      } else {
        thumbHeight = ScrollManager.DEFAULT_THUMB_HEIGHT;
      }
      const numSnaps = this._snapManager ? this._snapManager.getNumSnaps(slideId) : 0;
      thumbHeight = ScrollManager.computeThumbHeight(thumbHeight, trackHeight, numSnaps);
      const maxOffset = trackHeight - thumbHeight;
      return { trackEl, trackHeight, thumbHeight, maxOffset };
    }

    syncScrollbar(slideId) {
      const geo = this.trackGeometry(slideId);
      if (!geo) return;
      const thumb = this._scrollbarEl.querySelector(".slide-scrollbar-thumb");
      if (!thumb) return;

      const position = this._positions.get(slideId) || 0;
      const offset = this._positionToOffset(slideId, position, geo);

      thumb.style.height = geo.thumbHeight + "px";
      thumb.style.top = offset + "px";
    }

    syncVisibility(slideId, zoomLevel) {
      if (!this._scrollbarEl) return;
      const range = this._ranges.get(slideId) || 0;
      this._scrollbarEl.style.display = (zoomLevel === 1 && range > 0) ? "block" : "none";
    }

    init(canvas) {
      this._observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const container = entry.target.closest(".slide-container");
          if (!container) continue;
          const slideId = container.dataset.id;
          const cfg = this._config[slideId];
          if (!cfg || cfg.scrollRange !== null) continue;
          const subcanvas = container.querySelector(".subcanvas");
          const chunk = container.querySelector(".chunk");
          if (!subcanvas || !chunk) continue;
          const range = Math.max(0, chunk.scrollHeight - subcanvas.clientHeight);
          this.setRange(slideId, range);
        }
      });

      const containers = canvas.querySelectorAll(".slide-container");
      containers.forEach((container) => {
        const slideId = container.dataset.id;
        const cfg = this._config[slideId];
        if (!cfg) return;
        const initial = cfg.initialScrollPosition || 0;
        if (cfg.scrollRange === null) {
          this._positions.set(slideId, initial);
          const chunk = container.querySelector(".chunk");
          if (chunk) this._observer.observe(chunk);
        } else {
          this.setRange(slideId, cfg.scrollRange);
          this.setPosition(slideId, initial);
        }
      });
    }

    startDrag(e, selectedSlide) {
      const target = e.target;
      if (!target.classList || !target.classList.contains("slide-scrollbar-thumb")) return false;
      if (!selectedSlide) return false;
      e.preventDefault();
      if ((this._ranges.get(selectedSlide) || 0) <= 0) return false;

      const geo = this.trackGeometry(selectedSlide);
      if (!geo) return false;

      const startPosition = this._positions.get(selectedSlide) || 0;
      this._drag = {
        slideId: selectedSlide,
        startY: e.clientY,
        startOffset: this._positionToOffset(selectedSlide, startPosition, geo),
        geo,
      };
      target.classList.add("dragging");
      return true;
    }

    moveDrag(e) {
      if (!this._drag) return;
      if (this._drag.geo.maxOffset <= 0) return;
      const dy = e.clientY - this._drag.startY;
      const newOffset = this._drag.startOffset + dy;
      const newPosition = this._offsetToPosition(this._drag.slideId, newOffset, this._drag.geo);
      this.setPosition(this._drag.slideId, newPosition);
    }

    endDrag() {
      if (!this._drag) return null;
      const slideId = this._drag.slideId;
      document.querySelectorAll(".slide-scrollbar-thumb.dragging").forEach((el) => {
        el.classList.remove("dragging");
      });
      this._drag = null;
      return slideId;
    }

    get isDragging() { return this._drag !== null; }
  }

  // ---- SnapManager ---------------------------------------------------------

  class SnapManager {
    static IDLE_MS = 500;
    static DURATION_MS = 300;

    constructor(scrollManager, snapConfig, containerFn) {
      this._scrollManager = scrollManager;
      this._config = snapConfig;
      this._containerFn = containerFn;
      this._enabled = true;
      this._timer = null;
      this._anim = null;
      this._animTarget = null;
      this._controlEl = null;
      this._prevBtn = null;
      this._nextBtn = null;
      this._toggleBtn = null;
      this._selectedSlide = null;
    }

    get enabled() { return this._enabled; }
    get isControlVisible() { return this._controlEl && this._controlEl.style.display !== "none"; }

    initControl(controlEl) {
      this._controlEl = controlEl;
      if (!controlEl) return;
      this._prevBtn = controlEl.querySelector(".snap-control-prev");
      this._nextBtn = controlEl.querySelector(".snap-control-next");
      this._toggleBtn = controlEl.querySelector(".snap-control-toggle");

      if (this._prevBtn) {
        this._prevBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.up();
          this._prevBtn.blur();
        });
      }
      if (this._nextBtn) {
        this._nextBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.down();
          this._nextBtn.blur();
        });
      }
      if (this._toggleBtn) {
        this._toggleBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.toggle();
          this._toggleBtn.blur();
        });
      }
    }

    getNumSnaps(slideId) {
      const cfg = this._config[slideId];
      if (!cfg || !cfg.snapPositions) return 0;
      return cfg.snapPositions.length;
    }

    _snapsFor(slideId) {
      const cfg = this._config[slideId];
      if (!cfg || !cfg.snapPositions || cfg.snapPositions.length === 0) return null;
      return cfg.snapPositions;
    }

    schedule(slideId) {
      this.cancel();
      if (!this._enabled) return;
      if (!this._snapsFor(slideId)) return;
      this._timer = setTimeout(() => { this._timer = null; this._animateToNearest(slideId); }, SnapManager.IDLE_MS);
    }

    cancel() {
      if (this._timer !== null) { clearTimeout(this._timer); this._timer = null; }
      if (this._anim !== null) { cancelAnimationFrame(this._anim); this._anim = null; }
      this._animTarget = null;
    }

    finishIfRunning(slideId) {
      if (this._anim !== null && this._animTarget !== null) {
        cancelAnimationFrame(this._anim);
        this._anim = null;
        this._scrollManager.setPosition(slideId, this._animTarget);
        this._animTarget = null;
      }
    }

    animateTo(slideId, target) {
      const current = this._scrollManager.position(slideId);
      if (Math.abs(target - current) < 0.5) {
        this._scrollManager.setPosition(slideId, target);
        this._animTarget = null;
        this._syncChevronState();
        return;
      }

      this._animTarget = target;
      const start = current;
      const t0 = performance.now();
      const step = (now) => {
        const elapsed = now - t0;
        const t = Math.min(1, elapsed / SnapManager.DURATION_MS);
        const ease = SnapManager.easeOutQuad(t);
        this._scrollManager.setPosition(slideId, start + (target - start) * ease);
        if (t < 1) {
          this._anim = requestAnimationFrame(step);
        } else {
          this._anim = null;
          this._animTarget = null;
          this._syncChevronState();
        }
      };
      this._anim = requestAnimationFrame(step);
    }

    _animateToNearest(slideId) {
      const snaps = this._snapsFor(slideId);
      if (!snaps) return;
      const current = this._scrollManager.position(slideId);
      this.animateTo(slideId, SnapManager._nearest(current, snaps));
    }

    // `prev`/`next` are the semantic primitives (lower/higher scroll value);
    // `up`/`down` are the visual layer used by chevrons and shift+arrow,
    // dispatching through the slide's reverse flag so that visually-up
    // input always moves the thumb visually up regardless of the scroll
    // coordinate system.
    prev() {
      if (!this._enabled || !this._selectedSlide) return;
      this.finishIfRunning(this._selectedSlide);
      const target = this.prevTarget(this._selectedSlide);
      if (target === null) return;
      this.cancel();
      this.animateTo(this._selectedSlide, target);
    }

    next() {
      if (!this._enabled || !this._selectedSlide) return;
      this.finishIfRunning(this._selectedSlide);
      const target = this.nextTarget(this._selectedSlide);
      if (target === null) return;
      this.cancel();
      this.animateTo(this._selectedSlide, target);
    }

    up() {
      if (this._scrollManager.isReverse(this._selectedSlide)) this.next();
      else this.prev();
    }

    down() {
      if (this._scrollManager.isReverse(this._selectedSlide)) this.prev();
      else this.next();
    }

    upTarget(slideId) {
      return this._scrollManager.isReverse(slideId)
        ? this.nextTarget(slideId)
        : this.prevTarget(slideId);
    }

    downTarget(slideId) {
      return this._scrollManager.isReverse(slideId)
        ? this.prevTarget(slideId)
        : this.nextTarget(slideId);
    }

    toggle() {
      this._setEnabled(!this._enabled, true);
    }

    onScrollPositionChanged(slideId) {
      if (slideId === this._selectedSlide) this._syncChevronState();
    }

    _setEnabled(enabled, animate) {
      this._enabled = enabled;
      this._applyEnabledState();
      if (enabled) {
        this._syncChevronState();
        if (animate && this._selectedSlide) this.schedule(this._selectedSlide);
      } else {
        this.cancel();
      }
    }

    syncControl(selectedSlide, zoomLevel) {
      this._selectedSlide = selectedSlide;
      if (!this._controlEl) return;
      if (zoomLevel !== 1) {
        this._controlEl.style.display = "none";
        return;
      }
      const hasSnaps = !!this._snapsFor(selectedSlide);
      this._controlEl.style.display = hasSnaps ? "flex" : "none";
      this._applyEnabledState();
      if (hasSnaps) {
        this._syncChevronState();
        if (this._enabled) this.schedule(selectedSlide);
      }
    }

    _applyEnabledState() {
      if (!this._controlEl) return;
      const scrollbarEl = this._scrollManager._scrollbarEl;
      if (this._enabled) {
        this._controlEl.classList.remove("snap-off");
        if (scrollbarEl) scrollbarEl.classList.remove("snap-disabled");
      } else {
        this._controlEl.classList.add("snap-off");
        if (scrollbarEl) scrollbarEl.classList.add("snap-disabled");
      }
    }

    _syncChevronState() {
      if (!this._prevBtn || !this._nextBtn) return;
      const hasUp = this.upTarget(this._selectedSlide) !== null;
      const hasDown = this.downTarget(this._selectedSlide) !== null;
      this._prevBtn.disabled = !hasUp;
      this._prevBtn.style.opacity = hasUp ? "" : "0.3";
      this._nextBtn.disabled = !hasDown;
      this._nextBtn.style.opacity = hasDown ? "" : "0.3";
    }

    prevTarget(slideId) {
      const snaps = this._snapsFor(slideId);
      if (!snaps) return null;
      const current = this._scrollManager.position(slideId);
      for (let i = snaps.length - 1; i >= 0; i--) {
        if (snaps[i] < current - 0.5) return snaps[i];
      }
      return null;
    }

    nextTarget(slideId) {
      const snaps = this._snapsFor(slideId);
      if (!snaps) return null;
      const current = this._scrollManager.position(slideId);
      for (let i = 0; i < snaps.length; i++) {
        if (snaps[i] > current + 0.5) return snaps[i];
      }
      return null;
    }

    syncDots(slideId) {
      const trackEl = this._scrollManager._scrollbarEl;
      if (!trackEl) return;
      trackEl.querySelectorAll(".slide-scrollbar-snap").forEach((el) => el.remove());
      const snaps = this._snapsFor(slideId);
      if (!snaps) return;
      if (this._scrollManager.range(slideId) <= 0) return;
      const geo = this._scrollManager.trackGeometry(slideId);
      if (!geo) return;
      for (const pos of snaps) {
        const dot = document.createElement("div");
        dot.className = "slide-scrollbar-snap";
        const offset = this._scrollManager._positionToOffset(slideId, pos, geo);
        dot.style.top = geo.thumbHeight / 2 + offset + "px";
        geo.trackEl.appendChild(dot);
      }
    }

    static easeOutQuad(t) { return 1 - (1 - t) * (1 - t); }

    static _nearest(position, snaps) {
      let best = snaps[0];
      let bestDist = Math.abs(position - best);
      for (let i = 1; i < snaps.length; i++) {
        const d = Math.abs(position - snaps[i]);
        if (d < bestDist) { best = snaps[i]; bestDist = d; }
      }
      return best;
    }
  }

  // ---- EdgeArrows -----------------------------------------------------------

  const _EDGE_SIDES = ["top", "bottom", "left", "right"];
  const _ARROW_SVG =
    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2.5" fill="none" ' +
    'stroke-linecap="round" stroke-linejoin="round"/></svg>';

  class EdgeArrows {
    constructor(geo, edgeData, navLayer) {
      this._geometry = geo;
      this._edgesBySide = edgeData.edgesBySide;
      this._titles = edgeData.titles;
      this._navLayer = navLayer;
    }

    edgesForSide(slideId, side) {
      const slideEdges = this._edgesBySide[slideId];
      if (!slideEdges) return [];
      return slideEdges[side] || [];
    }

    slideTitle(slideId) {
      return this._titles[slideId] || slideId;
    }

    computeArrowData(selectedSlide) {
      const slideEdges = this._edgesBySide[selectedSlide];
      if (!slideEdges) return [];
      const result = [];
      for (const side of _EDGE_SIDES) {
        for (const edge of (slideEdges[side] || [])) {
          result.push({
            side,
            target: edge.target,
            title: this._titles[edge.target] || edge.target,
            fanIndex: edge.fan_index,
            fanSize: edge.fan_size,
            fanOffset: this._geometry.fanOffset(side, edge.fan_index, edge.fan_size),
          });
        }
      }
      return result;
    }

    rebuild(selectedSlide) {
      this._renderArrows(this.computeArrowData(selectedSlide));
    }

    _renderArrows(data) {
      const existing = this._navLayer.querySelectorAll(".edge-arrow");
      existing.forEach((el) => el.remove());
      for (const arrow of data) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "edge-arrow edge-arrow-" + arrow.side;
        btn.dataset.target = arrow.target;
        btn.dataset.title = arrow.title;
        btn.dataset.side = arrow.side;
        btn.dataset.fanIndex = String(arrow.fanIndex);
        btn.dataset.fanSize = String(arrow.fanSize);
        btn.style.setProperty("--fan-offset", arrow.fanOffset);
        btn.setAttribute("aria-label", "Go to " + arrow.title);
        btn.innerHTML = _ARROW_SVG;
        this._navLayer.appendChild(btn);
      }
    }

    refreshFanOffsets() {
      const arrows = this._navLayer.querySelectorAll(".edge-arrow");
      arrows.forEach((btn) => {
        const side = btn.dataset.side;
        const fanIndex = parseInt(btn.dataset.fanIndex, 10);
        const fanSize = parseInt(btn.dataset.fanSize, 10);
        if (!side || isNaN(fanIndex) || isNaN(fanSize)) return;
        btn.style.setProperty("--fan-offset",
          this._geometry.fanOffset(side, fanIndex, fanSize));
      });
    }

    pulseGlow(side) {
      const stale = this._navLayer.querySelector(".no-target-glow");
      if (stale) stale.remove();
      const el = document.createElement("div");
      el.className = "no-target-glow " + side;
      this._navLayer.appendChild(el);
      void el.offsetWidth;
      el.classList.add("pulse");
      el.addEventListener("animationend", () => el.remove(), { once: true });
    }

    pulseDisambiguation(side) {
      const stale = this._navLayer.querySelector(".disambiguation-glow");
      if (stale) stale.remove();
      const el = document.createElement("div");
      el.className = "disambiguation-glow " + side;
      this._navLayer.appendChild(el);
      void el.offsetWidth;
      el.classList.add("pulse");
      const arrows = this._navLayer.querySelectorAll(".edge-arrow-" + side);
      arrows.forEach((a) => {
        a.classList.remove("arrow-fan-pulse");
        void a.offsetWidth;
        a.classList.add("arrow-fan-pulse");
      });
      el.addEventListener(
        "animationend",
        () => {
          el.remove();
          arrows.forEach((a) => a.classList.remove("arrow-fan-pulse"));
        },
        { once: true },
      );
    }
  }

  // ---- GroupLayout ----------------------------------------------------------

  const GROUP_PADDING = { top: 0.03, side: 0.03, bottom: 0.03 };
  const TAB_H_PAD = 0.03;
  const TAB_PROTRUSION = 0.04;

  class GroupLayout {
    constructor(geo, canvasEl) {
      this._geometry = geo;
      this._canvas = canvasEl;
      this._elements = [];
      this._labelWidths = [];
    }

    init() {
      for (const group of this._geometry.groups) {
        const ns = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(ns, "svg");
        svg.setAttribute("class", "slide-group");
        const path = document.createElementNS(ns, "path");
        path.setAttribute("class", "slide-group-bg");
        if (group.color) path.style.fill = group.color;
        svg.appendChild(path);
        const label = document.createElement("span");
        label.className = "slide-group-label";
        label.textContent = group.label;
        this._elements.push({ group, svg, path, label });
      }
      const firstSlideContainer = this._canvas.querySelector(".slide-container");
      for (const { svg } of this._elements) {
        this._canvas.insertBefore(svg, firstSlideContainer);
      }
      for (const { label } of this._elements) {
        this._canvas.appendChild(label);
      }
    }

    _measureLabels() {
      // Use offsetWidth (CSS layout width, transform-immune) rather than
      // getBoundingClientRect().width (post-transform screen width). The
      // labels live inside the canvas, which carries a transform whose scale
      // factor varies with view state and viewport size; tabW is consumed
      // downstream as a canvas-coordinate value that the same transform is
      // applied to at paint time, so feeding it a post-transform measurement
      // would re-apply the scale and shrink the tab flat-top below the label
      // text envelope.
      this._labelWidths = this._elements.map(({ label }) =>
        label.offsetWidth
      );
    }

    computeLayout() {
      const geo = this._geometry;
      const vmax = Math.max(geo.vw, geo.vh);
      const tabHPad = TAB_H_PAD * vmax;
      const tabH = TAB_PROTRUSION * vmax;
      const r = Math.min(geo.vw, geo.vh) * 0.03;

      return geo.groups.map((group, i) => {
        const bounds = geo.groupBounds(group);
        const body = geo.cellBounds(bounds.minX, bounds.minY, bounds.maxX, bounds.maxY, GROUP_PADDING);
        const labelW = this._labelWidths[i] || 0;
        const tabW = Math.min(labelW + 2 * tabHPad, body.width - 2 * tabH);

        return {
          label: group.label,
          svgLeft: body.left,
          svgTop: body.top - tabH,
          svgWidth: body.width,
          svgHeight: body.height + tabH,
          path: GroupLayout.buildTabPath(body.width, body.height, tabW, tabH, r),
          labelX: body.left + body.width / 2,
          labelY: body.top + (body.topPad - tabH) / 2,
        };
      });
    }

    refresh() {
      this._measureLabels();
      const data = this.computeLayout();
      this._render(data);
    }

    _render(data) {
      for (let i = 0; i < this._elements.length; i++) {
        const { svg, path, label } = this._elements[i];
        const d = data[i];
        svg.style.left = d.svgLeft + "px";
        svg.style.top = d.svgTop + "px";
        svg.style.width = d.svgWidth + "px";
        svg.style.height = d.svgHeight + "px";
        svg.setAttribute("viewBox", "0 0 " + d.svgWidth + " " + d.svgHeight);
        path.setAttribute("d", d.path);
        label.style.left = d.labelX + "px";
        label.style.top = d.labelY + "px";
      }
    }

    static buildTabPath(bodyW, bodyH, tabW, tabH, r) {
      if (tabH <= 0 || tabW <= 0) {
        return GroupLayout._roundedRectPath(bodyW, bodyH, r, 0);
      }
      const tcx = bodyW / 2;
      const tlx = tcx - tabW / 2;
      const trx = tcx + tabW / 2;
      const margin = Math.min(tabH * 2, (bodyW - tabW) / 2 - r);
      const R = (n) => n.toFixed(2);

      return [
        "M " + R(r) + " " + R(tabH),
        "L " + R(tlx - margin) + " " + R(tabH),
        "C " + R(tlx - margin * 0.7) + " " + R(tabH) + " " + R(tlx - margin * 0.3) + " 0 " + R(tlx) + " 0",
        "L " + R(trx) + " 0",
        "C " + R(trx + margin * 0.3) + " 0 " + R(trx + margin * 0.7) + " " + R(tabH) + " " + R(trx + margin) + " " + R(tabH),
        "L " + R(bodyW - r) + " " + R(tabH),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(bodyW) + " " + R(tabH + r),
        "L " + R(bodyW) + " " + R(tabH + bodyH - r),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(bodyW - r) + " " + R(tabH + bodyH),
        "L " + R(r) + " " + R(tabH + bodyH),
        "A " + R(r) + " " + R(r) + " 0 0 1 0 " + R(tabH + bodyH - r),
        "L 0 " + R(tabH + r),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(r) + " " + R(tabH),
        "Z",
      ].join(" ");
    }

    static _roundedRectPath(w, h, r, yOff) {
      const R = (n) => n.toFixed(2);
      return [
        "M " + R(r) + " " + R(yOff),
        "L " + R(w - r) + " " + R(yOff),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(w) + " " + R(yOff + r),
        "L " + R(w) + " " + R(yOff + h - r),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(w - r) + " " + R(yOff + h),
        "L " + R(r) + " " + R(yOff + h),
        "A " + R(r) + " " + R(r) + " 0 0 1 0 " + R(yOff + h - r),
        "L 0 " + R(yOff + r),
        "A " + R(r) + " " + R(r) + " 0 0 1 " + R(r) + " " + R(yOff),
        "Z",
      ].join(" ");
    }
  }

  // ---- ViewState ------------------------------------------------------------

  class ViewState {
    static TRANSITION_MS = 300;
    static TRANSITION_BUFFER_MS = 50;

    constructor(geo, edgeArrows, snapManager, scrollManager, initialSlide, canvasEl, containerFn) {
      this._geometry = geo;
      this._edgeArrows = edgeArrows;
      this._snapManager = snapManager;
      this._scrollManager = scrollManager;
      this._canvas = canvasEl;
      this._containerFn = containerFn;
      this.selectedSlide = initialSlide;
      this.zoomLevel = 1;
      this._transitionEndTimer = null;
      this.onViewChange = null;
    }

    setView(next) {
      const prevSlide = this.selectedSlide;
      const prevZoom = this.zoomLevel;
      if (next.selectedSlide !== undefined) this.selectedSlide = next.selectedSlide;
      if (next.zoomLevel !== undefined) this.zoomLevel = next.zoomLevel;

      const slideChanged = this.selectedSlide !== prevSlide;
      const zoomChanged = this.zoomLevel !== prevZoom;

      if (slideChanged) this._edgeArrows.rebuild(this.selectedSlide);
      if (slideChanged || zoomChanged) this._startTransition(slideChanged, zoomChanged);
      this.syncView();
      if (this.onViewChange) this.onViewChange(this.selectedSlide, this.zoomLevel);
    }

    toggleView() {
      this.setView({ zoomLevel: this.zoomLevel === 1 ? 0 : 1 });
    }

    syncView() {
      this._applyViewCSS(this.computeViewCSS());
      this._applyBodyClass();
      this._applySelectedClass();
      this._snapManager.syncControl(this.selectedSlide, this.zoomLevel);
      this._scrollManager.syncVisibility(this.selectedSlide, this.zoomLevel);
    }

    _startTransition(slideChanged, zoomChanged) {
      const classes = document.body.classList;
      classes.add("view-transitioning");

      const isPan = slideChanged && !zoomChanged;
      classes.remove("pan-transitioning");
      if (isPan) {
        void this._canvas.offsetWidth;
        classes.add("pan-transitioning");
      }

      clearTimeout(this._transitionEndTimer);
      this._transitionEndTimer = setTimeout(() => {
        classes.remove("view-transitioning");
        classes.remove("pan-transitioning");
        this._scrollManager.syncScrollbar(this.selectedSlide);
        this._scrollManager.syncVisibility(this.selectedSlide, this.zoomLevel);
        this._snapManager.syncDots(this.selectedSlide);
      }, ViewState.TRANSITION_MS + ViewState.TRANSITION_BUFFER_MS);
    }

    computeViewCSS() {
      const pos = this._geometry.slideAbstractPos(this.selectedSlide);
      if (!pos) return null;
      if (this._geometry.cols === 0 || this._geometry.rows === 0) return null;

      const t = this.zoomLevel;
      const fitAllScale = this._geometry.fitAllScale();
      const dc = this._geometry.deckCenter();
      return {
        cx: (1 - t) * dc.x + t * (pos.x + 0.5),
        cy: (1 - t) * dc.y + t * (pos.y + 0.5),
        scale: (1 - t) * fitAllScale + t * 1,
        zoom: t,
      };
    }

    _applyViewCSS(css) {
      if (!css) return;
      this._canvas.style.setProperty("--view-cx", css.cx);
      this._canvas.style.setProperty("--view-cy", css.cy);
      this._canvas.style.setProperty("--view-scale", css.scale);
      this._canvas.style.setProperty("--view-zoom", css.zoom);
    }

    _applyBodyClass() {
      const classes = document.body.classList;
      if (this.zoomLevel === 0) {
        classes.remove("view-slide");
        classes.add("view-deck");
      } else {
        classes.remove("view-deck");
        classes.add("view-slide");
      }
    }

    _applySelectedClass() {
      const containers = this._canvas.querySelectorAll(".slide-container");
      containers.forEach((el) => {
        if (el.dataset.id === this.selectedSlide) {
          el.classList.add("selected");
        } else {
          el.classList.remove("selected");
        }
      });
    }
  }

  // ---- BezierOverlay --------------------------------------------------------

  class BezierOverlay {
    constructor(geo, svgContainer) {
      this._geometry = geo;
      this._svg = svgContainer;
      this._paths = [];
    }

    computePaths() {
      const geo = this._geometry;
      if (geo.cols === 0 || geo.rows === 0) return null;
      const { cols, rows } = geo.effectiveGridSize();
      return {
        viewBox: "0 0 " + cols + " " + rows,
        width: (cols * 100) + "dvw",
        height: (rows * 100) + "dvh",
        paths: geo.edges.map((edge) => geo.buildPath(edge)).filter(Boolean),
      };
    }

    rebuild() {
      this._render(this.computePaths());
    }

    _render(data) {
      this._paths.forEach((p) => p.remove());
      this._paths = [];
      if (!data) return;

      this._svg.setAttribute("viewBox", data.viewBox);
      this._svg.style.width = data.width;
      this._svg.style.height = data.height;

      const ns = "http://www.w3.org/2000/svg";
      for (const d of data.paths) {
        const path = document.createElementNS(ns, "path");
        path.setAttribute("class", "canvas-edge");
        path.setAttribute("marker-start", "url(#edge-dot)");
        path.setAttribute("marker-end", "url(#edge-dot)");
        path.setAttribute("d", d);
        this._svg.appendChild(path);
        this._paths.push(path);
      }
    }
  }

  // ---- ElementVisibility ----------------------------------------------------

  const VISIBILITY_THRESHOLD = 0.001;

  function evaluatePiecewiseLinear(keyframes, position) {
    if (keyframes.length === 0) return 1;
    if (position <= keyframes[0][0]) return keyframes[0][1];
    if (position >= keyframes[keyframes.length - 1][0]) return keyframes[keyframes.length - 1][1];
    for (let i = 1; i < keyframes.length; i++) {
      if (position <= keyframes[i][0]) {
        const [x0, y0] = keyframes[i - 1];
        const [x1, y1] = keyframes[i];
        const t = (position - x0) / (x1 - x0);
        return y0 + t * (y1 - y0);
      }
    }
    return keyframes[keyframes.length - 1][1];
  }

  // ---- IdleTimer ----------------------------------------------------------
  //
  // Small reusable scheduler for the "fade after N ms of inactivity" pattern.
  // Used twice: once for the scroll-UI fade (scrollbar + snap control), once
  // for the container-chrome fade (zoom-out + edge arrows). Owns the target
  // element, the idle class name, the delay, and the setTimeout handle.
  //
  //   reset()  remove the idle class immediately, then re-add it after delay.
  //   clear()  remove the idle class and cancel any pending re-add.
  //
  // Tolerates a null `target` so callers can construct the timer before the
  // matching DOM element is queried (or for the no-DOM case in tests).

  class IdleTimer {
    constructor(target, idleClass, delayMs) {
      this._target = target;
      this._class = idleClass;
      this._delay = delayMs;
      this._handle = null;
    }

    reset() {
      if (this._target) this._target.classList.remove(this._class);
      if (this._handle !== null) clearTimeout(this._handle);
      this._handle = setTimeout(() => {
        this._handle = null;
        if (this._target) this._target.classList.add(this._class);
      }, this._delay);
    }

    clear() {
      if (this._target) this._target.classList.remove(this._class);
      if (this._handle !== null) {
        clearTimeout(this._handle);
        this._handle = null;
      }
    }
  }

  class ElementVisibility {
    constructor(canvasEl) {
      this._entries = new Map();
      const elements = canvasEl.querySelectorAll("[data-opacity-keyframes]");
      for (const el of elements) {
        const container = el.closest(".slide-container");
        if (!container) continue;
        const slideId = container.dataset.id;
        const keyframes = JSON.parse(el.dataset.opacityKeyframes);
        if (!this._entries.has(slideId)) this._entries.set(slideId, []);
        this._entries.get(slideId).push({ el, keyframes, hidden: false });
      }
    }

    update(slideId, scrollPosition) {
      const entries = this._entries.get(slideId);
      if (!entries) return;
      for (const entry of entries) {
        const opacity = evaluatePiecewiseLinear(entry.keyframes, scrollPosition);
        const shouldHide = opacity < VISIBILITY_THRESHOLD;
        if (shouldHide !== entry.hidden) {
          entry.el.style.visibility = shouldHide ? "hidden" : "";
          entry.hidden = shouldHide;
        }
      }
    }
  }

  // ---- resolveTarget (pure navigation resolution) --------------------------

  const _KEY_TO_SIDE = {
    ArrowLeft: "left",
    ArrowRight: "right",
    ArrowUp: "top",
    ArrowDown: "bottom",
  };

  function resolveTarget(key, edgesForSideFn, selectedSlide) {
    const side = _KEY_TO_SIDE[key];
    if (!side) return null;

    const strictEdges = edgesForSideFn(selectedSlide, side);

    if (strictEdges.length === 1) {
      return { target: strictEdges[0].target, shouldGlow: false, ambiguous: false };
    }

    if (strictEdges.length === 0) {
      if (key === "ArrowLeft") {
        const pool = edgesForSideFn(selectedSlide, "top");
        if (pool.length === 1) {
          return { target: pool[0].target, shouldGlow: false, ambiguous: false };
        }
      } else if (key === "ArrowRight") {
        const pool = edgesForSideFn(selectedSlide, "bottom");
        if (pool.length === 1) {
          return { target: pool[0].target, shouldGlow: false, ambiguous: false };
        }
      }
    }

    return {
      target: null,
      shouldGlow: strictEdges.length === 0,
      ambiguous: strictEdges.length >= 2,
    };
  }

  // ---- Exports (for Node.js / Vitest testing) -------------------------------

  if (typeof exports !== "undefined") {
    exports.CanvasGeometry = CanvasGeometry;
    exports.ScrollManager = ScrollManager;
    exports.SnapManager = SnapManager;
    exports.EdgeArrows = EdgeArrows;
    exports.BezierOverlay = BezierOverlay;
    exports.ElementVisibility = ElementVisibility;
    exports.IdleTimer = IdleTimer;
    exports.evaluatePiecewiseLinear = evaluatePiecewiseLinear;
    exports.GroupLayout = GroupLayout;
    exports.ViewState = ViewState;
    exports.resolveTarget = resolveTarget;
  }

  // ---- DOM code (skipped in Node.js) ----------------------------------------

  if (typeof document === "undefined") return;



  const dataEl = document.getElementById("scrolly-deck");
  if (!dataEl) {
    console.error("scrolly: missing #scrolly-deck data block");
    return;
  }
  const deck = JSON.parse(dataEl.textContent);

  const geometry = new CanvasGeometry({
    slides: Object.fromEntries(
      Object.entries(deck.slides).map(([id, s]) => [id, s.position])
    ),
    edges: deck.edges || [],
    groups: deck.groups || [],
    fanSpacingFactor: deck.fan_spacing_factor,
  });
  geometry.refresh(window.innerWidth, window.innerHeight);

  const canvas = document.querySelector(".canvas");
  if (!canvas) {
    console.error("scrolly: missing .canvas element");
    return;
  }

  const navigationLayer = document.querySelector(".navigation");
  if (!navigationLayer) {
    console.error("scrolly: missing .navigation element");
    return;
  }


  const edgeArrows = new EdgeArrows(geometry, {
    edgesBySide: Object.fromEntries(
      Object.entries(deck.slides).map(([id, s]) => [id, s.edges || {}])
    ),
    titles: Object.fromEntries(
      Object.entries(deck.slides).map(([id, s]) => [id, s.title])
    ),
  }, navigationLayer);

  const groupLayout = new GroupLayout(geometry, canvas);
  const bezierOverlay = new BezierOverlay(geometry, canvas.querySelector(".canvas-edges"));

  // ---- Event handlers -----------------------------------------------------

  document.addEventListener("keydown", (e) => {
    if (e.key === "z" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (document.body.classList.contains("view-transitioning")) return;
      e.preventDefault();
      viewState.toggleView();
      return;
    }

    if (e.key === "s" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (viewState.zoomLevel !== 1) return;
      if (!snapManager.isControlVisible) return;
      e.preventDefault();
      snapManager.toggle();
      // The toggle is unambiguous user activity: reset both idle-fade
      // pipelines so the scrollbar + snap control fade back in (and stay
      // in long enough for the toggle's visible feedback to register) and
      // the hover-UI chrome follows the same active-user signal.
      scrollUiTimer.reset();
      hoverUiTimer.reset();
      return;
    }

    if (viewState.zoomLevel === 0) {
      if (e.key === "Escape") {
        e.preventDefault();
        viewState.toggleView();
      }
      return;
    }

    if (e.shiftKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      e.preventDefault();
      if (document.body.classList.contains("view-transitioning")) return;
      if (e.key === "ArrowUp") snapManager.up();
      else snapManager.down();
      return;
    }

    if (!(e.key in _KEY_TO_SIDE)) return;
    e.preventDefault();

    const resolved = resolveTarget(e.key, (s, side) => edgeArrows.edgesForSide(s, side), viewState.selectedSlide);
    if (!resolved) return;
    if (resolved.target) {
      viewState.setView({ selectedSlide: resolved.target });
    } else if (resolved.ambiguous) {
      edgeArrows.pulseDisambiguation(_KEY_TO_SIDE[e.key]);
    } else if (resolved.shouldGlow) {
      edgeArrows.pulseGlow(_KEY_TO_SIDE[e.key]);
    }
  });

  document.addEventListener("click", (e) => {
    const zoom = e.target.closest(".zoom-out-control");
    if (zoom) {
      e.preventDefault();
      viewState.toggleView();
      zoom.blur();
      return;
    }

    if (viewState.zoomLevel === 0) {
      const slideEl = e.target.closest(".slide-container");
      if (slideEl && slideEl.dataset.id) {
        e.preventDefault();
        viewState.setView({ zoomLevel: 1, selectedSlide: slideEl.dataset.id });
      }
      return;
    }

    const arrow = e.target.closest(".edge-arrow");
    if (arrow) {
      const target = arrow.dataset.target;
      if (target) {
        e.preventDefault();
        viewState.setView({ selectedSlide: target });
        arrow.blur();
      }
    }
  });

  // Recompute viewport-aware bits when the window resizes.
  // uses the same shifts to keep the deck-view fit and centre correct;
  // fan offsets re-derive against the new viewport-side length so the
  // small-viewport spacing floor binds correctly when the user shrinks
  // the window with edge-arrows already on screen.
  window.addEventListener("resize", () => {
    geometry.refresh(window.innerWidth, window.innerHeight);
    viewState.syncView();
    bezierOverlay.rebuild();
    edgeArrows.refreshFanOffsets();
    groupLayout.refresh();
    snapManager.syncDots(viewState.selectedSlide);
  });

  // ---- Scroll plumbing (ScrollManager) ------------------------------------

  function _container(slideId) {
    return canvas.querySelector('.slide-container[data-id="' + slideId + '"]');
  }

  const scrollbarEl = document.querySelector(".scroll-ui .slide-scrollbar");
  const scrollManager = new ScrollManager(
    Object.fromEntries(
      Object.entries(deck.slides).map(([id, s]) => [id, {
        scrollRange: s.scroll_range,
        scrollSpeed: s.scroll_speed,
        initialScrollPosition: s.initial_scroll_position,
        reverse: !!s.reverse,
      }])
    ),
    _container,
    scrollbarEl
  );
  const snapManager = new SnapManager(
    scrollManager,
    Object.fromEntries(
      Object.entries(deck.slides).map(([id, s]) => [id, {
        snapPositions: s.snap_positions,
      }])
    ),
    _container
  );
  scrollManager.setSnapManager(snapManager);
  const viewState = new ViewState(
    geometry, edgeArrows, snapManager, scrollManager,
    deck.initial_slide, canvas, _container
  );

  // Wheel / trackpad input on the active slide.
  document.addEventListener(
    "wheel",
    (e) => {
      if (viewState.zoomLevel !== 1) return;
      if (document.body.classList.contains("view-transitioning")) return;
      const slideId = viewState.selectedSlide;
      if (!slideId) return;
      const range = scrollManager.range(slideId);
      if (range <= 0) return;

      e.preventDefault();
      snapManager.cancel();

      const speed = scrollManager.scrollSpeed(slideId);
      scrollManager.applyScrollDelta(slideId, e.deltaY * speed);

      snapManager.schedule(slideId);
    },
    { passive: false },
  );

  // Scrollbar thumb drag — dispatches to ScrollManager.
  document.addEventListener("mousedown", (e) => {
    if (scrollManager.startDrag(e, viewState.selectedSlide)) snapManager.cancel();
  });

  document.addEventListener("mousemove", (e) => {
    scrollManager.moveDrag(e);
  });

  document.addEventListener("mouseup", () => {
    const slideId = scrollManager.endDrag();
    if (slideId) snapManager.schedule(slideId);
  });

  // ---- Snap control wiring --------------------------------------------------

  snapManager.initControl(document.querySelector(".snap-control"));

  // ---- Idle timers --------------------------------------------------------
  //
  // Two independent idle-fade pipelines:
  //
  //  - scroll-UI (scrollbar + snap control): resets on scroll-position
  //    changes, scrollbar hover, and the snap-toggle keypress ('s'),
  //    1000 ms delay, 0.5 s fade-out.
  //  - hover-UI (zoom-out + edge arrows): resets on any mouse movement
  //    and on the snap-toggle keypress ('s'), 2000 ms delay, 1.0 s
  //    fade-out (twice the scroll-UI values).
  //
  // Both clear (not just reset) on zoom-out to deck view so neither pipeline
  // affects deck-view chrome, and both reset on entry to slide view.

  const scrollUiEl = document.querySelector(".scroll-ui");
  const navigationEl = document.querySelector(".navigation");
  const scrollUiTimer = new IdleTimer(scrollUiEl, "scroll-ui-idle", 1000);
  const hoverUiTimer = new IdleTimer(navigationEl, "hover-ui-idle", 2000);

  // Reset scroll-UI idle on scroll position change + update element visibility.
  const elementVisibility = new ElementVisibility(canvas);
  scrollManager.onPositionChange = (slideId) => {
    snapManager.onScrollPositionChanged(slideId);
    elementVisibility.update(slideId, scrollManager.position(slideId));
    scrollUiTimer.reset();
  };

  // Reset scroll-UI idle on scroll-UI hover.
  if (scrollUiEl) {
    scrollUiEl.addEventListener("mouseenter", () => scrollUiTimer.reset());
  }

  // Reset hover-UI idle on any mouse movement in slide view.
  document.addEventListener("mousemove", () => {
    if (viewState.zoomLevel !== 1) return;
    hoverUiTimer.reset();
  });

  // Reset/clear both idle timers on view change (slide change or zoom toggle).
  viewState.onViewChange = (slideId, zoomLevel) => {
    if (zoomLevel === 1) {
      scrollUiTimer.reset();
      hoverUiTimer.reset();
    } else {
      scrollUiTimer.clear();
      hoverUiTimer.clear();
    }
  };

  // ---- Init ---------------------------------------------------------------

  if (viewState.selectedSlide) {
    canvas.querySelectorAll(".slide-container").forEach((el) => {
      const gap = geometry.slideGapOffset(el.dataset.id);
      if (gap) {
        el.style.setProperty("--gap-x", gap.gapX);
        el.style.setProperty("--gap-y", gap.gapY);
      }
    });
    edgeArrows.rebuild(viewState.selectedSlide);
    viewState.syncView();
    groupLayout.init();
    bezierOverlay.rebuild();
    groupLayout.refresh();
    scrollManager.init(canvas);
    snapManager.syncControl(viewState.selectedSlide, viewState.zoomLevel);
    elementVisibility.update(
      viewState.selectedSlide,
      scrollManager.position(viewState.selectedSlide)
    );
    scrollUiTimer.reset();
    hoverUiTimer.reset();
  }
})(typeof module !== "undefined" ? module.exports : {});
