#!/usr/bin/env python3
"""
Fail a PR if any sample directory has content changes without a
corresponding version bump in <root>/<slug>/sample.yaml, where <root>
is either `agents/` or `solutions/`.

Why this exists:
  release-samples.yml only cuts a new GitHub Release tarball when it
  sees a `<slug>-<version>` tag that doesn't already exist. Editing
  files inside a sample directory without bumping the `version:` field
  is a silent no-op as far as the published catalog is concerned — the
  immutable old tarball keeps shipping, and CLI users installing
  `<slug>@<current_version>` get the pre-edit bytes.

  This check makes "I forgot to bump" a hard failure at PR time.

Logic:
  - Diff agents/** + solutions/** vs the PR base ref.
  - Group changed paths by (root, slug).
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
SAMPLE_ROOT_NAMES = ("agents", "solutions")
SAMPLE_FILENAME = "sample.yaml"


def _verify_ref(ref: str, repo_root: pathlib.Path = REPO_ROOT) -> None:
    """
    Confirm `ref` resolves to a commit. Raises ValueError on unknown,
    malformed, or flag-shaped values. Prevents the user-supplied ref
    from being interpreted as a `git diff` flag (e.g. "--exec=...").
    """
    if ref.startswith("-"):
        raise ValueError(
            f"Refusing to use ref {ref!r}: looks like a flag, not a revision."
        )
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        raise ValueError(
            f"Could not resolve {ref!r} to a commit. "
            f"In CI this is typically `origin/${{{{ github.base_ref }}}}` — "
            f"ensure `actions/checkout` ran with `fetch-depth: 0`."
        )


def changed_sample_paths(base_ref: str, repo_root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Paths under any SAMPLE_ROOT_NAMES that differ between base_ref and HEAD."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, "HEAD"],
        cwd=repo_root,
    ).decode()
    prefixes = tuple(f"{name}/" for name in SAMPLE_ROOT_NAMES)
    return [line for line in out.splitlines() if line.startswith(prefixes)]


# Backwards-compat alias for any external callers (CI calls main()).
changed_agent_paths = changed_sample_paths


def root_slug_pairs_for_paths(paths: list[str]) -> list[tuple[str, str]]:
    """Return sorted unique (root, slug) pairs from diff paths."""
    pairs: set[tuple[str, str]] = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 2 and parts[0] in SAMPLE_ROOT_NAMES and parts[1]:
            pairs.add((parts[0], parts[1]))
    return sorted(pairs)


def slugs_for_paths(paths: list[str]) -> list[str]:
    """Back-compat: drop the root and return slugs only."""
    return sorted({slug for _root, slug in root_slug_pairs_for_paths(paths)})


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
        # check-sample-artifacts.yml owns sample.yaml parse-validation;
        # silently skip here so a YAML syntax error doesn't surface as
        # two confusingly-different CI failures on the same PR.
        return None
    version = data.get("version")
    return version if isinstance(version, str) else None


def find_unbumped_slugs(
    base_ref: str, repo_root: pathlib.Path = REPO_ROOT
) -> list[tuple[str, str, str]]:
    """Return (root, slug, version) triples for samples touched without a version bump."""
    paths = changed_sample_paths(base_ref, repo_root)
    pairs = root_slug_pairs_for_paths(paths)
    unbumped: list[tuple[str, str, str]] = []
    for root, slug in pairs:
        sample_path = f"{root}/{slug}/{SAMPLE_FILENAME}"
        base_version = version_at(base_ref, sample_path, repo_root)
        head_version = version_at("HEAD", sample_path, repo_root)
        if base_version is None or head_version is None:
            continue
        if base_version == head_version:
            unbumped.append((root, slug, head_version))
    return unbumped


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"

    try:
        _verify_ref(base_ref)
    except ValueError as e:
        print(f"check_sample_version_bumps: {e}", file=sys.stderr)
        return 2

    unbumped = find_unbumped_slugs(base_ref)

    if not unbumped:
        pairs = root_slug_pairs_for_paths(changed_sample_paths(base_ref))
        if pairs:
            print(f"OK: all {len(pairs)} touched sample(s) have version bumps.")
        else:
            print("No sample directories touched.")
        return 0

    print("Version-bump check FAILED:", file=sys.stderr)
    print("", file=sys.stderr)
    for root, slug, version in unbumped:
        print(
            f"  {root}/{slug}: files changed but version: unchanged at {version}.\n"
            f"    Bump version: in {root}/{slug}/sample.yaml so release-samples.yml\n"
            f"    cuts a new tarball with your changes (and remember to regenerate\n"
            f"    samples.json via `uv run scripts/sample_tool.py generate`).",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
