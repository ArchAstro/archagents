"""
The `new` subcommand: scaffold agents/<slug>/ with the minimum files
that pass the validator (sample.yaml v2 with upload_scripts +
deploy_agent, an agent.yaml with builtin tools + a participate
routine, an empty scripts/ dir with a .gitkeep, env.example, README).

After writing the files we run the generator so .aaignore +
samples.json land in the same commit. That keeps `--check` green
without a second manual step.

When --solution is passed, additionally scaffolds a `solution.yaml`
(catalog-facing wrapper), a `diagrams/` directory with a placeholder
architecture diagram, and the matching Image config wrapper. The
README is updated to reference the diagram so the scaffold renders
correctly on GitHub and in the Solution catalog out of the box.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from .generate import run_generate
from .paths import AGENTS_DIR, SLUG_RE
from .validation import SampleError

# Scaffolded sample.yaml uses v0.1.0; the matching solution_version
# follows the same shape so authors only have to bump in one place
# when the sample-as-a-whole gets a new release.
DEFAULT_SOLUTION_VERSION = "v0.1.0"


def _pretty_name_from_slug(slug: str) -> str:
    """`code-review-agent` -> `Code Review Agent`. Authors edit afterward."""
    return " ".join(part.capitalize() for part in slug.split("-"))


def _sample_yaml(slug: str, name: str, tagline: str, with_solution: bool = False) -> str:
    # Solution-mode samples wrap the deploy as `deploy_solution` so the
    # samples-catalog executor imports the catalog wrapper instead of
    # provisioning a runtime agent. The wrapped template body lives at
    # agents/<slug>.yaml so solution.yaml can use path-mode
    # `template_path` by default.
    if with_solution:
        deploy_block = (
            "  - type: deploy_solution\n"
            "    solution_file: solution.yaml\n"
        )
    else:
        deploy_block = (
            "  - type: deploy_agent\n"
            "    template_file: agent.yaml\n"
        )
    return (
        "# sample.yaml is the source of truth for this sample's catalog metadata\n"
        "# and deploy sequence. Edit it, then run:\n"
        "#\n"
        "#   uv run scripts/sample_tool.py generate\n"
        "#\n"
        "# to regenerate committed artifacts. CI fails if this file changes\n"
        "# without the generated artifacts being regenerated in the same PR.\n"
        "#\n"
        "# Users install this sample with:\n"
        "#\n"
        f"#   archastro install agentsample {slug}\n"
        "#\n"
        "# which streams the release tarball and runs the `steps:` block below\n"
        "# against the caller's app.\n"
        "\n"
        "schema_version: 2\n"
        "\n"
        "# Bump this to cut a new per-sample release. CI creates GitHub Release\n"
        '# "<slug>-<version>" with a tarball of this directory on every merge\n'
        "# to main where the version tag does not yet exist.\n"
        "version: v0.1.0\n"
        "\n"
        f'name: "{name}"\n'
        f'tagline: "{tagline}"\n'
        "\n"
        "# Minimum CLI version that can install this sample. `install agentsample`\n"
        "# + the DSL executor ship in 0.28.0.\n"
        'min_cli_version: "0.28.0"\n'
        "\n"
        "# Deploy steps. Executed top-to-bottom against the caller's app. See\n"
        "# @archastro/samples-catalog for the full DSL reference.\n"
        "steps:\n"
        "  - type: upload_scripts\n"
        "    source_dir: scripts\n"
        + deploy_block
    )


def _agent_yaml(slug: str, name: str, with_solution: bool = False) -> str:
    # `agent_key:` belongs to the deploy_agent flow (where it becomes
    # the provisioned agent's lookup_key). Solution-wrapped templates
    # must not carry it — the Python validator + the TS samples-catalog
    # reject the field on the deploy_solution path, since solution
    # import only publishes a library row and never provisions an agent.
    agent_key_line = "" if with_solution else f"agent_key: {slug}\n"
    return (
        "kind: AgentTemplate\n"
        f"{agent_key_line}"
        f"name: {name}\n"
        "identity: |\n"
        f"  You are {name}.\n"
        "\n"
        "  TODO: describe the agent's job, the events it responds to, the\n"
        "  tools it should reach for, and any guardrails the model must\n"
        "  respect. Replace this placeholder before deploying.\n"
        "\n"
        "tools:\n"
        "  - kind: builtin\n"
        "    builtin_tool_key: knowledge_search\n"
        "    status: active\n"
        "  - kind: builtin\n"
        "    builtin_tool_key: long_term_memory\n"
        "    status: active\n"
        "  - kind: builtin\n"
        "    builtin_tool_key: memory\n"
        "    status: active\n"
        "  - kind: builtin\n"
        "    builtin_tool_key: skills\n"
        "    status: active\n"
        "\n"
        "routines:\n"
        "  - name: Participate in conversations\n"
        "    description: Join threads when added so users can talk to this agent directly.\n"
        "    handler_type: preset\n"
        "    preset_name: participate\n"
        "    event_type: thread.session.join\n"
        "    event_config:\n"
        "      thread.session.join:\n"
        "        filters: {}\n"
        "    status: active\n"
        "\n"
        "installations:\n"
        "  - kind: memory/long-term\n"
        "    config: {}\n"
        "  - kind: archastro/thread\n"
        "    config: {}\n"
        "\n"
        "# Post-install checklist. Drop entries in here as you add env vars,\n"
        "# integrations, or custom verifier scripts the user must wire up\n"
        "# before the agent can run. See agents/code-review-agent/agent.yaml\n"
        "# for env_var / install / custom examples.\n"
        "setup_requirements: []\n"
        "\n"
        "metadata:\n"
        "  category: general\n"
        '  version: "1.0"\n'
    )


def _readme(slug: str, name: str, tagline: str) -> str:
    return (
        f"# {name}\n"
        "\n"
        f"{tagline}\n"
        "\n"
        "## What it does\n"
        "\n"
        "TODO: describe the agent's job and the events it responds to.\n"
        "\n"
        "## Install\n"
        "\n"
        "```sh\n"
        f"archastro install agentsample {slug}\n"
        "```\n"
        "\n"
        "## Local iteration\n"
        "\n"
        "To pack and install from a local checkout:\n"
        "\n"
        "```sh\n"
        f"uv run scripts/sample_tool.py pack {slug}\n"
        f"archastro install sample ./{slug}-<version>.tar.gz\n"
        "```\n"
        "\n"
        "Edit `agent.yaml` to change identity, tools, routines, and setup\n"
        "requirements. Edit `sample.yaml` to bump the version and adjust the\n"
        "deploy steps. Then run:\n"
        "\n"
        "```sh\n"
        "uv run scripts/sample_tool.py generate\n"
        "```\n"
        "\n"
        "to refresh `.aaignore` and `samples.json` before committing.\n"
    )


def _readme_with_solution(slug: str, name: str, tagline: str) -> str:
    """README variant for --solution scaffolds: surfaces the placeholder diagram."""
    return (
        f"# {name}\n"
        "\n"
        f"{tagline}\n"
        "\n"
        "## Architecture\n"
        "\n"
        "![Architecture overview](diagrams/architecture.svg)\n"
        "\n"
        "TODO: replace diagrams/architecture.svg with the real diagram.\n"
        "solution.yaml refs it directly via `asset_path`, so editing the SVG\n"
        "is the only thing you need to do.\n"
        "\n"
        "## What it does\n"
        "\n"
        "TODO: describe the agent's job and the events it responds to.\n"
        "\n"
        "## Validate/import\n"
        "\n"
        "```sh\n"
        f"uv run scripts/sample_tool.py pack {slug}\n"
        "```\n"
        "\n"
        "## Local iteration\n"
        "\n"
        "To pack and install from a local checkout:\n"
        "\n"
        "```sh\n"
        f"uv run scripts/sample_tool.py pack {slug}\n"
        "```\n"
        "\n"
        "Upload the generated tarball through the Solution import flow.\n"
        "\n"
        f"Edit `agents/{slug}.yaml` to change identity, tools, routines, and\n"
        "setup requirements. Edit `solution.yaml` to update the catalog-facing\n"
        "name, description, and README. Edit `sample.yaml` to bump the version\n"
        "and adjust the deploy steps. Then run:\n"
        "\n"
        "```sh\n"
        "uv run scripts/sample_tool.py generate\n"
        "```\n"
        "\n"
        "to refresh `.aaignore` and `samples.json` before committing.\n"
    )


def _solution_yaml(slug: str, name: str, tagline: str, solution_id: str) -> str:
    # `name` and `description` are quoted because user-supplied taglines /
    # display names frequently contain colons (the default TODO tagline
    # certainly does) and the YAML parser would treat those as inline
    # mapping separators otherwise.
    quoted_name = _yaml_double_quote(name)
    quoted_tagline = _yaml_double_quote(tagline)
    return (
        "# Solution config — catalog-facing wrapper around this sample's\n"
        "# deployable template. The portal / CLI sample browser renders the\n"
        "# `readme:` block, the `description:` tagline, and any `assets:`\n"
        "# linked from the README.\n"
        "#\n"
        "# `template_path` and `asset_path` are paths relative to the bundle\n"
        "# root. The CLI resolves them against the on-disk layout; the\n"
        "# server keeps them as path-mode Solution designators.\n"
        "\n"
        "kind: Solution\n"
        f"lookup_key: {slug}-solution\n"
        f"solution_id: {solution_id}\n"
        f"solution_version: {DEFAULT_SOLUTION_VERSION}\n"
        f"name: {quoted_name}\n"
        f"description: {quoted_tagline}\n"
        "\n"
        "readme: |\n"
        f"  # {name}\n"
        "\n"
        f"  {tagline}\n"
        "\n"
        "  ## Architecture\n"
        "\n"
        "  ![Architecture overview](diagrams/architecture.svg)\n"
        "\n"
        "  TODO: replace this placeholder with a real walkthrough — what the\n"
        "  agent does, what triggers it, what it produces.\n"
        "\n"
        "  ## Validate/import\n"
        "\n"
        "  ```sh\n"
        f"  uv run scripts/sample_tool.py pack agents/{slug}\n"
        "  ```\n"
        "\n"
        "assets:\n"
        '  - asset_path: diagrams/architecture.svg\n'
        "\n"
        "template:\n"
        f'  template_path: agents/{slug}.yaml\n'
        "\n"
        "metadata:\n"
        "  category: general\n"
        f"  sample_slug: {slug}\n"
    )


def _yaml_double_quote(value: str) -> str:
    """Wrap a single-line string in YAML double quotes, escaping `"` and `\\`."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# Minimal placeholder SVG. Real diagrams are author-supplied; this is
