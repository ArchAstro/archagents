#!/usr/bin/env python3
"""
Generate Claude Code and Codex plugin content from canonical sources in sources/.

One source file per concept in sources/<name>.md. Each source declares its
output targets (claude-skill, claude-command, codex-skill) via the `targets:`
frontmatter field. The script applies harness-specific substitutions and
conditional blocks, then writes to the declared output paths.

USAGE
    python3 scripts/generate-plugin-content.py           # write outputs
    python3 scripts/generate-plugin-content.py --check   # diff against committed, exit 1 if different

    Both modes first run a manifest consistency check (version and name
    must agree across .claude-plugin/marketplace.json, the Claude plugin.json,
    and the Codex plugin.json). Inconsistent manifests exit 2 before any
    content rendering is attempted.

SOURCE FILE FORMAT
    ---
    targets:
      claude-skill: <dirname>      # → .claude-plugins/archagents/skills/<dirname>/SKILL.md
      claude-command: <filename>   # → .claude-plugins/archagents/commands/<filename>
      codex-skill: <dirname>       # → plugins/archagents/skills/<dirname>/SKILL.md
    skill:                         # frontmatter used for any skill target
      name: <name>                 # must match <dirname>
      description: <description>   # natural-language trigger phrases
      allowed-tools: [...]
    command:                       # frontmatter used for claude-command targets
      description: <description>
      allowed-tools: [...]
    ---

    # Body

    Body content with {{SUBSTITUTION}} placeholders and conditional blocks.

SUBSTITUTIONS (resolved per target harness)
    {{HARNESS_NAME}}       "Claude Code" | "Codex"
    {{SESSION}}            "Claude Code session" | "Codex session"
    {{ASSUME_INSTALLED}}   harness-specific CLI install reminder paragraph
    {{INSTALL_ROUTE}}      "direct the user to `/archagents:install`" |
                           "instruct the user to install or upgrade `archagent`"
    {{AUTH_ROUTE}}         "direct the user to `/archagents:auth`" |
                           "instruct the user to run `archagent auth login`"
    {{AUTH_ROUTE_SHORT}}   "route to `/archagents:auth`" | "run `archagent auth login`"

CONDITIONAL BLOCKS (emit only for matching targets)
    {{#SKILL}} ... {{/SKILL}}                  any skill target (claude or codex)
    {{#CLAUDE_COMMAND}} ... {{/CLAUDE_COMMAND}} only claude-command targets

    Limitation: conditional blocks CANNOT nest. The non-greedy regex plus
    backreferenced close-tag means a pattern like
    `{{#A}}before {{#B}}inner{{/B}} after{{/A}}` would treat the outer `A`
    block as matching everything through `{{/A}}`, and the inner `{{#B}}`
    marker would leak into the substituted body as literal text. The
    generator detects unbalanced open/close marker counts and raises at
    generate time rather than silently producing wrong output.

DESIGN NOTE: ASYMMETRY BETWEEN INSTALL/AUTH AND OTHER CONCEPTS
    `install.md` and `auth.md` generate a claude-command + codex-skill, but
    intentionally do NOT generate a claude-skill.

    Why: install and auth are one-shot bootstrap actions. In Claude Code they
    are discovered via `/` autocomplete — a slash command is the right UX.
    Adding a claude-skill with the same name would create a naming collision
    with the claude-command in the Skill tool's dispatch table.

    In Codex there is no slash command concept (verified in
    https://developers.openai.com/codex/plugins/build), so skills are the only
    way to reach install/auth content via natural language. Codex gets a skill
    with trigger phrases; Claude Code gets a command and relies on autocomplete
    discovery.

    Impersonate is different: it has subcommands (start/status/sync/stop) and
    benefits from both explicit invocation (slash command) and conversational
    triggering. It generates claude-skill + claude-command + codex-skill.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
CLAUDE_PLUGIN_ROOT = REPO_ROOT / ".claude-plugins" / "archagents"
CODEX_PLUGIN_ROOT = REPO_ROOT / "plugins" / "archagents"

# Plugin manifest files. These are hand-edited (not generated from sources/)
# but their `version` and `name` fields must agree across all three — the
# Claude Code plugin cache keys off the marketplace.json plugin version.
CLAUDE_MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CLAUDE_PLUGIN_MANIFEST_PATH = CLAUDE_PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
CODEX_PLUGIN_MANIFEST_PATH = CODEX_PLUGIN_ROOT / ".codex-plugin" / "plugin.json"


TargetType = Literal["claude-skill", "claude-command", "codex-skill"]
Harness = Literal["claude", "codex"]


# Per-harness substitution maps. Keys are placeholders that appear in source
# bodies and frontmatter; values are the harness-specific rendered string.
SUBSTITUTIONS: dict[Harness, dict[str, str]] = {
    "claude": {
        "{{HARNESS_NAME}}": "Claude Code",
        "{{SESSION}}": "Claude Code session",
        "{{ASSUME_INSTALLED}}": (
            "Use the `/archagents:install` and `/archagents:auth` commands in "
            "this same plugin instead of trying to install or authenticate the "
            "CLI manually inside this skill."
        ),
        "{{INSTALL_ROUTE}}": "direct the user to `/archagents:install`",
        "{{AUTH_ROUTE}}": "direct the user to `/archagents:auth`",
        "{{AUTH_ROUTE_SHORT}}": "route to `/archagents:auth`",
    },
    "codex": {
        "{{HARNESS_NAME}}": "Codex",
        "{{SESSION}}": "Codex session",
        "{{ASSUME_INSTALLED}}": (
            "Install or upgrade `archagent` if missing, and run "
            "`archagent auth login` if not authenticated."
        ),
        "{{INSTALL_ROUTE}}": "instruct the user to install or upgrade `archagent`",
        "{{AUTH_ROUTE}}": "instruct the user to run `archagent auth login`",
        "{{AUTH_ROUTE_SHORT}}": "run `archagent auth login`",
    },
}


# Conditional block markers. A block is emitted only if its key is in the
# active set for the current target.
#   - claude-skill  → {"SKILL", "CLAUDE_SKILL"}
#   - codex-skill   → {"SKILL", "CODEX_SKILL"}
#   - claude-command → {"CLAUDE_COMMAND"}
CONDITIONAL_SETS: dict[TargetType, set[str]] = {
    "claude-skill": {"SKILL", "CLAUDE_SKILL"},
    "codex-skill": {"SKILL", "CODEX_SKILL"},
    "claude-command": {"CLAUDE_COMMAND"},
}

CONDITIONAL_RE = re.compile(
    r"\{\{#(?P<key>[A-Z_]+)\}\}(?P<body>.*?)\{\{/(?P=key)\}\}",
    flags=re.DOTALL,
)


@dataclass
class Source:
    path: Path
    targets: dict[str, str]  # target_type → dirname or filename
    skill_frontmatter: dict | None
    command_frontmatter: dict | None
    body: str


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Raises ValueError if missing."""
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter block")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter block")
    fm_raw = text[4:end]
    body = text[end + len("\n---\n"):]
    fm = yaml.safe_load(fm_raw)
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a mapping")
    return fm, body


