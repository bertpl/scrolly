# Contributing to scrolly

Thanks for your interest in contributing.

## Dev setup

One-time setup on a fresh clone:

```bash
make dev-setup
```

This syncs dev dependencies via `uv`, installs npm packages, and installs
pre-commit hooks.

## Common commands

```bash
make test       # Run the test suite (pytest + vitest)
make format     # Format and auto-fix with ruff
make lint       # Lint with ruff
```

## Branching

Branch names follow the pattern:

```
<prefix>/<NN>-<short-slug>
```

- **Prefix** -- one of `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`,
  `test/`. CI rejects anything else.
- **NN** -- two-digit zero-padded sequence number, continuous across all
  branches in the project (substitutes for an issue number where one
  doesn't exist). Use the next free number; check `git branch -a` if
  unsure.
- **Slug** -- short kebab-case description, lowercase letters, digits,
  and hyphens only.

Examples: `chore/01-oss-scaffolding`, `feat/07-new-slide-type`,
`fix/12-build-crash-on-empty-deck`.

When a GitHub issue exists, its number replaces the sequence
(`feat/42-...`).

## Pull requests

PRs are merged into `main` via **squash merge only** (repo settings
disable merge commits and rebase merges). Each PR therefore produces
exactly one commit on `main`. The squash commit subject is the PR
title and the body is the PR body, so write both with care -- they
become the permanent history. The feature branch is deleted
automatically on merge.

## Commit messages

Subject line uses the same short-form prefixes as branches:

```
<prefix>: <imperative summary>
```

- **Prefix** -- `feat`, `fix`, `chore`, `docs`, `refactor`, `test`
  (matching the branch prefix is the common case but not required).
- **Summary** -- imperative mood, lowercase, no trailing period,
  ideally under 72 characters.

Examples:

```
feat: add storyboard slide type
fix: handle empty group in deck build
chore: bump click to 8.3
docs: clarify scrollimation config
```

The body (optional) explains *why*, not *what*. Wrap at ~72 characters.

## Changelog

Add an entry under the appropriate category in the `## Unreleased` section
of [`CHANGELOG.md`](CHANGELOG.md) as part of your PR.
