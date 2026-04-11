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

CHECKS
    Implemented: check_manifest_consistency, check_compat_key_refs
    Planned (#9): check_slash_command_refs, check_hardcoded_versions,
                  check_version_bump_on_content_change
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterable, Iterator


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

PLUGIN_COMPATIBILITY_PATH = REPO_ROOT / "plugin-compatibility.json"

# Content directories scanned by compat/slash-command/hardcoded-version checks.
CONTENT_ROOTS: list[Path] = [
    REPO_ROOT / "sources",
    REPO_ROOT / ".claude-plugins" / "archagents" / "skills",
    REPO_ROOT / ".claude-plugins" / "archagents" / "commands",
    REPO_ROOT / "plugins" / "archagents" / "skills",
]


def _rel(p: Path) -> str:
    """Return `p` relative to REPO_ROOT, or absolute (tests use tmpdirs)."""
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def _iter_content_files(roots: Iterable[Path] | None = None) -> Iterator[Path]:
    """
    Yield markdown files under the plugin content directories, sorted for
    deterministic output. Missing roots are skipped.
    """
    if roots is None:
        roots = CONTENT_ROOTS
    for root in roots:
        if not root.exists():
            continue
        yield from sorted(root.rglob("*.md"))


def check_manifest_consistency(
    marketplace_path: Path = CLAUDE_MARKETPLACE_PATH,
    claude_plugin_path: Path = CLAUDE_PLUGIN_MANIFEST_PATH,
    codex_plugin_path: Path = CODEX_PLUGIN_MANIFEST_PATH,
) -> list[str]:
    """
    Verify the three plugin manifest files agree on `version` and `name`.
    The Claude Code plugin cache keys off the marketplace version; drift
    between the three silently ships broken releases.

    Returns a list of error messages (empty on success).
    """
    errors: list[str] = []

    # Load all three files defensively. A parse/read error on any single
    # file is reported as a check failure rather than a crash, but we stop
    # after collecting all load errors since we can't compare against files
    # we couldn't read.
    manifests: dict[Path, dict] = {}
    for path in (marketplace_path, claude_plugin_path, codex_plugin_path):
        try:
            data = json.loads(path.read_text())
        except OSError as e:
            errors.append(f"{_rel(path)}: cannot read ({e})")
            continue
        except json.JSONDecodeError as e:
            errors.append(f"{_rel(path)}: invalid JSON ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{_rel(path)}: top-level JSON is not an object")
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
            f"{_rel(marketplace_path)}: expected `plugins` to be a list, "
            f"found {type(plugins_list).__name__}"
        )
        return errors
    if len(plugins_list) != 1:
        errors.append(
            f"{_rel(marketplace_path)}: expected exactly one entry in `plugins`, "
            f"found {len(plugins_list)}"
        )
        return errors
    marketplace_plugin = plugins_list[0]
    if not isinstance(marketplace_plugin, dict):
        errors.append(f"{_rel(marketplace_path)}: `plugins[0]` is not an object")
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
            _rel(marketplace_path): marketplace_plugin.get(field),
            _rel(claude_plugin_path): claude_plugin.get(field),
            _rel(codex_plugin_path): codex_plugin.get(field),
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


# Matches `plugins.<name>.minimumCliVersion` references in skill and command
# markdown. Word boundaries at both ends prevent substring matches inside
# larger identifiers (e.g. `xplugins.X.minimumCliVersion` or
# `plugins.X.minimumCliVersionZ`).
_COMPAT_KEY_RE = re.compile(r"\bplugins\.([a-zA-Z0-9_-]+)\.minimumCliVersion\b")


def check_compat_key_refs(
    compat_path: Path = PLUGIN_COMPATIBILITY_PATH,
    content_files: Iterable[Path] | None = None,
) -> list[str]:
    """
    Verify every `plugins.<name>.minimumCliVersion` reference in skill and
    command markdown resolves to a plugin declared in plugin-compatibility.json.
    Stale references silently fall through to the top-level minimumCliVersion,
    hollowing out per-plugin version gating.

    Returns a list of error messages (empty on success).
    """
    errors: list[str] = []

    try:
        compat = json.loads(compat_path.read_text())
    except OSError as e:
        return [f"{_rel(compat_path)}: cannot read ({e})"]
    except json.JSONDecodeError as e:
        return [f"{_rel(compat_path)}: invalid JSON ({e})"]

    if not isinstance(compat, dict):
        return [f"{_rel(compat_path)}: top-level JSON is not an object"]

    plugins_dict = compat.get("plugins")
    if not isinstance(plugins_dict, dict):
        return [
            f"{_rel(compat_path)}: expected `plugins` to be an object, "
            f"found {type(plugins_dict).__name__}"
        ]

    valid_names = set(plugins_dict.keys())

    files = _iter_content_files() if content_files is None else content_files
    for path in files:
        try:
            text = path.read_text()
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _COMPAT_KEY_RE.finditer(line):
                name = match.group(1)
                if name not in valid_names:
                    errors.append(
                        f"{_rel(path)}:{lineno}: references "
                        f"`plugins.{name}.minimumCliVersion` but `{name}` is "
                        f"not declared in plugin-compatibility.json "
                        f"(valid: {sorted(valid_names)})"
                    )

    return errors


# Ordered list of (name, callable) pairs. Runner invokes each in order so
# earlier checks can establish preconditions that later checks rely on
# (e.g. check_version_bump_on_content_change, when added, will assume
# check_manifest_consistency has already validated cross-file agreement).
CHECKS: list[tuple[str, Callable[[], list[str]]]] = [
    ("manifest consistency", check_manifest_consistency),
    ("compat key refs", check_compat_key_refs),
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
