.PHONY: help dev-setup build test lint lint-check update-deps install release hero-animation capture-setup

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
	@echo 'Also install a gifski binary (not a Python package):'
	@echo '  macOS:  brew install gifski'
	@echo '  cargo:  cargo install gifski'
	@echo '  more:   https://gif.ski'

hero-animation:
	bash scripts/make_animation.sh
