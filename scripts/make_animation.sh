#!/usr/bin/env bash
#
# Build + capture + composite the hero animation from its recipe.
#
# Usage:
#   scripts/make_animation.sh [RECIPE]
#
# Environment:
#   WORK=<dir>   Work / cache directory (default: $TMPDIR/scrolly-hero-animation).
#                Raw captured frames live in $WORK/frames and are reused by REUSE=1.
#   REUSE=1      Skip the slow capture stage and re-composite from cached frames.
#                Use this while tuning overlays only (captions, cursor, timing).
#
# Format-neutral on purpose: the target produces whatever the recipe's
# output declares (GIF and / or WebP). Requires `make capture-setup`
# first (Playwright browser + Pillow + a gifski and / or img2webp binary
# on PATH, per the recipe's output format).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECIPE="${1:-docs/_gen/animation_engine/hero-animation.recipe.json}"
WORK="${WORK:-${TMPDIR:-/tmp}/scrolly-hero-animation}"
REUSE="${REUSE:-0}"

export PYTHONPATH="docs/_gen${PYTHONPATH:+:$PYTHONPATH}"
RUN="uv run python -m animation_engine"

if [ "$REUSE" = "1" ]; then
  echo "==> REUSE=1: re-compositing from cached frames in $WORK/frames"
  $RUN composite --recipe "$RECIPE" --work "$WORK"
else
  DECK="$($RUN deck-path --recipe "$RECIPE")"
  echo "==> building deck: $DECK"
  uv run scrolly build "$DECK" --out "$WORK/deck" --force
  echo "==> capturing + compositing (work: $WORK)"
  $RUN all --recipe "$RECIPE" --deck-html "$WORK/deck/index.html" --work "$WORK"
fi
