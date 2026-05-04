.PHONY: help dev-setup build test format lint update-deps install release

help:
	@echo 'Commands:'
	@echo '  dev-setup   One-time: sync dev deps, install npm packages, install pre-commit hooks'
	@echo '  build       Build package'
	@echo '  test        Run pytest + vitest'
	@echo '  format      Format and fix with ruff'
	@echo '  lint        Ruff check'
	@echo '  update-deps Re-resolve uv.lock to latest versions'
	@echo '  install     Re-install scrolly stand-alone tool'
	@echo '  release     Bump version, validate, tag, push (VERSION=X.Y.Z)'

dev-setup:
	uv sync --group dev
	npm ci
	uv run pre-commit install

build:
	uv build

test:
	uv run pytest
	npx vitest run

format:
	uv run ruff format scrolly tests/python scripts
	uv run ruff check --fix scrolly tests/python scripts

lint:
	uv run ruff check scrolly tests/python scripts

update-deps:
	uv lock --upgrade

install:
	uv tool install --editable .

release:
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=X.Y.Z" && exit 1)
	$(MAKE) test
	uv run python scripts/release.py $(VERSION)
