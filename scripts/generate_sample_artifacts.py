#!/usr/bin/env python3
"""
Generate per-sample deploy artifacts and the top-level samples.json catalog
from each sample's sample.yaml.

For every agents/<slug>/ directory:

  - Read sample.yaml (version, name, tagline, min_cli_version, deploy_mode,
    and — when deploy_mode is `generated` — capabilities).

  - Always write .aaignore. The sample directory is deploy.sh-authoritative,
    so `deploy configs` should not re-upload anything inside it. We enumerate
    the top-level contents (excluding .aaignore and sample.yaml themselves)
    so the ignore list stays accurate even as new files are added.

  - If deploy_mode is `generated`, write deploy.sh from a template driven
    by `capabilities`. Covers the vanilla case: scripts upload, optional
    env.example loading, agent deploy. Non-vanilla samples (skills, post-
    deploy uploads, schema+routine attachment) set deploy_mode: custom and
    commit their own deploy.sh.

After all samples, write samples.json at the repo root — the catalog the
CLI reads for `listSamples()`. One network round trip to replace the
current tree-API + N raw-blob walk.

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
SCHEMA_VERSION = 1

# Always-excluded entries in .aaignore. The sample dir itself is
# deploy.sh-authoritative — nothing inside should be `deploy configs`'d —
# so we just enumerate every top-level entry at generate time. These two
# filenames are the only ones the generator itself owns; they stay out of
# the enumeration so the generated file doesn't list itself.
AAIGNORE_SKIP = frozenset({".aaignore"})

# Semver-ish: `v<MAJOR>.<MINOR>.<PATCH>`. Prereleases (rc, beta) deferred
# — the samples catalog ships stable tags only for now.
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Keep in sync with the CLI's min_cli_version check. Loose semver match.
CLI_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class SampleError(Exception):
    """Raised for any validation problem in a sample.yaml or its directory."""


def _display_path(path: pathlib.Path) -> pathlib.Path:
    """
    Render `path` relative to REPO_ROOT when possible (clean error messages
    in CI), absolute when not (tests pass tmp paths outside the repo).
    """
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

    # Deterministic order. Keeps diffs clean across runs.
    samples.sort(key=lambda s: s["slug"])

    planned: dict[pathlib.Path, str] = {}
    for sample in samples:
        sample_dir = AGENTS_DIR / sample["slug"]
        planned[sample_dir / ".aaignore"] = render_aaignore(sample_dir)
        if sample["deploy_mode"] == "generated":
            planned[sample_dir / "deploy.sh"] = render_deploy_sh(sample)
    planned[MANIFEST_PATH] = render_manifest(samples)

    if args.check:
        return check_drift(planned)

    for path, body in planned.items():
        write_if_changed(path, body)
        # deploy.sh is the only shell script we write; set +x so
        # maintainers committing from a fresh checkout get an immediately
        # runnable file. tarball packaging later will rely on this bit
        # surviving the git tree.
        if path.name == "deploy.sh":
            path.chmod(0o755)
    return 0


# --- loading + validation ---------------------------------------------------


def load_all_samples() -> list[dict[str, Any]]:
    """Parse every agents/<slug>/sample.yaml into a validated dict."""
    samples: list[dict[str, Any]] = []
    for sample_dir in sorted(AGENTS_DIR.iterdir()):
        if not sample_dir.is_dir():
            continue
        yaml_path = sample_dir / "sample.yaml"
        if not yaml_path.exists():
            raise SampleError(
                f"{sample_dir.relative_to(REPO_ROOT)}: missing sample.yaml. "
                f"Every sample directory must declare its version and metadata."
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

    # schema_version is checked for future-proofing. Bumping it is a
    # signal that this generator needs updating alongside the change.
    schema_version = raw.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise SampleError(
            f"{where}: schema_version must be {SCHEMA_VERSION}, got {schema_version!r}. "
            f"Update the generator if the schema has intentionally evolved."
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
            f'{where}: min_cli_version must be a string like "0.25.0", got {min_cli_version!r}'
        )

    deploy_mode = raw.get("deploy_mode")
    if deploy_mode not in ("generated", "custom"):
        raise SampleError(
            f'{where}: deploy_mode must be "generated" or "custom", got {deploy_mode!r}'
        )

    capabilities: dict[str, bool] = {}
    if deploy_mode == "generated":
        caps = raw.get("capabilities")
        if not isinstance(caps, dict):
            raise SampleError(
                f"{where}: deploy_mode=generated requires a capabilities mapping"
            )
        for key in ("scripts", "skills", "agent", "env_example"):
            val = caps.get(key)
            if not isinstance(val, bool):
                raise SampleError(
                    f"{where}: capabilities.{key} must be true or false, got {val!r}"
                )
            capabilities[key] = val
        validate_generated_capabilities(slug, capabilities, source)
    elif "capabilities" in raw:
        raise SampleError(
            f"{where}: deploy_mode=custom must not declare a capabilities block "
            f"(it would be silently ignored — remove it to avoid confusion)"
        )

    return {
        "slug": slug,
        "version": version,
        "name": name.strip(),
        "tagline": tagline.strip(),
        "min_cli_version": min_cli_version,
        "deploy_mode": deploy_mode,
        "capabilities": capabilities,
    }


def validate_generated_capabilities(
    slug: str, caps: dict[str, bool], source: pathlib.Path
) -> None:
    """
    Cross-check capabilities against what's actually on disk. Catches the
    common mistake of setting `skills: true` without a skills/ dir (the
    generated deploy.sh would then loop over nothing and silently succeed).
    """
    sample_dir = source.parent
    where = _display_path(source)

    if caps["scripts"] and not (sample_dir / "scripts").is_dir():
        raise SampleError(f"{where}: capabilities.scripts=true but no scripts/ dir exists")
    if caps["skills"] and not (sample_dir / "skills").is_dir():
        raise SampleError(f"{where}: capabilities.skills=true but no skills/ dir exists")
    if caps["agent"] and not (sample_dir / "agent.yaml").is_file():
        raise SampleError(f"{where}: capabilities.agent=true but no agent.yaml exists")
    if caps["env_example"] and not (sample_dir / "env.example").is_file():
        raise SampleError(
            f"{where}: capabilities.env_example=true but no env.example exists"
        )


# --- rendering --------------------------------------------------------------


def render_aaignore(sample_dir: pathlib.Path) -> str:
    """
    Produce the sample's .aaignore. Every top-level entry in the sample dir
    is listed so `deploy configs` treats the sample as deploy.sh-authoritative
    and skips it entirely.
    """
    entries: list[str] = []
    for child in sorted(sample_dir.iterdir()):
        if child.name in AAIGNORE_SKIP:
            continue
        # Directories get a trailing slash; plain files don't. Matches the
        # gitignore-style convention the CLI's aaignore parser expects.
        entries.append(f"{child.name}/" if child.is_dir() else child.name)
    header = (
        "# Auto-generated by scripts/generate_sample_artifacts.py — do not edit.\n"
        "#\n"
        "# deploy.sh is the authoritative entry point for this sample. Every\n"
        "# file below is deployed (or ignored) by deploy.sh or its helpers —\n"
        "# `<cli> deploy configs` should skip the entire directory.\n"
    )
    return header + "\n".join(entries) + "\n"


def render_deploy_sh(sample: dict[str, Any]) -> str:
    """
    Template the generated deploy.sh from capability flags. Ordered so the
    output is readable as a flat script rather than a template rendering.
    """
    caps = sample["capabilities"]
    name = sample["name"]
    slug = sample["slug"]

    out: list[str] = []
    out.append("#!/usr/bin/env bash")
    out.append(f"# Auto-generated by scripts/generate_sample_artifacts.py from sample.yaml.")
    out.append(f"# Edit sample.yaml and rerun the generator — do not hand-edit this file.")
    out.append(f"#")
    out.append(f"# Deploy the {name} sample.")
    out.append(f"#")
    out.append(f"# Usage:  ./deploy.sh")
    out.append("")
    out.append("set -euo pipefail")
    out.append("")
    out.append('cd "$(dirname "$0")"')
    out.append("")
    out.extend(cli_detection_block())
    out.append("")
    if caps["env_example"]:
        out.extend(env_loader_block())
        out.append("")
    if caps["scripts"]:
        out.extend(scripts_block())
        out.append("")
    if caps["agent"]:
        out.extend(agent_block())
        out.append("")
    out.extend(finished_block(name, slug))

    # Trailing newline so POSIX-compliant tools don't complain.
    return "\n".join(out) + "\n"


def cli_detection_block() -> list[str]:
    """
    Inlined CLI resolver. Duplicated in every generated deploy.sh because
    each sample is distributed as a standalone tarball — no shared helper
    travels with it. Keep this template in sync if the logic changes.
    """
    return [
        "# Resolve which CLI binary to invoke (archastro vs archagent). Order:",
        "#   1. $ARCHASTRO_CLI env override",
        "#   2. Nearest archastro.json / archagent.json walking up from here",
        "#   3. First of archastro / archagent on PATH",
        "#   4. Fallback: archagent",
        'if [[ -n "${ARCHASTRO_CLI:-}" ]]; then',
        '  CLI="$ARCHASTRO_CLI"',
        "else",
        '  CLI=""',
        '  _dir="$PWD"',
        '  while [[ -n "$_dir" && "$_dir" != "/" ]]; do',
        '    if [[ -f "$_dir/archastro.json" ]]; then CLI="archastro"; break; fi',
        '    if [[ -f "$_dir/archagent.json" ]]; then CLI="archagent"; break; fi',
        '    _dir="$(dirname "$_dir")"',
        "  done",
        "  unset _dir",
        '  if [[ -z "$CLI" ]]; then',
        '    if   command -v archastro >/dev/null 2>&1; then CLI="archastro"',
        '    elif command -v archagent >/dev/null 2>&1; then CLI="archagent"',
        '    else CLI="archagent"',
        "    fi",
        "  fi",
        "fi",
    ]


def env_loader_block() -> list[str]:
    return [
        "if [[ ! -f .env ]]; then",
        '  echo "ℹ️  No .env file found. Copy env.example to .env if you need custom values."',
        "else",
        "  # shellcheck disable=SC1091",
        "  source .env",
        "fi",
    ]


def scripts_block() -> list[str]:
    return [
        'echo "📜 Deploying scripts..."',
        "for script in scripts/*.aascript; do",
        '  name=$(basename "$script" .aascript | tr \'_\' \'-\')',
        '  pretty=$(echo "$name" | tr \'-\' \' \')',
        '  echo "  → $name"',
        '  "$CLI" create scripts \\',
        '    --id "$name" \\',
        '    --name "$pretty" \\',
        '    --file "$script" 2>/dev/null || \\',
        '  "$CLI" update scripts "$name" --file "$script"',
        "done",
    ]


def agent_block() -> list[str]:
    return [
        'echo "🤖 Deploying agent..."',
        '"$CLI" deploy agent agent.yaml',
    ]


def finished_block(name: str, slug: str) -> list[str]:
    return [
        'echo ""',
        f'echo "✅ {name} deployed."',
        'echo ""',
        'echo "Inspect the agent:"',
        f'echo "  $CLI describe agent {slug}"',
    ]


def render_manifest(samples: list[dict[str, Any]]) -> str:
    """
    Build samples.json. The CLI reads this file directly to populate its
    sample-selection menu — one network round trip for the whole catalog.

    Deterministic: no `generated_at` timestamp because the file would
    otherwise diff on every run and `--check` mode would fail spuriously.
    Per-version release dates come from the GitHub Release timestamp,
    which is the right source of truth.
    """
    manifest = {
        "$schema_version": SCHEMA_VERSION,
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
    # ensure_ascii=False so em-dashes and other UTF-8 don't render as
    # — escapes — easier for humans to scan.
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


# --- write / drift check ----------------------------------------------------


def write_if_changed(path: pathlib.Path, body: str) -> None:
    """Only write when the content would change — keeps mtimes stable for tar."""
    if path.exists() and path.read_text() == body:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def check_drift(planned: dict[pathlib.Path, str]) -> int:
    """Return 1 if any committed file diverges from the planned output."""
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