def load_source(path: Path) -> Source:
    text = path.read_text()
    fm, body = split_frontmatter(text)
    targets = fm.get("targets") or {}
    if not targets or not isinstance(targets, dict):
        raise ValueError(f"{path}: missing or empty `targets` block")
    for t in targets:
        if t not in ("claude-skill", "claude-command", "codex-skill"):
            raise ValueError(f"{path}: unknown target type {t!r}")
    return Source(
        path=path,
        targets=targets,
        skill_frontmatter=fm.get("skill"),
        command_frontmatter=fm.get("command"),
        body=body,
    )


def apply_substitutions(text: str, harness: Harness) -> str:
    subs = SUBSTITUTIONS[harness]
    for placeholder, value in subs.items():
        text = text.replace(placeholder, value)
    return text


CONDITIONAL_OPEN_RE = re.compile(r"\{\{#[A-Z_]+\}\}")
CONDITIONAL_CLOSE_RE = re.compile(r"\{\{/[A-Z_]+\}\}")


def apply_conditionals(text: str, target: TargetType) -> str:
    """Expand {{#KEY}}...{{/KEY}} blocks, keeping only those matching target.

    Conditional blocks cannot nest. The non-greedy regex with a backreferenced
    close tag would mishandle nesting and silently leak inner markers into the
    output, so we detect unbalanced open/close marker counts up front and raise.
    """
    open_count = len(CONDITIONAL_OPEN_RE.findall(text))
    close_count = len(CONDITIONAL_CLOSE_RE.findall(text))
    if open_count != close_count:
        raise ValueError(
            f"unbalanced conditional markers in source: {open_count} open, "
            f"{close_count} close. Conditional blocks must be paired and "
            f"cannot nest."
        )

    active = CONDITIONAL_SETS[target]

    def replace(match: re.Match) -> str:
        key = match.group("key")
        inner = match.group("body")
        return inner if key in active else ""

    return CONDITIONAL_RE.sub(replace, text)


def format_frontmatter(fm: dict) -> str:
    """
    Render frontmatter dict as a YAML block matching the Claude Code plugin
    convention: each key on its own line, string values as plain scalars (no
    quoting), lists as flow-style with double-quoted elements.

    This hand-rolled rendering is intentional — PyYAML's default dumper wraps
    long strings and escapes Unicode, producing output that differs from the
    committed files. The Claude Code and Codex harnesses both accept plain
    scalars for the descriptions we write, so no quoting is needed.

    The output is round-trip validated: the rendered block is re-parsed by
    yaml.safe_load and must equal the input dict. This catches any future
    description that contains YAML-hostile characters (leading `-`, ` : `,
    ` #`, etc.) at generate time, instead of letting the harness silently
    fail to parse the skill.
    """
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            # Flow-style list with double-quoted string elements
            items = ", ".join(f'"{item}"' for item in value)
            lines.append(f"{key}: [{items}]")
        elif isinstance(value, str):
            # Plain scalar — no quoting. Validated by round-trip parse below.
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    rendered = "\n".join(lines) + "\n"

    # Round-trip validation: re-parse our hand-rolled YAML and assert it
    # matches the input dict. Any divergence means a frontmatter value
    # contained a YAML-hostile pattern that we silently corrupted.
    yaml_body = "\n".join(lines[1:-1])
    try:
        reparsed = yaml.safe_load(yaml_body)
    except yaml.YAMLError as e:
        raise ValueError(
            f"frontmatter round-trip failed: hand-rolled YAML did not parse. "
            f"A frontmatter value likely contains a YAML-hostile character "
            f"(leading `-`, ` : `, ` #`, unbalanced `'` or `\"`, etc.).\n"
            f"  input: {fm!r}\n  parser error: {e}"
        ) from e
    if reparsed != fm:
        raise ValueError(
            f"frontmatter round-trip failed: rendered YAML parses to a "
            f"different dict than the input. A frontmatter value contains "
            f"a character that changes meaning under YAML parsing.\n"
            f"  input:    {fm!r}\n  reparsed: {reparsed!r}"
        )

    return rendered


