#!/usr/bin/env python3
"""
Repository-validation checks for the archagents plugin repo.

This module hosts all checks that validate the *state* of the repository
as opposed to the *content rendering* in `generate-plugin-content.py`.
The split is structural:

    generate-plugin-content.py   → reads sources/, writes skill/command files
    check_plugin_repo.py         → reads repo state, reports correctness errors

Keeping repo validation in its own module means:

- New validation checks land here without bloating the generator file
- CI can invoke each script independently (failure modes don't interleave)
- Tests for each concern live in their own test module
- The generator stays narrowly focused on its rendering contract

USAGE

    python3 scripts/check_plugin_repo.py

    Runs every check and exits non-zero if any reports errors.

ERROR CONTRACT

    Each check function takes optional path / repo-root keyword arguments
    (for testability) and returns `list[str]` of human-readable error
    messages — empty list means the check passed. Checks do not raise;
    the runner composes results across all checks so a single report can
    surface multiple failures at once.

CHECKS (currently implemented)

    check_manifest_consistency
        All three plugin manifest files (marketplace.json, the Claude
        plugin.json, the Codex plugin.json) must agree on `version` and
        `name`. The Claude Code plugin cache keys off the marketplace
        plugin version; drift between the three silently ships broken
        releases. Moved here from generate-plugin-content.py as part of
        the L3 follow-up from PR #14 — repo-validation concerns now live
        in one place.

CHECKS (planned, tracked on #9)

    check_compat_key_refs
        Every plugins.<name>.minimumCliVersion reference in skill/command
        markdown corresponds to a real key in plugin-compatibility.json.

    check_slash_command_refs
        Every /<plugin>:<command> reference in skill/command markdown
        corresponds to a plugin declared in marketplace.json and a command
        file under that plugin's commands/ directory.

    check_hardcoded_versions
        Flag any literal N.N.N version string in skill/command prose.
        Prefer the dynamic plugin-compatibility.json lookup pattern.

    check_version_bump_on_content_change
        Content changes under sources/, .claude-plugins/archagents/, or
        plugins/archagents/ must come with a manifest version bump, or
        the Claude/Codex plugin caches will not refresh for users.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parent.parent

# Plugin manifest files. These are hand-edited (not generated) but their
# `version` and `name` fields must agree across all three — the Claude
# Code plugin cache keys off the marketplace.json plugin version.
CLAUDE_MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CLAUDE_PLUGIN_MANIFEST_PATH = (
    REPO_ROOT / ".claude-plugins" / "archagents" / ".claude-plugin" / "plugin.json"
)
CODEX_PLUGIN_MANIFEST_PATH = (
    REPO_ROOT / "plugins" / "archagents" / ".codex-plugin" / "plugin.json"
)


def check_manifest_consistency(
    marketplace_path: Path = CLAUDE_MARKETPLACE_PATH,
    claude_plugin_path: Path = CLAUDE_PLUGIN_MANIFEST_PATH,
    codex_plugin_path: Path = CODEX_PLUGIN_MANIFEST_PATH,
) -> list[str]:
    """
    Verify the three plugin manifest files agree on plugin name and version.

    The manifest files are hand-edited (not generated from sources/) but the
    Claude Code plugin cache keys off the marketplace.json plugin version. If
    the three version fields drift, the cache will either fail to refresh or
    serve stale content to users — this was the operational lesson from PR
    #12. This check enforces version equality across all three files and
    plugin name equality as a belt-and-braces guard against copy-paste drift.

    Paths default to the committed manifest locations but accept overrides
    for tests. Returns a list of human-readable error messages (empty if
    consistent). Does not raise — callers compose this with the other
    check(s) so all failures surface in a single report.
    """
    errors: list[str] = []

    def rel(p: Path) -> str:
        # Fall back to the full path when p is outside REPO_ROOT (tests use
        # tmpdirs that aren't relative to the repo).
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return str(p)

    # Load all three files defensively. A parse/read error on any single
    # file is reported as a check failure rather than a crash, but we stop
    # after collecting all load errors since we can't compare against files
    # we couldn't read.
    manifests: dict[Path, dict] = {}
    for path in (marketplace_path, claude_plugin_path, codex_plugin_path):
        try:
            data = json.loads(path.read_text())
        except OSError as e:
            errors.append(f"{rel(path)}: cannot read ({e})")
            continue
        except json.JSONDecodeError as e:
            errors.append(f"{rel(path)}: invalid JSON ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{rel(path)}: top-level JSON is not an object")
            continue
        manifests[path] = data
    if errors:
        return errors

    # marketplace.json is expected to contain exactly one plugin entry.
    # Enforce that contract explicitly rather than silently indexing [0],
    # so a future contributor adding a second entry cannot defeat the check.
    plugins_list = manifests[marketplace_path].get("plugins")
    if not isinstance(plugins_list, list):
        errors.append(
            f"{rel(marketplace_path)}: expected `plugins` to be a list, "
            f"found {type(plugins_list).__name__}"
        )
        return errors
    if len(plugins_list) != 1:
        errors.append(
            f"{rel(marketplace_path)}: expected exactly one entry in `plugins`, "
            f"found {len(plugins_list)}"
        )
        return errors
    marketplace_plugin = plugins_list[0]
    if not isinstance(marketplace_plugin, dict):
        errors.append(f"{rel(marketplace_path)}: `plugins[0]` is not an object")
        return errors

    claude_plugin = manifests[claude_plugin_path]
    codex_plugin = manifests[codex_plugin_path]

    # For each checked field we enforce two separate invariants:
    #   (a) the field is present in every file (missing → per-file error)
    #   (b) the values across files agree (disagree → consolidated error)
    # Splitting (a) from (b) prevents the `None == None == None` silent-pass
    # failure mode where all three files omit the field and the set-equality
    # check would otherwise collapse to `{None}` and report consistent.
    def check_field(field: str, label: str) -> None:
        values = {
            rel(marketplace_path): marketplace_plugin.get(field),
            rel(claude_plugin_path): claude_plugin.get(field),
            rel(codex_plugin_path): codex_plugin.get(field),
        }
        # Treat None (missing) and "" (explicit empty string) as equivalent
        # failure modes. Without the empty-string branch, three files all
        # set to `"version": ""` would produce `{""}` under set-equality
        # and pass silently — same shape of bug as the None case.
        missing = [path for path, v in values.items() if v is None or v == ""]
        if missing:
            errors.append(
                f"plugin manifest `{field}` field missing or empty in:\n"
                + "\n".join(f"    {path}" for path in missing)
            )
            return
        if len(set(values.values())) != 1:
            detail = "\n".join(f"    {path}: {v!r}" for path, v in values.items())
            errors.append(f"plugin manifest {label} disagree:\n{detail}")

    # Hard invariant: plugin version (cache refresh depends on it).
    check_field("version", "versions")
    # Soft invariant: plugin name (not cache-critical but catches drift cheaply).
    check_field("name", "names")

    return errors


# Ordered list of (name, callable) pairs. Runner invokes each in order so
# earlier checks can establish preconditions that later checks rely on
# (e.g. check_version_bump_on_content_change, when added, will assume
# check_manifest_consistency has already validated cross-file agreement).
CHECKS: list[tuple[str, Callable[[], list[str]]]] = [
    ("manifest consistency", check_manifest_consistency),
]


def main() -> int:
    any_failed = False
    for name, check in CHECKS:
        errors = check()
        if errors:
            any_failed = True
            print(f"FAIL [{name}]:", file=sys.stderr)
            for err in errors:
                for line in err.splitlines():
                    print(f"  {line}", file=sys.stderr)
        else:
            print(f"OK   [{name}]")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
