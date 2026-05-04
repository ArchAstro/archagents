#!/usr/bin/env python3
"""
Fail a PR if any sample directory has content changes without a
corresponding version bump in agents/<slug>/sample.yaml.

Why this exists:
  release-samples.yml only cuts a new GitHub Release tarball when it
  sees a `<slug>-<version>` tag that doesn't already exist. Editing
  files inside agents/<slug>/ without bumping the `version:` field is
  a silent no-op as far as the published catalog is concerned — the
  immutable old tarball keeps shipping, and CLI users installing
  `<slug>@<current_version>` get the pre-edit bytes.

  This check makes "I forgot to bump" a hard failure at PR time.

Logic:
  - Diff agents/** vs the PR base ref.
  - Group changed paths by slug (agents/<slug>/...).
  - For each slug where sample.yaml exists on both sides, fail if the
    `version:` field is identical between base and HEAD.
  - Skip slugs where sample.yaml is new or deleted (introducing or
    removing a sample is not a "bump-or-no-bump" question).

Usage:
    python3 scripts/check_sample_version_bumps.py [BASE_REF]

BASE_REF defaults to origin/main. CI passes `origin/${{ github.base_ref }}`.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Optional

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENTS_DIR_NAME = "agents"
SAMPLE_FILENAME = "sample.yaml"


def changed_agent_paths(base_ref: str, repo_root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Paths under agents/ that differ between base_ref and HEAD."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, "HEAD"],
        cwd=repo_root,
    ).decode()
    prefix = f"{AGENTS_DIR_NAME}/"
    return [line for line in out.splitlines() if line.startswith(prefix)]


def slugs_for_paths(paths: list[str]) -> list[str]:
    slugs = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 2 and parts[0] == AGENTS_DIR_NAME and parts[1]:
            slugs.add(parts[1])
    return sorted(slugs)


def version_at(
    ref: str, path: str, repo_root: pathlib.Path = REPO_ROOT
) -> Optional[str]:
    """Return the `version:` field of `path` at `ref`, or None if missing/unparseable."""
    try:
        text = subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        ).decode()
    except subprocess.CalledProcessError:
        return None
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    version = data.get("version")
    return version if isinstance(version, str) else None


def find_unbumped_slugs(
    base_ref: str, repo_root: pathlib.Path = REPO_ROOT
) -> list[tuple[str, str]]:
    """Return (slug, version) pairs for samples touched without a version bump."""
    paths = changed_agent_paths(base_ref, repo_root)
    slugs = slugs_for_paths(paths)
    unbumped: list[tuple[str, str]] = []
    for slug in slugs:
        sample_path = f"{AGENTS_DIR_NAME}/{slug}/{SAMPLE_FILENAME}"
        base_version = version_at(base_ref, sample_path, repo_root)
        head_version = version_at("HEAD", sample_path, repo_root)
        if base_version is None or head_version is None:
            continue
        if base_version == head_version:
            unbumped.append((slug, head_version))
    return unbumped


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"

    unbumped = find_unbumped_slugs(base_ref)

    if not unbumped:
        slugs = slugs_for_paths(changed_agent_paths(base_ref))
        if slugs:
            print(f"OK: all {len(slugs)} touched sample(s) have version bumps.")
        else:
            print("No sample directories touched.")
        return 0

    print("Version-bump check FAILED:", file=sys.stderr)
    print("", file=sys.stderr)
    for slug, version in unbumped:
        print(
            f"  agents/{slug}: files changed but version: unchanged at {version}.\n"
            f"    Bump version: in agents/{slug}/sample.yaml so release-samples.yml\n"
            f"    cuts a new tarball with your changes (and remember to regenerate\n"
            f"    samples.json via scripts/generate_sample_artifacts.py).",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
