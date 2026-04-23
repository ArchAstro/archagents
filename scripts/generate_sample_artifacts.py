#!/usr/bin/env python3
"""
Generate per-sample artifacts + the top-level samples.json catalog from
each sample's sample.yaml.

For every agents/<slug>/ directory:

  - Read sample.yaml (schema_version, version, name, tagline,
    min_cli_version, steps) and validate the DSL shape.

  - Always write .aaignore. Sample directories are deploy-atomic —
    the whole thing gets installed by `archastro install agentsample
    <slug>` via the DSL executor, so `archastro deploy configs`
    shouldn't re-upload anything inside. We enumerate the top-level
    contents (excluding .aaignore + sample.yaml themselves) so the
    ignore list stays accurate as files are added.

After all samples, write samples.json at the repo root — the catalog
the CLI + portal read for `listSamples()`.

NOTE: We no longer emit deploy.sh. The user-facing flow is now
`archastro install agentsample <slug>`, which fetches the release
tarball, parses this sample.yaml's `steps:` block, and runs the
@archastro/samples-catalog DSL executor. Nothing lands on disk.
Sample authors iterating on a local checkout can use
`archastro install sample .` instead. The deprecated deploy.sh files
(and per-sample upload-rules.sh / upload-knowledge.sh helpers) are
deleted as part of the migration.

USAGE
    python3 scripts/generate_sample_artifacts.py           # write outputs
    python3 scripts/generate_sample_artifacts.py --check   # exit 1 on drift

CI runs --check on every PR. Regenerate locally and commit before pushing.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
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

# Semver-ish: `v<MAJOR>.<MINOR>.<PATCH>`. Prereleases deferred.
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Loose semver match for min_cli_version. Keep in sync with the CLI's
# update-check.ts compareSemver accepted shapes.
CLI_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

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
    "upload_files": {
        "required": {"source_dir", "installation_kind", "source_type"},
        "optional": {"glob", "content_type"},
    },
}


class SampleError(Exception):
    """Raised for any validation problem in a sample.yaml or its directory."""


def _display_path(path: pathlib.Path) -> pathlib.Path:
    """Render `path` relative to REPO_ROOT when possible (cleaner errors in CI)."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if committed artifacts differ from regeneration.",
    )
    args = parser.parse_args()

    samples = load_all_samples()
    samples.sort(key=lambda s: s["slug"])

    planned: dict[pathlib.Path, str] = {}
    for sample in samples:
        sample_dir = AGENTS_DIR / sample["slug"]
        planned[sample_dir / ".aaignore"] = render_aaignore(sample_dir)
    planned[MANIFEST_PATH] = render_manifest(samples)

    if args.check:
        return check_drift(planned)

    for path, body in planned.items():
        write_if_changed(path, body)
    return 0


# --- loading + validation ---------------------------------------------------


def load_all_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for sample_dir in sorted(AGENTS_DIR.iterdir()):
        if not sample_dir.is_dir():
            continue
        yaml_path = sample_dir / "sample.yaml"
        if not yaml_path.exists():
            raise SampleError(
                f"{sample_dir.relative_to(REPO_ROOT)}: missing sample.yaml. "
                f"Every sample directory must declare its version + DSL steps."
            )
        raw = yaml.safe_load(yaml_path.read_text())
        sample = validate_sample(sample_dir.name, raw, yaml_path)
        samples.append(sample)
    if not samples:
        raise SampleError(f"No samples found under {AGENTS_DIR}")
    return samples


