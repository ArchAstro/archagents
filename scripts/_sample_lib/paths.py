"""
Paths + constants shared across the sample_tool subcommands. Kept in
one module so validation/render/generate/scaffold/pack all agree on
schema versions, regex shapes, and the on-disk layout.

REPO_ROOT walks three parents up: this file lives at
scripts/_sample_lib/paths.py, so parents[2] is the repo root.
"""
from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
# Catalog-facing Solution bundles live under solutions/ by convention.
# Every sample under solutions/ ships with solution.yaml + a `-sample`
# slug suffix; sample_tool walks SAMPLE_ROOTS so generate / pack /
# validate / lint discover entries from either directory.
SOLUTIONS_DIR = REPO_ROOT / "solutions"
SAMPLE_ROOTS = (AGENTS_DIR, SOLUTIONS_DIR)
MANIFEST_PATH = REPO_ROOT / "samples.json"
MANIFEST_SCHEMA_VERSION = 1

# Bump sample.yaml's schema_version to 2 to signal the DSL migration:
# capabilities / deploy_mode are gone; a `steps:` block is now required.
# Samples declaring schema_version: 1 in this repo would be an
# un-migrated holdover — the validator rejects them to force the
# author's attention.
SAMPLE_SCHEMA_VERSION = 2

# Always-excluded entries in .aaignore. The sample dir itself is
# install-authoritative — every file inside is managed by the DSL
# executor — so we just enumerate every top-level entry at generate
# time. These two filenames stay out of the enumeration so the
# generated file doesn't list itself.
AAIGNORE_SKIP = frozenset({".aaignore"})

# Accepted file extensions for ArchAstro scripts. `.aascript` is the
# original/default extension; `.agentscript` is the newer name and is
# also accepted by the platform executor + the CLI's validate command.
# Both are stripped to the bare stem for setup_requirements'
# script_ref cross-reference.
SCRIPT_EXTENSIONS = frozenset({".aascript", ".agentscript"})

# Semver-ish: `v<MAJOR>.<MINOR>.<PATCH>`. Prereleases deferred.
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Loose semver match for min_cli_version. Keep in sync with the CLI's
# update-check.ts compareSemver accepted shapes.
CLI_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Kebab-case slug: lowercase letters/digits, dashes between segments.
# Enforced by `sample_tool.py new` so we don't accept slugs the CLI
# install command couldn't address cleanly.
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# DSL verb vocabulary. Mirrors @archastro/samples-catalog's schema.ts
# (the source of truth in TS). Keep in sync with the samples-catalog
# package; CI would fail to deploy a sample the CLI can't execute, so
# drift here just becomes a clear validation error.
STEP_VERBS = {
    "upload_scripts": {
        "required": {"source_dir"},
        "optional": {"glob"},
    },
    "upload_skills": {
        "required": {"source_dir"},
        "optional": set(),
    },
    "upload_configs": {
        "required": {"source_dir"},
        "optional": {"glob"},
    },
    "deploy_agent": {
        "required": {"template_file"},
        "optional": set(),
    },
    "deploy_solution": {
        "required": {"solution_file"},
        "optional": set(),
    },
    "upload_files": {
        "required": {"source_dir", "installation_kind", "source_type"},
        "optional": {"glob", "content_type"},
    },
}

# `setup_requirements:` entries in agent.yaml. Mirrors the discriminated
# union in @archastro/samples-catalog's schema.ts. Each entry becomes
# one row in the platform's `agent_health_actions` table at install
# time (source: setup, status: pending). Validating shape at packaging
# time catches mistakes before the sample ships.
SETUP_REQUIREMENT_KINDS = {
    "env_var": {
        "required": {"key", "scope", "description"},
        "optional": {
            "secret",
            "example",
            "validate_regex",
            "required",
            "title",
            "depends_on",
        },
    },
    "install": {
        "required": {"installation_kind", "description"},
        "optional": {"required", "title", "depends_on"},
    },
    "custom": {
        "required": {"id", "title", "description", "verify"},
        "optional": {"required", "depends_on"},
    },
}

ENV_VAR_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ENV_VAR_SCOPES = frozenset({"org_env_var", "agent_env_var"})


def display_path(path: pathlib.Path) -> str:
    """Render `path` relative to REPO_ROOT when possible (cleaner errors in CI)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
