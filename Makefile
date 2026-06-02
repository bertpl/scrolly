.PHONY: help dev-setup build test lint lint-check update-deps install release hero-animation demo-clips capture-setup

help:
	@echo 'Commands:'
	@echo '  dev-setup      One-time: sync dev deps, install npm packages, install pre-commit hooks'
	@echo '  build          Build package'
	@echo '  test           Run pytest + vitest'
	@echo '  lint           Format + lint, with auto-fixes'
	@echo '  lint-check     Format + lint check only, no fixes (gate used by CI)'
	@echo '  update-deps    Re-resolve uv.lock to latest versions'
	@echo '  install        Re-install scrolly stand-alone tool'
	@echo '  release        Bump version, validate, tag, push (VERSION=X.Y.Z)'
	@echo '  capture-setup  One-time: install the hero-animation capture deps (Playwright + browser; see notes)'
	@echo '  hero-animation Build + capture + composite the hero animation from its recipe'
	@echo '  demo-clips     Build every viewing-decks demo clip (one work dir each; REUSE=1 to re-encode)'

dev-setup:
	uv sync --group dev
	npm ci
	uv run pre-commit install

build:
	uv build

test:
	uv run pytest
	npx vitest run

lint:
	uv run ruff format scrolly tests/python scripts docs/_gen
	uv run ruff check --fix scrolly tests/python scripts docs/_gen

lint-check:
	uv run ruff format --check scrolly tests/python scripts docs/_gen
	uv run ruff check scrolly tests/python scripts docs/_gen

update-deps:
	uv lock --upgrade

install:
	uv tool install --editable .

release:
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=X.Y.Z" && exit 1)
	$(MAKE) test
	uv run python scripts/release.py $(VERSION)

capture-setup:
	uv sync --group capture
	uv run playwright install chromium
	@echo ''
	@echo 'Also install the native assembly binaries (not Python packages),'
	@echo 'per the recipe output format — gifski for GIF, img2webp for WebP:'
	@echo '  gifski (GIF):'
	@echo '    macOS:  brew install gifski'
	@echo '    cargo:  cargo install gifski'
	@echo '    more:   https://gif.ski'
	@echo '  img2webp (WebP, ships with libwebp):'
	@echo '    macOS:  brew install webp'
	@echo '    apt:    apt install webp'

# Version stamped into rendered help screens (hero + demo clips). The package
# version is still pre-release at render time, so set this to the release these
# assets ship with; update it when re-rendering for a new version.
CLIP_VERSION ?= 0.2.4

hero-animation:
	SCROLLY_CLIP_VERSION=$(CLIP_VERSION) bash scripts/make_animation.sh

# Each clip gets its own work dir so cached frames don't collide and
# per-clip REUSE=1 (re-composite without re-capturing) works.
demo-clips:
	@for recipe in docs/_gen/animation_engine/clips/*.recipe.json; do \
		name=$$(basename "$$recipe" .recipe.json); \
		echo "==> clip: $$name"; \
		SCROLLY_CLIP_VERSION=$(CLIP_VERSION) WORK="$${TMPDIR:-/tmp}/scrolly-clips/$$name" bash scripts/make_animation.sh "$$recipe"; \
	done
