"""Release driver for scrolly.

Run via ``make release VERSION=X.Y.Z``.  Validates state, bumps
version, finalizes the changelog, commits, tags, opens a new
Unreleased section, commits, and pushes main + tag atomically.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PYTHON_VERSIONS_FILE = REPO_ROOT / ".python-versions"

PACKAGE_NAME = "scrolly"
CATEGORIES = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ==================================================================================================
#  helpers
# ==================================================================================================
def run(cmd: list[str], **kw) -> str:
    """Run a subprocess and return stdout, or exit on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        sys.stderr.write(f"\n$ {' '.join(cmd)}\n")
        if result.stdout:
            sys.stderr.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result.stdout


def step(n: int, msg: str) -> None:
    """Print a numbered step message."""
    print(f"  [{n:>2}] {msg}")


def fail(msg: str, code: int = 1) -> None:
    """Print an error and exit."""
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse and validate a semver string."""
    if not SEMVER_RE.match(version):
        fail(f"VERSION {version!r} is not in X.Y.Z form")
    return tuple(int(p) for p in version.split("."))  # type: ignore[return-value]


def read_pyproject_version() -> str:
    """Read the current version from pyproject.toml."""
    text = PYPROJECT.read_text()
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not m:
        fail("Could not find version in pyproject.toml")
    return m.group(1)


def read_python_versions() -> list[str]:
    """Read supported Python versions from .python-versions."""
    return [v.strip() for v in PYTHON_VERSIONS_FILE.read_text().split() if v.strip()]


# ==================================================================================================
#  validation steps (1-6)
# ==================================================================================================
def step_1_check_working_tree() -> None:
    """Validate working tree is on main and clean."""
    step(1, "working tree on main and clean")
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch != "main":
        fail(f"not on main (currently on {branch})")
    porcelain = run(["git", "status", "--porcelain"])
    if porcelain.strip():
        fail("working tree has uncommitted changes:\n" + porcelain)


def step_2_check_in_sync() -> None:
    """Validate main is in sync with origin."""
    step(2, "main in sync with origin")
    run(["git", "fetch", "origin", "main"])
    local = run(["git", "rev-parse", "HEAD"]).strip()
    remote = run(["git", "rev-parse", "origin/main"]).strip()
    if local != remote:
        fail(f"local main ({local[:8]}) does not match origin/main ({remote[:8]})")


def step_3_check_version_upgrade(version: str) -> None:
    """Validate VERSION is strictly greater than current."""
    step(3, f"VERSION {version} is an upgrade")
    new = parse_semver(version)
    current = parse_semver(read_pyproject_version())
    if new <= current:
        fail(f"VERSION {version} is not greater than current {'.'.join(str(p) for p in current)}")


def step_4_check_tag_doesnt_exist(version: str) -> None:
    """Validate tag does not exist locally or on origin."""
    step(4, f"tag v{version} does not exist (local + remote)")
    tag = f"v{version}"
    if run(["git", "tag", "-l", tag]).strip():
        fail(f"tag {tag} already exists locally")
    if run(["git", "ls-remote", "--tags", "origin", tag]).strip():
        fail(f"tag {tag} already exists on origin")


def step_5_check_pypi_doesnt_have(version: str) -> None:
    """Validate version is not already on PyPI."""
    step(5, f"version {version} is not on PyPI")
    url = f"https://pypi.org/pypi/{PACKAGE_NAME}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=10):
            fail(f"version {version} is already published on PyPI")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            fail(f"PyPI check returned HTTP {e.code}")


def step_6_check_classifiers_match() -> None:
    """Validate Python classifiers match .python-versions."""
    step(6, "Python classifiers in pyproject.toml match .python-versions")
    versions = read_python_versions()
    text = PYPROJECT.read_text()
    declared = set(re.findall(r'"Programming Language :: Python :: ([\d.]+)"', text))
    expected = set(versions)
    missing = expected - declared
    extra = declared - expected
    if missing or extra:
        fail(
            f"classifiers do not match .python-versions. "
            f"Missing: {sorted(missing) or 'none'}; "
            f"Extra: {sorted(extra) or 'none'}"
        )


def step_7_check_changelog_has_entries() -> None:
    """Validate Unreleased section has at least one bullet entry."""
    step(7, "CHANGELOG.md '## Unreleased' has at least one entry")
    text = CHANGELOG.read_text()
    m = re.search(r"^## Unreleased\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        fail("no '## Unreleased' section in CHANGELOG.md")
    if not re.search(r"^- ", m.group(1), re.MULTILINE):
        fail("'## Unreleased' has no bullet entries")


# ==================================================================================================
#  release commit steps (8-11)
# ==================================================================================================
def step_8_bump_version(version: str) -> None:
    """Set version in pyproject.toml."""
    step(8, f"bump version to {version}")
    run(["uv", "version", version])


def step_9_lock() -> None:
    """Refresh uv.lock after version bump."""
    step(9, "refresh uv.lock")
    run(["uv", "lock"])


def step_10_finalize_changelog(version: str) -> None:
    """Move Unreleased entries to a dated version section."""
    step(10, f"finalize CHANGELOG.md '## Unreleased' -> '## {version} ({date.today().isoformat()})'")
    text = CHANGELOG.read_text()
    m = re.search(r"^## Unreleased\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        fail("no '## Unreleased' section to finalize")
    body = m.group(1)
    new_body_lines: list[str] = []
    lines = body.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        cat_match = re.match(r"^### (\w+)\s*$", line)
        if cat_match and cat_match.group(1) in CATEGORIES:
            j = i + 1
            has_entry = False
            while j < len(lines) and not re.match(r"^### ", lines[j]):
                if lines[j].lstrip().startswith("- "):
                    has_entry = True
                    break
                j += 1
            if has_entry:
                new_body_lines.append(line)
                i += 1
                while i < len(lines) and not re.match(r"^### ", lines[i]):
                    new_body_lines.append(lines[i])
                    i += 1
            else:
                i += 1
                while i < len(lines) and lines[i].strip() == "":
                    i += 1
        else:
            new_body_lines.append(line)
            i += 1
    new_body = "".join(new_body_lines).rstrip() + "\n"
    new_header = f"## {version} ({date.today().isoformat()})\n"
    text = text[: m.start()] + new_header + new_body + text[m.end() :]
    CHANGELOG.write_text(text)


def step_11_commit_release(version: str) -> None:
    """Create the release commit."""
    step(11, f"commit 'release: {version}'")
    run(["git", "add", "pyproject.toml", "uv.lock", "CHANGELOG.md"])
    run(["git", "commit", "-m", f"release: {version}"])


def step_12_tag(version: str) -> None:
    """Create the version tag."""
    step(12, f"create tag v{version}")
    run(["git", "tag", f"v{version}"])


# ==================================================================================================
#  post-release steps (13-15)
# ==================================================================================================
def step_13_add_unreleased_section() -> None:
    """Add a fresh Unreleased section to the changelog."""
    step(13, "add fresh '## Unreleased' section to CHANGELOG.md")
    text = CHANGELOG.read_text()
    m = re.search(r"^## ", text, re.MULTILINE)
    if not m:
        fail("CHANGELOG.md has no version sections")
    insertion = "## Unreleased\n\n" + "\n".join(f"### {c}\n" for c in CATEGORIES) + "\n"
    text = text[: m.start()] + insertion + text[m.start() :]
    CHANGELOG.write_text(text)


def step_14_commit_next_cycle() -> None:
    """Commit the fresh Unreleased section."""
    step(14, "commit 'chore: begin next development cycle'")
    run(["git", "add", "CHANGELOG.md"])
    run(["git", "commit", "-m", "chore: begin next development cycle"])


def step_15_push(version: str) -> None:
    """Push main and the tag atomically."""
    step(15, f"push main + v{version} atomically")
    run(["git", "push", "--atomic", "origin", "main", f"refs/tags/v{version}"])


# ==================================================================================================
#  orchestration
# ==================================================================================================
def post_tag_recovery_hint(failed_step: int, version: str, also_next_cycle: bool) -> None:
    """Print recovery instructions after a post-tag failure."""
    reset_count = 2 if also_next_cycle else 1
    print(
        f"\nERROR: step {failed_step} failed.\n"
        f"Local state: release commit and tag v{version} created, not pushed.\n"
        f"To abort and retry:\n"
        f"  git tag -d v{version}\n"
        f"  git reset --hard HEAD~{reset_count}\n",
        file=sys.stderr,
    )


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="X.Y.Z (no leading v)")
    args = parser.parse_args()
    version = args.version
    parse_semver(version)

    print(f"Releasing {PACKAGE_NAME} v{version}\n")

    print("Validation:")
    step_1_check_working_tree()
    step_2_check_in_sync()
    step_3_check_version_upgrade(version)
    step_4_check_tag_doesnt_exist(version)
    step_5_check_pypi_doesnt_have(version)
    step_6_check_classifiers_match()
    step_7_check_changelog_has_entries()

    print("\nRelease commit:")
    step_8_bump_version(version)
    step_9_lock()
    step_10_finalize_changelog(version)
    step_11_commit_release(version)
    step_12_tag(version)

    print("\nPost-release:")
    also_next_cycle = False
    try:
        step_13_add_unreleased_section()
        step_14_commit_next_cycle()
        also_next_cycle = True
        step_15_push(version)
    except subprocess.CalledProcessError:
        post_tag_recovery_hint(13, version, also_next_cycle)
        sys.exit(1)
    except SystemExit:
        post_tag_recovery_hint(13, version, also_next_cycle)
        raise

    print(f"\nReleased v{version}.")


if __name__ == "__main__":
    main()