def render_target(source: Source, target_type: TargetType) -> tuple[Path, str]:
    """Render one (source, target) pair and return (output_path, content)."""
    target_value = source.targets[target_type]

    # Determine harness
    harness: Harness = "codex" if target_type == "codex-skill" else "claude"

    # Resolve output path
    if target_type == "claude-skill":
        output_path = CLAUDE_PLUGIN_ROOT / "skills" / target_value / "SKILL.md"
    elif target_type == "codex-skill":
        output_path = CODEX_PLUGIN_ROOT / "skills" / target_value / "SKILL.md"
    elif target_type == "claude-command":
        output_path = CLAUDE_PLUGIN_ROOT / "commands" / target_value
    else:
        raise ValueError(f"unknown target type: {target_type}")

    # Pick frontmatter block based on target type
    if target_type in ("claude-skill", "codex-skill"):
        if not source.skill_frontmatter:
            raise ValueError(f"{source.path}: {target_type} requires `skill:` frontmatter block")
        fm = dict(source.skill_frontmatter)  # copy
    else:  # claude-command
        if not source.command_frontmatter:
            raise ValueError(f"{source.path}: {target_type} requires `command:` frontmatter block")
        fm = dict(source.command_frontmatter)

    # Apply substitutions to frontmatter string values
    for key, value in list(fm.items()):
        if isinstance(value, str):
            fm[key] = apply_substitutions(value, harness)

    # Render body: conditionals first, then substitutions.
    # Normalize leading blank lines — the source format allows whitespace
    # between the closing frontmatter fence and the body, but the output
    # should have exactly one blank line between fence and first body line.
    body = apply_conditionals(source.body, target_type)
    body = apply_substitutions(body, harness)
    body = body.lstrip("\n")

    # Stitch frontmatter + blank line + body
    content = format_frontmatter(fm) + "\n" + body

    return output_path, content


def render_all() -> dict[Path, str]:
    """Render every source to every declared target. Return {path: content}."""
    if not SOURCES_DIR.exists():
        raise FileNotFoundError(f"sources dir not found: {SOURCES_DIR}")

    outputs: dict[Path, str] = {}
    for source_path in sorted(SOURCES_DIR.glob("*.md")):
        source = load_source(source_path)
        for target_type in source.targets:
            output_path, content = render_target(source, target_type)  # type: ignore[arg-type]
            if output_path in outputs:
                raise ValueError(
                    f"output collision at {output_path} from {source_path} "
                    f"and a previous source"
                )
            outputs[output_path] = content
    return outputs


def write_outputs(outputs: dict[Path, str]) -> int:
    """Write outputs to disk. Return number of files written."""
    written = 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text() if path.exists() else None
        if existing != content:
            path.write_text(content)
            written += 1
    return written


def check_outputs(outputs: dict[Path, str]) -> list[Path]:
    """Compare generator output to committed files. Return list of paths that differ."""
    diffs: list[Path] = []
    for path, content in outputs.items():
        if not path.exists():
            diffs.append(path)
            continue
        if path.read_text() != content:
            diffs.append(path)
    return diffs


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Diff generator output against committed files; exit 1 if different",
    )
    args = parser.parse_args()

    # Manifest consistency is a precondition check on repo state, independent
    # of content rendering. Run it in both modes so developers regenerating
    # locally also catch drift, not just CI.
    manifest_errors = check_manifest_consistency()
    if manifest_errors:
        print("ERROR: plugin manifest consistency check failed:", file=sys.stderr)
        for err in manifest_errors:
            for line in err.splitlines():
                print(f"  {line}", file=sys.stderr)
        return 2

    try:
        outputs = render_all()
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.check:
        diffs = check_outputs(outputs)
        if diffs:
            print(
                f"FAIL: {len(diffs)} file(s) are out of sync with sources/. "
                "Run `python3 scripts/generate-plugin-content.py` and commit the result.",
                file=sys.stderr,
            )
            for p in diffs:
                print(f"  {p.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1
        print(f"OK: {len(outputs)} file(s) in sync with sources/.")
        return 0

    written = write_outputs(outputs)
    print(f"Wrote {written}/{len(outputs)} file(s) (others already up-to-date).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
