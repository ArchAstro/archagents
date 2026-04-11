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
    Implemented: check_manifest_consistency, check_compat_key_refs,
                 check_slash_command_refs, check_hardcoded_versions,
                 check_version_bump_on_content_change
"""
from __future__ import annotations

import json
import os
import re
import subprocess
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


# Repo-relative path prefixes that count as "plugin content" for the
# version-bump-on-change check. A change under any of these paths requires
# a corresponding manifest version bump so the Claude Code and Codex plugin
# caches refresh. Manifest files themselves are NOT content (they live under
# `.claude-plugin/` and `...path.../.claude-plugin/`, which don't match any
# of these prefixes).
_CONTENT_PATH_PREFIXES: tuple[str, ...] = (
    "sources/",
    ".claude-plugins/archagents/skills/",
    ".claude-plugins/archagents/commands/",
    "plugins/archagents/skills/",
)


def _is_content_path(relpath: str) -> bool:
    """True if `relpath` (repo-relative, forward-slash) is a content file."""
    return any(relpath.startswith(p) for p in _CONTENT_PATH_PREFIXES)


def _load_json_dict(path: Path) -> tuple[dict | None, str | None]:
    """
    Load a JSON file and verify the top level is an object. Returns
    `(data, None)` on success or `(None, error_message)` on failure.
    Exactly one of the two elements is None.
    """
    try:
        data = json.loads(path.read_text())
    except OSError as e:
        return None, f"{_rel(path)}: cannot read ({e})"
    except json.JSONDecodeError as e:
        return None, f"{_rel(path)}: invalid JSON ({e})"
    if not isinstance(data, dict):
        return None, f"{_rel(path)}: top-level JSON is not an object"
    return data, None


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
    # file is collected, but we stop after the loop since we can't compare
    # against files we couldn't read.
    manifests: dict[Path, dict] = {}
    for path in (marketplace_path, claude_plugin_path, codex_plugin_path):
        data, err = _load_json_dict(path)
        if err is not None:
            errors.append(err)
            continue
        assert data is not None  # contract of _load_json_dict
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

    compat, err = _load_json_dict(compat_path)
    if err is not None:
        return [err]
    assert compat is not None

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


# Matches `/plugin:command` slash command references in skill and command
# markdown. Both segments use the same kebab/snake/alnum charset as plugin
# names elsewhere. The greedy `+` captures the full command identifier,
# so `/archagents:installer` captures `installer`, not a `install` prefix.
_SLASH_COMMAND_RE = re.compile(r"/([a-zA-Z0-9_-]+):([a-zA-Z0-9_-]+)")


def check_slash_command_refs(
    marketplace_path: Path = CLAUDE_MARKETPLACE_PATH,
    content_files: Iterable[Path] | None = None,
) -> list[str]:
    """
    Verify every `/plugin:command` reference in skill and command markdown
    resolves to a plugin declared in marketplace.json and a command file
    that actually exists under that plugin's commands/ directory.

    Returns a list of error messages (empty on success).
    """
    errors: list[str] = []

    marketplace, err = _load_json_dict(marketplace_path)
    if err is not None:
        return [err]
    assert marketplace is not None

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        return [
            f"{_rel(marketplace_path)}: expected `plugins` to be a list, "
            f"found {type(plugins).__name__}"
        ]
    if not plugins:
        return [f"{_rel(marketplace_path)}: `plugins` list is empty"]

    # Build {plugin_name: {command_name, ...}} from marketplace entries.
    # Each plugin's `source` field points at its plugin tree root; commands
    # live at `<source>/commands/*.md`. A plugin with no commands/ directory
    # contributes an empty set, which cleanly makes every command ref fail.
    #
    # `source` paths are relative to the repo root — marketplace.json lives
    # at `<repo>/.claude-plugin/marketplace.json`, so the repo root is two
    # levels up. Tests mirror this layout in tmpdir.
    #
    # Resolved commands directories must stay inside `repo_base`. A `source`
    # that escapes the repo (via `../` or absolute path) would otherwise let
    # the check enumerate arbitrary filesystem locations as "valid commands."
    #
    # Malformed entries (non-dict, or dict with missing/wrong-typed `name`
    # or `source`) surface as explicit errors rather than being silently
    # skipped — a contributor typing `"nmae"` should see the typo, not
    # discover it later via a downstream "plugin X not declared" error.
    repo_base = marketplace_path.parent.parent
    repo_resolved = repo_base.resolve()
    valid: dict[str, set[str]] = {}
    for i, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            errors.append(
                f"{_rel(marketplace_path)}: plugins[{i}] is not an object "
                f"(found {type(entry).__name__})"
            )
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str) or not isinstance(source, str):
            errors.append(
                f"{_rel(marketplace_path)}: plugins[{i}] has missing or "
                f"non-string `name`/`source` (name={name!r}, source={source!r})"
            )
            continue
        commands_dir = (repo_base / source / "commands").resolve()
        if not commands_dir.is_relative_to(repo_resolved):
            errors.append(
                f"{_rel(marketplace_path)}: plugin {name!r} source "
                f"{source!r} resolves outside the repo "
                f"({commands_dir} not under {repo_resolved})"
            )
            continue
        if commands_dir.exists() and commands_dir.is_dir():
            valid[name] = {p.stem for p in commands_dir.glob("*.md")}
        else:
            valid[name] = set()

    if errors:
        return errors

    files = _iter_content_files() if content_files is None else content_files
    for path in files:
        try:
            text = path.read_text()
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _SLASH_COMMAND_RE.finditer(line):
                plugin, command = match.group(1), match.group(2)
                if plugin not in valid:
                    errors.append(
                        f"{_rel(path)}:{lineno}: references "
                        f"`/{plugin}:{command}` but plugin `{plugin}` is "
                        f"not declared in marketplace.json "
                        f"(valid: {sorted(valid)})"
                    )
                elif command not in valid[plugin]:
                    errors.append(
                        f"{_rel(path)}:{lineno}: references "
                        f"`/{plugin}:{command}` but command `{command}` does "
                        f"not exist in {plugin}'s commands/ directory "
                        f"(valid: {sorted(valid[plugin])})"
                    )

    return errors


# Matches three-segment version literals like `0.3.1`. Each segment is
# 1-3 digits, which excludes 4-digit year components (e.g. `2026.04.10`
# would not match because `2026` exceeds the `\d{1,3}` bound). Word
# boundaries prevent substring matches inside longer identifiers.
_VERSION_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _iter_scannable_lines(text: str) -> Iterator[tuple[int, str]]:
    """
    Yield (1-based lineno, line) pairs from markdown text, skipping YAML
    frontmatter at the top of the file and lines inside fenced code blocks.
    Both fence delimiters and frontmatter delimiters are consumed but not
    yielded.
    """
    lines = text.splitlines()
    i = 0
    n = len(lines)

    # Frontmatter: if the first line is `---` alone, consume until the
    # next `---`. A file without frontmatter starts scanning at line 1.
    if n > 0 and lines[0].strip() == "---":
        i = 1
        while i < n and lines[i].strip() != "---":
            i += 1
        i += 1  # consume the closing ---

    in_fence = False
    while i < n:
        stripped = lines[i].lstrip()
        # Markdown fences may use either ``` or ~~~ as delimiters.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif not in_fence:
            yield (i + 1, lines[i])
        i += 1


def check_hardcoded_versions(
    content_files: Iterable[Path] | None = None,
) -> list[str]:
    """
    Flag hardcoded semver literals (N.N.N) in skill and command markdown
    prose. Contributors should read from plugin-compatibility.json
    dynamically so a version bump in the manifest flows through to every
    reference automatically. YAML frontmatter and fenced code blocks are
    excluded — version literals there are usually legitimate examples.

    Returns a list of error messages (empty on success).
    """
    errors: list[str] = []
    files = _iter_content_files() if content_files is None else content_files
    for path in files:
        try:
            text = path.read_text()
        except OSError:
            continue
        for lineno, line in _iter_scannable_lines(text):
            for match in _VERSION_RE.finditer(line):
                version = match.group(0)
                errors.append(
                    f"{_rel(path)}:{lineno}: hardcoded version string "
                    f"`{version}` — prefer reading from "
                    f"plugin-compatibility.json dynamically"
                )
    return errors


def check_version_bump_on_content_change(
    marketplace_path: Path = CLAUDE_MARKETPLACE_PATH,
    base_ref: str | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """
    If any content file changed between `base_ref` and HEAD, verify the
    marketplace plugin version also changed. Without a bump, Claude Code
    and Codex serve stale content from their version-keyed caches.

    Assumes check_manifest_consistency has already validated cross-file
    version agreement, so comparing one manifest is sufficient.

    Skips cleanly when:
    - the base ref is unreachable (fresh clone, shallow fetch, local-only)
    - git is unavailable
    - no content files changed
    - marketplace.json didn't exist at the base ref (new-plugin bootstrap)

    Returns a list of error messages (empty on success or skip).
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    # Auto-detect base ref from GITHUB_BASE_REF (PR context) or fall back
    # to origin/main for local dev and push events. On push-to-main the
    # diff will be empty and the check trivially passes.
    if base_ref is None:
        github_base = os.environ.get("GITHUB_BASE_REF")
        base_ref = f"origin/{github_base}" if github_base else "origin/main"

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
        )

    def _warn(msg: str) -> None:
        # Stderr warning that does NOT fail the check — lets skip conditions
        # surface visibly so a misconfigured CI (shallow clone, missing
        # origin/main) doesn't silently no-op this check.
        print(f"WARN [version bump on content change]: {msg}", file=sys.stderr)

    try:
        base_check = _git("rev-parse", "--verify", f"{base_ref}^{{commit}}")
    except FileNotFoundError:
        _warn("git executable not found; skipping check")
        return []
    if base_check.returncode != 0:
        _warn(
            f"base ref {base_ref!r} is unreachable; skipping check. "
            f"If unexpected, verify `fetch-depth: 0` on actions/checkout "
            f"or run `git fetch origin main` locally."
        )
        return []

    diff = _git("diff", "--name-only", f"{base_ref}...HEAD")
    if diff.returncode != 0:
        _warn(f"git diff against {base_ref} failed; skipping check")
        return []
    changed_files = [line for line in diff.stdout.splitlines() if line]
    content_changed = [f for f in changed_files if _is_content_path(f)]
    if not content_changed:
        return []

    # Read current version from the working-tree marketplace. Load errors
    # are silently skipped — a malformed current manifest is the manifest
    # consistency check's concern, not this one's.
    current, _ = _load_json_dict(marketplace_path)
    if current is None:
        return []
    try:
        current_version = current["plugins"][0]["version"]
    except (KeyError, IndexError, TypeError):
        return []

    # Read base version from the marketplace at the base ref.
    try:
        marketplace_relpath = marketplace_path.relative_to(repo_root).as_posix()
    except ValueError:
        _warn(
            f"marketplace_path {marketplace_path!r} is not under "
            f"repo_root {repo_root!r}; skipping check"
        )
        return []
    base_show = _git("show", f"{base_ref}:{marketplace_relpath}")
    if base_show.returncode != 0:
        # marketplace.json didn't exist at base → treat as implicit bump.
        return []
    try:
        base_data = json.loads(base_show.stdout)
        base_version = base_data["plugins"][0]["version"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return []

    if current_version != base_version:
        return []

    detail = "\n".join(f"    {f}" for f in content_changed)
    return [
        f"plugin content changed but marketplace plugin version is still "
        f"{current_version!r} (same as {base_ref}). Bump the version in all "
        f"three manifest files or CI will serve stale content on install. "
        f"Changed files:\n{detail}"
    ]


# Ordered list of (name, callable) pairs. Runner invokes each in order so
# earlier checks can establish preconditions that later checks rely on
# (e.g. check_version_bump_on_content_change assumes check_manifest_consistency
# has already validated cross-file agreement, so it can compare just one
# manifest's version against the PR base).
CHECKS: list[tuple[str, Callable[[], list[str]]]] = [
    ("manifest consistency", check_manifest_consistency),
    ("compat key refs", check_compat_key_refs),
    ("slash command refs", check_slash_command_refs),
    ("hardcoded versions", check_hardcoded_versions),
    ("version bump on content change", check_version_bump_on_content_change),
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