# just enough to render in README + catalog and prove the wiring works.
_PLACEHOLDER_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 240" font-family="-apple-system, system-ui, sans-serif">
  <rect x="20" y="20" width="440" height="200" rx="8" ry="8" fill="#f9fafb" stroke="#9ca3af" stroke-width="1.5"/>
  <text x="240" y="110" text-anchor="middle" font-size="20" font-weight="600" fill="#111827">Architecture diagram</text>
  <text x="240" y="140" text-anchor="middle" font-size="13" fill="#4b5563">TODO: replace with the real diagram</text>
  <text x="240" y="162" text-anchor="middle" font-size="11" fill="#6b7280">(edit diagrams/architecture.svg)</text>
</svg>
"""


def _architecture_svg() -> str:
    return _PLACEHOLDER_SVG


def _env_example(slug: str) -> str:
    return (
        f"# Environment variables for the {slug} sample.\n"
        "#\n"
        "# Declare each env var in agent.yaml's `setup_requirements:` block\n"
        "# (kind: env_var) and mirror it here so local development has a\n"
        "# template to copy from. The values in this file are placeholders;\n"
        "# real values come from `archastro env` or the agent's settings UI.\n"
    )


def run_new(
    slug: str,
    name: str | None,
    tagline: str | None,
    target_dir: Path | None = None,
    with_solution: bool = False,
) -> int:
    if not SLUG_RE.match(slug):
        raise SampleError(
            f"slug {slug!r} must be lowercase kebab-case "
            f"(letters/digits with single dashes between segments). "
            f"Compare existing slugs under agents/."
        )

    # Default to the caller's cwd — the tool doesn't presume to know
    # where a contributor wants the scaffold to land. Pass
    # --target-dir <archagents>/agents to write into the catalog (which
    # additionally triggers a .aaignore + samples.json refresh below).
    if target_dir is None:
        target_dir = Path.cwd()
    target_dir = target_dir.resolve()

    if not target_dir.is_dir():
        raise SampleError(
            f"target directory {target_dir} does not exist or is not a directory. "
            f"Create it first or pass --target-dir to an existing path."
        )

    sample_dir = target_dir / slug
    if sample_dir.exists():
        raise SampleError(
            f"{sample_dir} already exists. Pick a different slug or delete "
            f"the existing directory first."
        )

    pretty_name = name or _pretty_name_from_slug(slug)
    final_tagline = tagline or f"TODO: one-line description of {pretty_name}."

    # parents=False is intentional: we create exactly <target_dir>/<slug>/,
    # one level deep. target_dir was validated above; if a user wants to
    # scaffold into a deeper path, they pass --target-dir to that path.
    sample_dir.mkdir(parents=False)
    (sample_dir / "scripts").mkdir()
    # .gitkeep so the empty scripts/ dir survives commits — upload_scripts
    # source_dir validation only requires the directory exist, so this
    # also lets the freshly scaffolded sample pass `generate` immediately.
    (sample_dir / "scripts" / ".gitkeep").write_text("")
    (sample_dir / "sample.yaml").write_text(
        _sample_yaml(slug, pretty_name, final_tagline, with_solution=with_solution)
    )
    (sample_dir / "env.example").write_text(_env_example(slug))

    if with_solution:
        # Fresh UUID per scaffold — solution_id is meant to stay stable
        # across re-publishes of the same logical solution, so we mint
        # it once at scaffold time and authors keep it for the lifetime
        # of the sample.
        solution_id = str(uuid.uuid4())
        templates_dir = sample_dir / "agents"
        templates_dir.mkdir()
        (templates_dir / f"{slug}.yaml").write_text(
            _agent_yaml(slug, pretty_name, with_solution=True)
        )
        diagrams_dir = sample_dir / "diagrams"
        diagrams_dir.mkdir()
        (diagrams_dir / "architecture.svg").write_text(_architecture_svg())
        (sample_dir / "solution.yaml").write_text(
            _solution_yaml(slug, pretty_name, final_tagline, solution_id)
        )
        (sample_dir / "README.md").write_text(
            _readme_with_solution(slug, pretty_name, final_tagline)
        )
    else:
        (sample_dir / "agent.yaml").write_text(
            _agent_yaml(slug, pretty_name, with_solution=False)
        )
        (sample_dir / "README.md").write_text(_readme(slug, pretty_name, final_tagline))

    is_catalog_target = target_dir == AGENTS_DIR.resolve()
    if is_catalog_target:
        # Only refresh .aaignore + samples.json when we're scaffolding
        # into the archagents catalog. Standalone scaffolds skip this.
        rc = run_generate(check=False)
        if rc != 0:
            return rc

    try:
        rel = sample_dir.relative_to(Path.cwd())
    except ValueError:
        rel = sample_dir
    print(f"Scaffolded {rel}/", file=sys.stderr)
    print("", file=sys.stderr)
    print("Next steps:", file=sys.stderr)
    if with_solution:
        print(
            f"  1. Edit {rel}/agents/{slug}.yaml — identity, tools, routines, setup_requirements.",
            file=sys.stderr,
        )
    else:
        print(f"  1. Edit {rel}/agent.yaml — identity, tools, routines, setup_requirements.", file=sys.stderr)
    print(f"  2. Add scripts to {rel}/scripts/ if the agent needs custom tools.", file=sys.stderr)
    if with_solution:
        print(
            f"  3. Edit {rel}/solution.yaml — catalog name, description, and README.",
            file=sys.stderr,
        )
        print(
            f"  4. Replace {rel}/diagrams/architecture.svg with the real diagram",
            file=sys.stderr,
        )
        print(
            f"     (solution.yaml refs it directly via asset_path, no wrapper needed).",
            file=sys.stderr,
        )
        print(f"  5. Run: uv run scripts/sample_tool.py pack {rel}", file=sys.stderr)
        print("     Then upload the tarball through the Solution import flow.", file=sys.stderr)
    else:
        # `pack` is always cwd-relative — suggest the same path we just
        # scaffolded. `rel` is relative when sample_dir is under cwd,
        # absolute otherwise.
        print(f"  3. Run: uv run scripts/sample_tool.py pack {rel}", file=sys.stderr)
        print(f"     Then: archastro install sample ./{slug}-v0.1.0.tar.gz", file=sys.stderr)
    return 0
