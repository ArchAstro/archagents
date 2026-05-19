#!/usr/bin/env python3
"""
sample_tool — author, validate, regenerate artifacts for, and package
ArchAstro samples under agents/<slug>/.

Subcommands:

  generate         Validate every sample.yaml under agents/ and refresh
                   each sample's .aaignore + the top-level samples.json.
                   Pass --check to exit non-zero on drift (CI uses this).

  new <slug>       Scaffold a fresh sample at agents/<slug>/ — sample.yaml
                   (schema v2 with upload_scripts + deploy_agent),
                   agent.yaml with builtin tools + a participate routine,
                   an empty scripts/ dir, env.example, README.md. Runs
                   `generate` afterward so .aaignore + samples.json
                   include the new entry.

                   Pass --solution to additionally scaffold solution.yaml
                   (catalog-facing wrapper) and a diagrams/ directory
                   with a placeholder architecture diagram. The README
                   references the diagram so the new sample renders
                   correctly on GitHub and in the Solution catalog out
                   of the box.

                   Solution-mode bundles are multi-template by design:
                   solution.yaml's `templates:` is always a list, even
                   for a single AgentTemplate. To add atomic
                   AgentToolTemplate / AgentRoutineTemplate configs (so
                   they can be installed standalone alongside the
                   deployable agent), drop them under tools/ or
                   routines/, add `- template_path:` entries to
                   `templates:`, and reference them from the deployable
                   AgentTemplate via the polymorphic inline shape:

                       tools:
                         - tool_type: builtin              # inline literal
                           builtin_tool_key: knowledge_search
                         - template_path: tools/query-osv.yaml
                         - template_ref: query-osv         # by lookup_key
                       routines:
                         - template_path: routines/daily-scan.yaml

                   Each atomic template owns its own `setup_requirements:`
                   block so users installing just one tool/routine get
                   the env vars + installs it depends on.

  pack <slug>      Validate one sample and build the release tarball
                   <slug>-<version>.tar.gz. Same archive shape CI uploads
                   on merge to main — use it locally for
                   `archastro install sample ./<tarball>` smoke tests.

  validate         Walk every sample's `upload_scripts` source_dir and
                   shell out `archagent validate script --file <path>`
                   per .aascript. Requires `archagent` on $PATH and
                   credentials configured. Used by CI's
                   validate-sample-scripts.yml on push to main; locally
                   it's the same one-shot semantic check.

USAGE
    uv run scripts/sample_tool.py generate
    uv run scripts/sample_tool.py generate --check
    uv run scripts/sample_tool.py new my-new-sample
    uv run scripts/sample_tool.py pack code-review-agent
    uv run scripts/sample_tool.py pack code-review-agent --output-dir dist/
    uv run scripts/sample_tool.py validate
    uv run scripts/sample_tool.py validate --repo-root ./sample-source --cli archagent

Deps and the Python version are pinned in pyproject.toml + uv.lock at
the repo root; `uv run` resolves them automatically. CI runs
`generate --check` on every PR; release-samples.yml delegates to
`pack`; validate-sample-scripts.yml delegates to `validate`.
Regenerate locally and commit before pushing.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

from _sample_lib.generate import run_generate
from _sample_lib.pack import run_pack
from _sample_lib.paths import REPO_ROOT
from _sample_lib.scaffold import run_new
from _sample_lib.validate_scripts import (
    DEFAULT_SCRIPT_TIMEOUT_SECONDS,
    run_validate,
)
from _sample_lib.validation import SampleError


def _build_parser() -> argparse.ArgumentParser:
    description = (__doc__ or "").strip().splitlines()[0]
    parser = argparse.ArgumentParser(
        prog="sample_tool",
        description=description,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate",
        help="Regenerate .aaignore for each sample + the top-level samples.json.",
    )
    gen.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if committed artifacts differ from regeneration.",
    )

    new = sub.add_parser(
        "new",
        help="Scaffold a new sample (under agents/ by default, or anywhere via --target-dir).",
    )
    new.add_argument("slug", help="kebab-case slug — used as the directory + install handle.")
    new.add_argument(
        "--name",
        help="Pretty display name (defaults to the slug Title Cased).",
    )
    new.add_argument(
        "--tagline",
        help="One-line tagline shown in the sample catalog.",
    )
    new.add_argument(
        "--target-dir",
        type=pathlib.Path,
        default=None,
        help=(
            "Parent directory where <slug>/ should be scaffolded. Defaults "
            "to the current working directory. Pass the archagents repo's "
            "agents/ to scaffold into the catalog — that path additionally "
            "refreshes .aaignore + samples.json."
        ),
    )
    new.add_argument(
        "--solution",
        action="store_true",
        help=(
            "Also scaffold solution.yaml (catalog-facing Solution config) "
            "with a canonical `templates:` list (one entry by default; "
            "add more atomic AgentToolTemplate / AgentRoutineTemplate "
            "files under tools/ or routines/ to ship standalone-"
            "installable tools/routines alongside the deployable agent). "
            "Also scaffolds a diagrams/ directory with a placeholder "
            "architecture diagram and bumps the README to reference it."
        ),
    )

    pack = sub.add_parser(
        "pack",
        help="Validate one sample and build its release tarball.",
    )
    pack.add_argument(
        "slug",
        help=(
            "Path to the sample directory, always cwd-relative (e.g. "
            "`my-sample`, `./my-sample`, or `agents/code-review-agent` "
            "from the archagents repo root). Absolute paths also work. "
            "The tarball name derives from the directory's basename."
        ),
    )
    pack.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Where to write the .tar.gz (defaults to the current directory).",
    )

    validate = sub.add_parser(
        "validate",
        help="Run `archagent validate script` over every sample's scripts.",
    )
    validate.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help=(
            "Repository root containing the agents/ directory to validate. "
            "Defaults to the archagents repo root. CI uses this to point at "
            "an untrusted PR checkout while running the validator from a "
            "trusted ref."
        ),
    )
    validate.add_argument(
        "--cli",
        default=os.environ.get("ARCHAGENTS_SCRIPT_VALIDATOR_CLI", "archagent"),
        help="CLI executable to run (default: archagent).",
    )
    validate.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_SCRIPT_TIMEOUT_SECONDS,
        help=f"Per-script CLI timeout in seconds (default: {DEFAULT_SCRIPT_TIMEOUT_SECONDS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        return run_generate(check=args.check)
    if args.command == "new":
        return run_new(
            args.slug,
            args.name,
            args.tagline,
            args.target_dir,
            with_solution=args.solution,
        )
    if args.command == "pack":
        return run_pack(args.slug, args.output_dir.resolve())
    if args.command == "validate":
        return run_validate(args.repo_root, args.cli, args.timeout_seconds)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SampleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
