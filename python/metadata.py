"""HILIGHTer project metadata.

This file is the single source of truth for user-facing application versioning.

Version policy:

- `VERSION_MAJOR` (`x`) changes only when explicitly directed by the human.
- `VERSION_MINOR` (`y`) increments when a milestone is reached.
- `z` is derived from the current git build count relative to `PATCH_BASE_BUILD`.
  It resets to `0` when a new milestone is declared by moving `PATCH_BASE_BUILD`
  to the build that establishes the new `x.y.0` line.
- Build number is the total repository commit count.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


VERSION_MAJOR = 1
VERSION_MINOR = 0
RELEASE_STAGE = "beta"

# Build 40 is the first planned committed build for the 1.0.0 beta line.
PATCH_BASE_BUILD = 40

# Fallbacks used when git metadata is unavailable.
FALLBACK_BUILD_NUMBER = 39
FALLBACK_COMMIT = "unknown"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_git(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def get_build_number() -> int:
    raw = _run_git("rev-list", "--count", "HEAD")
    if raw and raw.isdigit():
        return int(raw)
    return FALLBACK_BUILD_NUMBER


def get_commit_short_sha() -> str:
    return _run_git("rev-parse", "--short", "HEAD") or FALLBACK_COMMIT


def get_patch_number(build_number: int | None = None) -> int:
    build = get_build_number() if build_number is None else int(build_number)
    return max(build - PATCH_BASE_BUILD, 0)


def get_version(build_number: int | None = None) -> str:
    patch = get_patch_number(build_number)
    return f"{VERSION_MAJOR}.{VERSION_MINOR}.{patch}"


def get_release_label(build_number: int | None = None) -> str:
    return f"{get_version(build_number)} ({RELEASE_STAGE})"


def get_build_label(build_number: int | None = None) -> str:
    build = get_build_number() if build_number is None else int(build_number)
    return f"Build {build}"


def get_full_version_label(build_number: int | None = None) -> str:
    return f"{get_release_label(build_number)} {get_build_label(build_number)}"