def validate_sample(slug: str, raw: Any, source: pathlib.Path) -> dict[str, Any]:
    """
    Validate a sample.yaml. Errors point at source path + the offending key
    so a CI failure tells the author exactly where to look.
    """
    where = _display_path(source)
    if not isinstance(raw, dict):
        raise SampleError(f"{where}: top-level must be a mapping, got {type(raw).__name__}")

    schema_version = raw.get("schema_version")
    if schema_version != SAMPLE_SCHEMA_VERSION:
        raise SampleError(
            f"{where}: schema_version must be {SAMPLE_SCHEMA_VERSION}, got {schema_version!r}. "
            f"If you're updating a sample from an earlier schema, bump schema_version to "
            f"{SAMPLE_SCHEMA_VERSION} and replace the old capabilities/deploy_mode fields "
            f"with a `steps:` block (see docs/ for the DSL reference)."
        )

    version = raw.get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise SampleError(
            f'{where}: version must be a string like "v1.2.3", got {version!r}'
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SampleError(f"{where}: name must be a non-empty string")

    tagline = raw.get("tagline")
    if not isinstance(tagline, str) or not tagline.strip():
        raise SampleError(f"{where}: tagline must be a non-empty string")

    min_cli_version = raw.get("min_cli_version")
    if not isinstance(min_cli_version, str) or not CLI_VERSION_RE.match(min_cli_version):
        raise SampleError(
            f'{where}: min_cli_version must be a string like "0.28.0", got {min_cli_version!r}'
        )

    # steps: is the new required block. `post_install:` is accepted as
    # an alias during the TS samples-catalog's transition, but we insist
    # on `steps:` in source of truth (sample.yaml) so authors converge
    # on one name.
    steps_raw = raw.get("steps")
    if steps_raw is None:
        raise SampleError(
            f"{where}: missing `steps:` block. Every sample must declare its "
            f"deploy sequence. See agents/code-review-agent/sample.yaml for the "
            f"simplest shape; the full DSL reference is in @archastro/samples-catalog."
        )
    validate_steps(slug, steps_raw, source)

    # Defensive check against authors leaving behind the old schema's
    # fields after migrating.
    for legacy_key in ("deploy_mode", "capabilities"):
        if legacy_key in raw:
            raise SampleError(
                f"{where}: `{legacy_key}` is from the old (schema_version: 1) "
                f"format and no longer has any effect — remove it. Deploy "
                f"behavior is now declared in `steps:`."
            )

    return {
        "slug": slug,
        "version": version,
        "name": name.strip(),
        "tagline": tagline.strip(),
        "min_cli_version": min_cli_version,
        "steps": steps_raw,
    }


def validate_steps(slug: str, steps: Any, source: pathlib.Path) -> None:
    """
    Shape-validate the `steps:` block. Catches obvious structural errors
    at packaging time; the TS executor does a full zod validation at
    runtime too, so this is the fast-feedback gate, not the safety net.
    """
    where = _display_path(source)
    if not isinstance(steps, list):
        raise SampleError(f"{where}: steps must be a list, got {type(steps).__name__}")

    # Each sample must deploy exactly one agent, so the list must contain
    # exactly one `deploy_agent` step. Catches the "wrote all the scripts
    # + skills, forgot to deploy the agent" mistake.
    deploy_count = 0
    sample_dir = source.parent

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise SampleError(
                f"{where}: steps[{idx}] must be a mapping, got {type(step).__name__}"
            )
        verb = step.get("type")
        if verb not in STEP_VERBS:
            valid = ", ".join(sorted(STEP_VERBS))
            raise SampleError(
                f"{where}: steps[{idx}].type {verb!r} is not a known verb. "
                f"Valid verbs: {valid}."
            )

        spec = STEP_VERBS[verb]
        supplied = set(step.keys()) - {"type"}
        missing = spec["required"] - supplied
        if missing:
            raise SampleError(
                f"{where}: steps[{idx}] ({verb}) missing required fields: "
                f"{', '.join(sorted(missing))}"
            )
        unknown = supplied - spec["required"] - spec["optional"]
        if unknown:
            raise SampleError(
                f"{where}: steps[{idx}] ({verb}) has unknown fields: "
                f"{', '.join(sorted(unknown))}"
            )
        for field in supplied:
            value = step[field]
            if not isinstance(value, str) or not value.strip():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}).{field} must be a non-empty string, "
                    f"got {value!r}"
                )

        # Directory / file reality checks — catches `source_dir: skills`
        # on a sample that doesn't ship a skills/ subdirectory.
        if "source_dir" in step:
            target = sample_dir / step["source_dir"]
            if not target.is_dir():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}) source_dir "
                    f"{step['source_dir']!r} does not exist in {slug}/"
                )
        if "template_file" in step:
            target = sample_dir / step["template_file"]
            if not target.is_file():
                raise SampleError(
                    f"{where}: steps[{idx}] ({verb}) template_file "
                    f"{step['template_file']!r} does not exist in {slug}/"
                )

        if verb == "deploy_agent":
            deploy_count += 1

    if deploy_count != 1:
        raise SampleError(
            f"{where}: steps must contain exactly one deploy_agent step "
            f"(found {deploy_count}). Every sample deploys exactly one agent."
        )


# --- rendering --------------------------------------------------------------


def render_aaignore(sample_dir: pathlib.Path) -> str:
    """
    Produce the sample's .aaignore. Every top-level entry in the sample
    dir is listed so `archastro deploy configs` treats the sample as
    install-authoritative and skips it entirely — the DSL executor
    handles every file inside.
    """
    entries: list[str] = []
    for child in sorted(sample_dir.iterdir()):
        if child.name in AAIGNORE_SKIP:
            continue
        entries.append(f"{child.name}/" if child.is_dir() else child.name)
    header = (
        "# Auto-generated by scripts/generate_sample_artifacts.py — do not edit.\n"
        "#\n"
        "# This sample is installed via `archastro install agentsample <slug>`,\n"
        "# which reads sample.yaml's `steps:` block and runs the DSL executor.\n"
        "# `archastro deploy configs` should skip every file inside this\n"
        "# directory.\n"
    )
    return header + "\n".join(entries) + "\n"


def render_manifest(samples: list[dict[str, Any]]) -> str:
    """
    Build samples.json. The CLI + portal read this file directly to
    populate their sample-selection menus — one network round trip for
    the whole catalog.

    Deterministic: no `generated_at` timestamp so `--check` is stable.
    Per-version release dates come from the GitHub Release timestamp.
    """
    manifest = {
        "$schema_version": MANIFEST_SCHEMA_VERSION,
        "samples": [
            {
                "slug": s["slug"],
                "name": s["name"],
                "tagline": s["tagline"],
                "current_version": s["version"],
                "min_cli_version": s["min_cli_version"],
            }
            for s in samples
        ],
    }
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


# --- write / drift check ----------------------------------------------------


def write_if_changed(path: pathlib.Path, body: str) -> None:
    """Only write when the content would change — keeps mtimes stable for tar."""
    if path.exists() and path.read_text() == body:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def check_drift(planned: dict[pathlib.Path, str]) -> int:
    drifted: list[pathlib.Path] = []
    for path, body in planned.items():
        if not path.exists() or path.read_text() != body:
            drifted.append(path)
    if not drifted:
        return 0
    print(
        "The following files are out of date. Run:\n"
        "    python3 scripts/generate_sample_artifacts.py\n"
        "and commit the result.\n",
        file=sys.stderr,
    )
    for path in drifted:
        print(f"  - {path.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SampleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
