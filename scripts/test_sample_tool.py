#!/usr/bin/env python3
"""
Unit tests for scripts/sample_tool.py and the helpers under
scripts/_sample_lib/.

Run directly:

    uv run scripts/test_sample_tool.py

Tests for the pure functions (validation + rendering) build tiny
sample dirs in tmp paths. Tests for the side-effecting commands
(`new`, `pack`, `generate`) monkey-patch AGENTS_DIR / MANIFEST_PATH /
REPO_ROOT to a tmp tree so we never touch the real agents/. The
"committed artifacts match what generate would produce" integration
check is covered by CI running `generate --check`; we don't duplicate
that here.
"""
from __future__ import annotations

import io
import json
import subprocess
import os
import sys
import tarfile
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
# Make `_sample_lib` importable as a regular package — the real
# sample_tool.py entry script gets this for free because Python puts
# the script's directory on sys.path when invoked directly.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _sample_lib import generate as gen_mod  # noqa: E402
from _sample_lib import lint as lint_mod  # noqa: E402
from _sample_lib import pack as pack_mod  # noqa: E402
from _sample_lib import paths as paths_mod  # noqa: E402
from _sample_lib import scaffold as scaffold_mod  # noqa: E402
from _sample_lib import validate_scripts as vs_mod  # noqa: E402
from _sample_lib.render import render_aaignore, render_manifest  # noqa: E402
from _sample_lib.validation import SampleError, validate_sample  # noqa: E402


# --- helpers ---------------------------------------------------------------


def _make_sample_dir(**overrides) -> Path:
    """
    Build a minimal-valid sample directory in a tmp path and return it.
    Callers override `sample_yaml` (string) or specific fields.
    """
    tmp = Path(tempfile.mkdtemp())
    (tmp / "scripts").mkdir()
    (tmp / "agent.yaml").write_text("kind: AgentTemplate\nname: X\n")
    sample_body = overrides.pop(
        "sample_yaml",
        textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: Alpha
            tagline: An alpha sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
        """),
    )
    (tmp / "sample.yaml").write_text(sample_body)
    return tmp


def _parsed(sample_dir: Path):
    import yaml as pyyaml

    return pyyaml.safe_load((sample_dir / "sample.yaml").read_text())


class _TmpAgentsRoot:
    """
    Context manager that swaps the module-level AGENTS_DIR, MANIFEST_PATH,
    and REPO_ROOT to point inside a tmp tree, then restores them on exit.
    Used by `new` and `pack` tests so we don't touch the real agents/.
    """

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agents_dir = self.tmp / "agents"
        self.manifest_path = self.tmp / "samples.json"
        self._saved = {}

    def __enter__(self):
        self.agents_dir.mkdir()
        self.solutions_dir = self.tmp / "solutions"
        sample_roots = (self.agents_dir, self.solutions_dir)
        # Patch every module that imported the constants. Because the
        # constants are bound at import time, each module that did
        # `from .paths import AGENTS_DIR` got its own binding — we
        # rewrite all of them. Future drive-by additions: keep this
        # list in sync.
        self._patch(paths_mod, "AGENTS_DIR", self.agents_dir)
        self._patch(paths_mod, "SOLUTIONS_DIR", self.solutions_dir)
        self._patch(paths_mod, "SAMPLE_ROOTS", sample_roots)
        self._patch(paths_mod, "MANIFEST_PATH", self.manifest_path)
        self._patch(paths_mod, "REPO_ROOT", self.tmp)
        # generate.py imports MANIFEST_PATH, REPO_ROOT, SAMPLE_ROOTS.
        self._patch(gen_mod, "MANIFEST_PATH", self.manifest_path)
        self._patch(gen_mod, "REPO_ROOT", self.tmp)
        self._patch(gen_mod, "SAMPLE_ROOTS", sample_roots)
        self._patch(scaffold_mod, "AGENTS_DIR", self.agents_dir)
        # pack imports SAMPLE_ROOTS (slug resolution) + REPO_ROOT
        # (tarball path display).
        self._patch(pack_mod, "SAMPLE_ROOTS", sample_roots)
        self._patch(pack_mod, "REPO_ROOT", self.tmp)
        # lint imports AGENTS_DIR + REPO_ROOT for both the sample walk
        # and `display_path` error rendering.
        self._patch(lint_mod, "AGENTS_DIR", self.agents_dir)
        self._patch(lint_mod, "REPO_ROOT", self.tmp)
        return self

    def __exit__(self, *exc):
        for (mod, name), saved in self._saved.items():
            setattr(mod, name, saved)

    def _patch(self, mod, name, value):
        self._saved[(mod, name)] = getattr(mod, name)
        setattr(mod, name, value)


# --- validation -----------------------------------------------------------


class ValidateSampleTest(unittest.TestCase):
    """Every error path should produce a useful, pointed message."""

    def test_minimal_sample_passes(self):
        sample_dir = _make_sample_dir()
        parsed = validate_sample(
            "alpha", _parsed(sample_dir), sample_dir / "sample.yaml"
        )
        self.assertEqual(parsed["slug"], "alpha")
        self.assertEqual(parsed["version"], "v0.2.0")
        self.assertEqual(len(parsed["steps"]), 2)

    def test_schema_version_must_be_current(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 1
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        with self.assertRaisesRegex(SampleError, "schema_version"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_bad_version_format_is_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: 1.0.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        with self.assertRaisesRegex(SampleError, "version"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_missing_steps_block_is_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
            """)
        )
        with self.assertRaisesRegex(SampleError, "steps"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_legacy_deploy_mode_field_is_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                deploy_mode: generated
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        with self.assertRaisesRegex(SampleError, "deploy_mode"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_legacy_capabilities_field_is_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                capabilities:
                  scripts: true
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        with self.assertRaisesRegex(SampleError, "capabilities"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")


class ValidateStepsTest(unittest.TestCase):

    def _run(self, sample_yaml: str) -> None:
        sample_dir = _make_sample_dir(sample_yaml=sample_yaml)
        (sample_dir / "skills").mkdir(exist_ok=True)
        (sample_dir / "schemas").mkdir(exist_ok=True)
        (sample_dir / "rules").mkdir(exist_ok=True)
        (sample_dir / "knowledge").mkdir(exist_ok=True)
        validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_unknown_verb_is_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: unknown_verb
                source_dir: scripts
        """)
        with self.assertRaisesRegex(SampleError, "unknown_verb"):
            self._run(yaml)

    def test_missing_required_field_is_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: upload_files
                source_dir: rules
        """)
        with self.assertRaisesRegex(SampleError, "installation_kind|source_type"):
            self._run(yaml)

    def test_unknown_field_is_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: deploy_agent
                template_file: agent.yaml
                extra_junk: true
        """)
        with self.assertRaisesRegex(SampleError, "extra_junk"):
            self._run(yaml)

    def test_missing_source_dir_is_caught(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: nope
              - type: deploy_agent
                template_file: agent.yaml
        """)
        with self.assertRaisesRegex(SampleError, "nope"):
            self._run(yaml)

    def test_must_have_exactly_one_deploy_agent(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
        """)
        with self.assertRaisesRegex(SampleError, "deploy_agent"):
            self._run(yaml)

    def test_zero_deploy_agent_steps_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps: []
        """)
        with self.assertRaisesRegex(SampleError, "deploy_agent"):
            self._run(yaml)

    def test_two_deploy_agent_steps_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: deploy_agent
                template_file: agent.yaml
              - type: deploy_agent
                template_file: agent.yaml
        """)
        with self.assertRaisesRegex(SampleError, "exactly one"):
            self._run(yaml)

    def test_deploy_agent_and_deploy_solution_together_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
                  - type: deploy_solution
                    solution_file: solution.yaml
            """)
        )
        (sample_dir / "solution.yaml").write_text(
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                name: X
                template:
                  template_path: agents/x.yaml
            """)
        )
        with self.assertRaisesRegex(SampleError, "exactly one"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_deploy_solution_step_passes_when_solution_file_exists(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: upload_scripts
                    source_dir: scripts
                  - type: deploy_solution
                    solution_file: solution.yaml
            """)
        )
        (sample_dir / "solution.yaml").write_text(
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                name: X
                template:
                  template_path: agents/x.yaml
            """)
        )
        (sample_dir / "agents").mkdir()
        (sample_dir / "agents" / "x.yaml").write_text("kind: AgentTemplate\nname: X\n")
        validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_deploy_solution_absolute_template_path_is_rejected_by_solution_gate(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_solution
                    solution_file: solution.yaml
            """)
        )
        outside = sample_dir.parent / "outside-template.yaml"
        outside.write_text(textwrap.dedent("""\
            kind: AgentTemplate
            name: Outside
            setup_requirements:
              - kind: not-a-real-kind
        """))
        (sample_dir / "solution.yaml").write_text(
            textwrap.dedent(f"""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                name: X
                template:
                  template_path: {outside}
            """)
        )
        with self.assertRaisesRegex(SampleError, "template_path.*relative path"):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_deploy_solution_with_missing_solution_file_rejected(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: deploy_solution
                solution_file: missing.yaml
        """)
        with self.assertRaisesRegex(SampleError, "missing.yaml"):
            self._run(yaml)

    def test_upload_files_alongside_deploy_solution_rejected(self):
        sample_dir = _make_sample_dir(
            sample_yaml=textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: X
                tagline: X
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_solution
                    solution_file: solution.yaml
                  - type: upload_files
                    source_dir: docs
                    installation_kind: archastro/files
                    source_type: file/document
            """)
        )
        (sample_dir / "docs").mkdir()
        (sample_dir / "solution.yaml").write_text(
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                name: X
                template:
                  template_path: agents/x.yaml
            """)
        )
        with self.assertRaisesRegex(
            SampleError, "upload_files is not supported alongside deploy_solution"
        ):
            validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_upload_files_with_all_fields_passes(self):
        yaml = textwrap.dedent("""\
            schema_version: 2
            version: v0.2.0
            name: X
            tagline: X
            min_cli_version: "0.28.0"
            steps:
              - type: deploy_agent
                template_file: agent.yaml
              - type: upload_files
                source_dir: rules
                glob: "*.md"
                installation_kind: archastro/files
                source_type: file/document
                content_type: text/markdown
        """)
        self._run(yaml)


class ValidateSetupRequirementsTest(unittest.TestCase):
    """
    `setup_requirements:` lives in agent.yaml and is parsed when
    validate_steps walks the deploy_agent step. These tests build a
    minimal sample dir with a custom agent.yaml + scripts dir to
    exercise the full path including script_ref cross-referencing.
    """

    def _make_dir_with_agent_yaml(self, agent_body: str, scripts=None):
        scripts = scripts or []
        tmp = Path(tempfile.mkdtemp())
        (tmp / "scripts").mkdir()
        for name in scripts:
            (tmp / "scripts" / name).write_text("// stub\n")
        (tmp / "agent.yaml").write_text(agent_body)
        (tmp / "sample.yaml").write_text(
            textwrap.dedent("""\
                schema_version: 2
                version: v0.2.0
                name: Setup Sample
                tagline: tests setup_requirements
                min_cli_version: "0.28.0"
                steps:
                  - type: upload_scripts
                    source_dir: scripts
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        return tmp

    def _validate(self, sample_dir: Path):
        validate_sample(
            "setup-sample", _parsed(sample_dir), sample_dir / "sample.yaml"
        )

    def test_no_setup_requirements_block_is_fine(self):
        sample_dir = self._make_dir_with_agent_yaml("kind: AgentTemplate\nname: X\n")
        self._validate(sample_dir)

    def test_empty_setup_requirements_list_is_fine(self):
        sample_dir = self._make_dir_with_agent_yaml(
            "kind: AgentTemplate\nname: X\nsetup_requirements: []\n"
        )
        self._validate(sample_dir)

    def test_minimal_env_var_passes(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: GITHUB_TOKEN
                scope: org_env_var
                description: PAT with repo scope
        """))
        self._validate(sample_dir)

    def test_lowercase_env_var_key_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: github_token
                scope: org_env_var
                description: bad
        """))
        with self.assertRaisesRegex(SampleError, "SCREAMING_SNAKE_CASE"):
            self._validate(sample_dir)

    def test_unknown_scope_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: K
                scope: weird_scope
                description: bad
        """))
        with self.assertRaisesRegex(SampleError, "is not a valid scope"):
            self._validate(sample_dir)

    def test_unknown_kind_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: nonsense
                description: bad
        """))
        with self.assertRaisesRegex(SampleError, "is not a known kind"):
            self._validate(sample_dir)

    def test_install_requires_installation_kind(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: install
                description: missing the kind field
        """))
        with self.assertRaisesRegex(SampleError, "missing required fields.*installation_kind"):
            self._validate(sample_dir)

    def test_custom_with_existing_script_ref_passes(self):
        sample_dir = self._make_dir_with_agent_yaml(
            textwrap.dedent("""\
                kind: AgentTemplate
                name: X
                setup_requirements:
                  - kind: custom
                    id: verify-x
                    title: Verify X
                    description: Custom check
                    verify:
                      script_ref: verify-x
            """),
            scripts=["verify-x.aascript"],
        )
        self._validate(sample_dir)

    def test_custom_with_agentscript_extension_passes(self):
        # `.agentscript` is the newer extension — discovery accepts both,
        # so a sample shipping verify-x.agentscript should resolve a
        # `verify.script_ref: verify-x` cleanly.
        sample_dir = self._make_dir_with_agent_yaml(
            textwrap.dedent("""\
                kind: AgentTemplate
                name: X
                setup_requirements:
                  - kind: custom
                    id: verify-x
                    title: Verify X
                    description: Custom check
                    verify:
                      script_ref: verify-x
            """),
            scripts=["verify-x.agentscript"],
        )
        self._validate(sample_dir)

    def test_custom_with_dangling_script_ref_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(
            textwrap.dedent("""\
                kind: AgentTemplate
                name: X
                setup_requirements:
                  - kind: custom
                    id: verify-x
                    title: Verify X
                    description: Custom check
                    verify:
                      script_ref: ghost-script-not-shipped
            """),
            scripts=["verify-x.aascript"],
        )
        with self.assertRaisesRegex(SampleError, "doesn't match any script"):
            self._validate(sample_dir)

    def test_duplicate_identifier_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: GITHUB_TOKEN
                scope: org_env_var
                description: First
              - kind: env_var
                key: GITHUB_TOKEN
                scope: agent_env_var
                description: Duplicate
        """))
        with self.assertRaisesRegex(SampleError, "duplicate identifier 'GITHUB_TOKEN'"):
            self._validate(sample_dir)

    def test_unknown_field_rejected(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: K
                scope: org_env_var
                description: ok
                bogus_field: foo
        """))
        with self.assertRaisesRegex(SampleError, "has unknown fields.*bogus_field"):
            self._validate(sample_dir)

    def test_depends_on_must_be_list_of_strings(self):
        sample_dir = self._make_dir_with_agent_yaml(textwrap.dedent("""\
            kind: AgentTemplate
            name: X
            setup_requirements:
              - kind: env_var
                key: K
                scope: org_env_var
                description: ok
                depends_on: [123, "FOO"]
        """))
        with self.assertRaisesRegex(SampleError, "depends_on must be a list of strings"):
            self._validate(sample_dir)


# --- solution.yaml validation --------------------------------------------


class ValidateSolutionYamlTest(unittest.TestCase):
    """
    solution.yaml is optional; when present, template_path / asset_path
    values are local file paths and template_ref / asset_ref values are
    lookup-key refs. Local markdown image/link references (inline readme
    + any .md file under the sample dir) must also resolve to real files.

    Path fields are the default scaffold shape and may point at any
    local file inside the sample dir. Ref fields are still supported:
    template_ref resolves to a local wrapped-template file by lookup_key,
    and asset_ref resolves to a unique local asset file by lookup_key.
    """

    _MINIMAL_SOLUTION_HEADER = textwrap.dedent("""\
        kind: Solution
        lookup_key: x-solution
        solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
        solution_version: v0.1.0
        name: X
        description: X
    """)

    _WRAPPED_PATH = "agents/x.yaml"
    _WRAPPED_DEFAULT_BODY = "kind: AgentTemplate\nname: X\n"

    def _make_solution_sample_dir(self, slug: str = "x") -> Path:
        """
        Build a minimal sample at `<tmp>/agents/<slug>/`. The root
        agent.yaml is only for the deploy_agent step in sample.yaml; the
        solution wrapper helper uses the scaffold default agents/x.yaml
        via template_path, but individual tests can place files elsewhere.
        """
        tmp = Path(tempfile.mkdtemp())
        sample_dir = tmp / "agents" / slug
        sample_dir.mkdir(parents=True)
        (sample_dir / "scripts").mkdir()
        (sample_dir / "agent.yaml").write_text(self._WRAPPED_DEFAULT_BODY)
        (sample_dir / "sample.yaml").write_text(textwrap.dedent(f"""\
            schema_version: 2
            version: v0.1.0
            name: X
            tagline: An X sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
        """))
        return sample_dir

    def _validate(self, sample_dir: Path) -> None:
        validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def _write_solution(self, sample_dir: Path, body: str) -> None:
        (sample_dir / "solution.yaml").write_text(body)

    def _write_path_template(
        self, sample_dir: Path, body: str = _WRAPPED_DEFAULT_BODY
    ) -> Path:
        target = sample_dir / self._WRAPPED_PATH
        target.parent.mkdir(exist_ok=True)
        target.write_text(body)
        return target

    def _solution_with_template_path(self, extra: str = "") -> str:
        return (
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent(f"""\
                template:
                  template_path: {self._WRAPPED_PATH}
            """)
            + extra
        )

    def test_no_solution_yaml_is_fine(self):
        sample_dir = self._make_solution_sample_dir()
        self._validate(sample_dir)  # should not raise

    def test_missing_lookup_key_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                name: X
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "lookup_key"):
            self._validate(sample_dir)

    def test_missing_solution_id_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_version: v0.1.0
                name: X
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "solution_id"):
            self._validate(sample_dir)

    def test_non_uuid_solution_id_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: not-a-uuid
                solution_version: v0.1.0
                name: X
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "solution_id"):
            self._validate(sample_dir)

    def test_missing_solution_version_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                name: X
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "solution_version"):
            self._validate(sample_dir)

    def test_non_semver_solution_version_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: "0.1"
                name: X
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "solution_version"):
            self._validate(sample_dir)

    def test_missing_name_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            textwrap.dedent("""\
                kind: Solution
                lookup_key: x-solution
                solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
                solution_version: v0.1.0
                description: X
                template:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "name"):
            self._validate(sample_dir)

    def test_missing_template_block_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(sample_dir, self._MINIMAL_SOLUTION_HEADER)
        with self.assertRaisesRegex(SampleError, "template"):
            self._validate(sample_dir)

    def test_inline_template_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  kind: AgentTemplate
                  name: Inline
            """),
        )
        with self.assertRaisesRegex(SampleError, "template_path"):
            self._validate(sample_dir)

    def test_template_ref_resolves_wrapped_template_file_by_lookup_key(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_ref: x
            """),
        )
        self._validate(sample_dir)

    def test_template_ref_missing_lookup_key_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_ref: missing-template
            """),
        )
        with self.assertRaisesRegex(SampleError, "template_ref.*missing-template.*lookup_key"):
            self._validate(sample_dir)

    def test_template_ref_ambiguous_lookup_key_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        nested = sample_dir / "agents" / "nested"
        nested.mkdir()
        (nested / "x.yaml").write_text(self._WRAPPED_DEFAULT_BODY)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_ref: x
            """),
        )
        with self.assertRaisesRegex(SampleError, "template_ref.*ambiguous"):
            self._validate(sample_dir)

    def test_path_style_template_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_ref: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "template_ref.*lookup_key.*template_path"):
            self._validate(sample_dir)

    def test_valid_template_path_and_asset_path_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_path: diagrams/architecture.svg
                """)
            ),
        )
        self._validate(sample_dir)

    def test_nonstandard_template_path_asset_path_and_markdown_refs_pass(self):
        sample_dir = self._make_solution_sample_dir()
        template_path = sample_dir / "templates" / "wrapped" / "primary.yaml"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(self._WRAPPED_DEFAULT_BODY)

        asset_path = sample_dir / "public" / "catalog" / "images" / "hero.svg"
        asset_path.parent.mkdir(parents=True)
        asset_path.write_text("<svg/>")

        docs_path = sample_dir / "docs" / "guides" / "overview.md"
        docs_path.parent.mkdir(parents=True)
        docs_path.write_text(
            "# Overview\n\n![Hero](../../public/catalog/images/hero.svg)\n"
        )

        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_path: templates/wrapped/primary.yaml
                assets:
                  - asset_path: public/catalog/images/hero.svg
                  - asset_path: docs/guides/overview.md
                readme: |
                  # X

                  ![Hero](public/catalog/images/hero.svg)
                  [Overview](docs/guides/overview.md)
            """),
        )
        self._validate(sample_dir)

    def test_lookup_refs_resolve_nested_nonstandard_files(self):
        sample_dir = self._make_solution_sample_dir()
        template_path = sample_dir / "agents" / "library" / "deep-template.yaml"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(self._WRAPPED_DEFAULT_BODY)

        asset_path = sample_dir / "media" / "catalog" / "cards" / "hero-card.svg"
        asset_path.parent.mkdir(parents=True)
        asset_path.write_text("<svg/>")

        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_ref: deep-template
                assets:
                  - asset_ref: hero-card
            """),
        )
        self._validate(sample_dir)

    def test_asset_ref_resolves_local_file_by_lookup_key(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_ref: architecture
                """)
            ),
        )
        self._validate(sample_dir)

    def test_asset_ref_missing_lookup_key_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_ref: missing-asset
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "asset_ref.*missing-asset.*lookup_key"):
            self._validate(sample_dir)

    def test_asset_ref_ambiguous_lookup_key_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "docs").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        (sample_dir / "docs" / "architecture.md").write_text("# Architecture\n")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_ref: architecture
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "asset_ref.*ambiguous"):
            self._validate(sample_dir)

    def test_path_style_asset_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_ref: diagrams/architecture.svg
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "asset_ref.*lookup_key.*asset_path"):
            self._validate(sample_dir)

    def test_template_path_accepts_nested_nonstandard_local_file(self):
        sample_dir = self._make_solution_sample_dir()
        template_path = sample_dir / "templates" / "wrapped" / "x.yaml"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(self._WRAPPED_DEFAULT_BODY)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + "template:\n  template_path: templates/wrapped/x.yaml\n",
        )
        self._validate(sample_dir)

    def test_template_path_missing_file_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + "template:\n  template_path: agents/not-here.yaml\n",
        )
        with self.assertRaisesRegex(SampleError, "template_path.*not-here.yaml"):
            self._validate(sample_dir)

    def test_asset_path_missing_file_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - asset_path: diagrams/nope.svg
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "asset_path.*nope.svg"):
            self._validate(sample_dir)

    def test_template_path_accepts_root_local_file(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + "template:\n  template_path: agent.yaml\n",
        )
        self._validate(sample_dir)

    def test_absolute_template_path_is_rejected_via_relative_path_gate(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + "template:\n  template_path: /etc/passwd\n",
        )
        with self.assertRaisesRegex(SampleError, "template_path.*relative path"):
            self._validate(sample_dir)

    def test_escaping_template_path_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + "template:\n  template_path: ../escape.yaml\n",
        )
        with self.assertRaisesRegex(SampleError, "template_path.*escapes"):
            self._validate(sample_dir)

    def test_wrapped_template_that_isnt_a_mapping_is_rejected(self):
        # Parseability check: a list-at-root template body would slip
        # past validate today but blow up at platform-import time.
        # Catch it here, with a hint about what shape is expected.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir, "- not\n- a\n- mapping\n")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(),
        )
        with self.assertRaisesRegex(SampleError, "must be a YAML mapping"):
            self._validate(sample_dir)

    def test_non_list_assets_is_rejected(self):
        # Author wrote `assets:` as a single mapping (a common mistake)
        # instead of a list. Would silently drop and fail at import
        # time; catch up-front.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "a.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  asset_ref: diagrams/a.svg
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "`assets:` must be a list"):
            self._validate(sample_dir)

    def test_asset_entry_without_path_or_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - name: missing-ref
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "assets\\[0\\].*asset_path"):
            self._validate(sample_dir)

    def test_non_mapping_asset_entry_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                assets:
                  - diagrams/a.svg
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "assets\\[0\\]"):
            self._validate(sample_dir)

    def test_wrapped_template_with_agent_key_is_rejected(self):
        # agent_key is a deploy_agent-only field. A Solution import
        # publishes a library row and never provisions an agent, so
        # carrying agent_key in the wrapped template would silently
        # mislead later readers. Mirrors the TS samples-catalog
        # parseSolutionFile check.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(
            sample_dir, "kind: AgentTemplate\nagent_key: alpha\nname: X\n"
        )
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(),
        )
        with self.assertRaisesRegex(SampleError, "agent_key"):
            self._validate(sample_dir)

    def test_wrapped_template_without_agent_key_passes(self):
        # Sanity: the validator only objects to `agent_key:`, not to
        # any other template body content.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(
            sample_dir, "kind: AgentTemplate\nname: X\nidentity: |\n  You are X.\n"
        )
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(),
        )
        self._validate(sample_dir)

    def test_inline_readme_with_missing_image_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                readme: |
                  # X

                  ![missing](diagrams/missing.svg)
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "diagrams/missing.svg"):
            self._validate(sample_dir)

    def test_inline_readme_with_valid_image_ref_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                readme: |
                  # X

                  ![Arch](diagrams/architecture.svg)
                """)
            ),
        )
        self._validate(sample_dir)

    def test_inline_readme_external_url_is_skipped(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                readme: |
                  # X

                  ![Hosted](https://example.com/diagram.svg)
                  [Docs](https://example.com/docs)
                  [Section](#anchor)
                """)
            ),
        )
        self._validate(sample_dir)

    def test_inline_readme_link_with_title_is_validated(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                readme: |
                  # X

                  [Diagram](diagrams/missing.svg "Architecture diagram")
                """)
            ),
        )
        with self.assertRaisesRegex(SampleError, "diagrams/missing.svg"):
            self._validate(sample_dir)

    def test_on_disk_readme_with_missing_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(),
        )
        (sample_dir / "README.md").write_text(
            "# Title\n\n![diagram](diagrams/missing.svg)\n"
        )
        with self.assertRaisesRegex(SampleError, "diagrams/missing.svg"):
            self._validate(sample_dir)

    def test_markdown_ref_with_fragment_is_stripped(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "diagrams").mkdir()
        (sample_dir / "diagrams" / "architecture.svg").write_text("<svg/>")
        self._write_solution(
            sample_dir,
            self._solution_with_template_path(
                textwrap.dedent("""\
                readme: |
                  ![Arch](diagrams/architecture.svg#zoomed)
                """)
            ),
        )
        self._validate(sample_dir)

    def test_scaffolded_with_solution_passes_validation(self):
        # End-to-end: --solution scaffold should produce a sample that
        # passes the solution.yaml validator out of the box. Catches the
        # case where the scaffold drifts from the validator's contract.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            scaffold_mod.run_new(
                "hello-world",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            sample_dir = root.agents_dir / "hello-world"
            self._validate(sample_dir)

    # `templates:` is the canonical shape (a list, even with one entry).
    # Singular `template:` is kept for backwards compatibility — it's
    # normalized to a one-element list at import time on the wire side,
    # so local validation mirrors that and accepts both shapes.

    def test_templates_list_with_single_entry_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
            """),
        )
        self._validate(sample_dir)

    def test_templates_list_with_multiple_entries_passes(self):
        # A multi-template bundle: the deployable template plus
        # additional library-row templates. Each entry is independently
        # walked for setup_requirements.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        sibling = sample_dir / "agents" / "sibling.yaml"
        sibling.write_text(self._WRAPPED_DEFAULT_BODY)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: agents/sibling.yaml
            """),
        )
        self._validate(sample_dir)

    def test_templates_list_mixing_path_and_ref_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        sibling = sample_dir / "agents" / "sibling.yaml"
        sibling.write_text(self._WRAPPED_DEFAULT_BODY)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_ref: sibling
            """),
        )
        self._validate(sample_dir)

    def test_templates_with_duplicate_entry_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_ref: x
            """),
        )
        with self.assertRaisesRegex(SampleError, "templates\\[1\\].*already declared"):
            self._validate(sample_dir)

    def test_templates_entry_with_both_path_and_ref_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                    template_ref: x
            """),
        )
        with self.assertRaisesRegex(
            SampleError, "templates\\[0\\].*either `template_path:` or `template_ref:`"
        ):
            self._validate(sample_dir)

    def test_empty_templates_list_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER + "templates: []\n",
        )
        with self.assertRaisesRegex(SampleError, "`templates:` must be a non-empty list"):
            self._validate(sample_dir)

    def test_templates_as_mapping_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "`templates:` must be a non-empty list"):
            self._validate(sample_dir)

    def test_declaring_both_template_and_templates_is_rejected(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                template:
                  template_path: agents/x.yaml
                templates:
                  - template_path: agents/x.yaml
            """),
        )
        with self.assertRaisesRegex(SampleError, "either `template:` or `templates:`"):
            self._validate(sample_dir)

    def test_templates_setup_requirements_walked_per_entry(self):
        # Each template body's setup_requirements block is independently
        # validated when the sample's deploy step is deploy_solution.
        # Any custom verify.script_ref must resolve to a script in an
        # upload_scripts source_dir — a dangling script_ref in the
        # *second* template should still be caught.
        sample_dir = self._make_solution_sample_dir()
        # Swap deploy_agent for deploy_solution so validate_steps walks
        # the bundle's templates list rather than the sample-root
        # agent.yaml.
        (sample_dir / "sample.yaml").write_text(textwrap.dedent("""\
            schema_version: 2
            version: v0.1.0
            name: X
            tagline: An X sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_solution
                solution_file: solution.yaml
        """))
        self._write_path_template(sample_dir)
        # Drop a real script so the cross-reference check actually runs
        # (it's skipped when no upload_scripts source_dir yields any
        # lookup_keys — see validation.py).
        (sample_dir / "scripts" / "real-script.aascript").write_text("// stub\n")
        sibling = sample_dir / "agents" / "sibling.yaml"
        sibling.write_text(textwrap.dedent("""\
            kind: AgentTemplate
            name: Sibling
            setup_requirements:
              - kind: custom
                id: sibling-check
                title: Sibling check
                description: verifies the sibling template
                verify:
                  script_ref: not-a-real-script
        """))
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: agents/sibling.yaml
            """),
        )
        with self.assertRaisesRegex(
            SampleError, "script_ref 'not-a-real-script'"
        ):
            self._validate(sample_dir)

    def test_tool_template_without_display_name_is_rejected(self):
        # The backend allows AgentToolTemplate.display_name to be empty
        # and falls back to humanizing `name`, but the humanizer loses
        # acronym casing (`query_osv` → `Query Osv`). validate_sample
        # forces samples to declare `display_name:` so the catalog
        # renders properly.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "tools").mkdir()
        (sample_dir / "tools" / "query-osv.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            tool_type: custom
            name: query_osv
            description: stub
            handler_type: script
            config_ref: query-osv
        """))
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/query-osv.yaml
            """),
        )
        with self.assertRaisesRegex(
            SampleError,
            r"tools/query-osv.yaml.*AgentToolTemplate.*display_name",
        ):
            self._validate(sample_dir)

    def test_routine_template_without_display_name_is_rejected(self):
        # Same rule applies to AgentRoutineTemplate. `name` is the
        # kebab-case routine handle; without `display_name` the carousel
        # label degrades to `Daily Dependency Scan`-style humanization.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "routines").mkdir()
        (sample_dir / "routines" / "daily-scan.yaml").write_text(textwrap.dedent("""\
            kind: AgentRoutineTemplate
            name: daily-scan
            description: stub
        """))
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: routines/daily-scan.yaml
            """),
        )
        with self.assertRaisesRegex(
            SampleError,
            r"routines/daily-scan.yaml.*AgentRoutineTemplate.*display_name",
        ):
            self._validate(sample_dir)

    def test_tool_template_with_display_name_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "tools").mkdir()
        (sample_dir / "tools" / "query-osv.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            tool_type: custom
            name: query_osv
            display_name: "Query OSV.dev"
            description: stub
            handler_type: script
            config_ref: query-osv
        """))
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/query-osv.yaml
            """),
        )
        self._validate(sample_dir)

    def test_agent_template_does_not_require_display_name(self):
        # AgentTemplate.name *is* the catalog-facing display name (per
        # agent_template.ex), so the display_name requirement only
        # applies to AgentToolTemplate / AgentRoutineTemplate.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
            """),
        )
        self._validate(sample_dir)

    def test_template_readme_path_missing_file_is_rejected(self):
        # A `readme_path:` typo would silently fall through to a
        # placeholder in the Library inspector. The strict validator
        # catches it at pack time instead — same gate as template_path.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                    readme_path: docs/typo.md
            """),
        )
        with self.assertRaisesRegex(
            SampleError,
            r"templates\[0\]\.readme_path 'docs/typo.md'.*does not point at a real file",
        ):
            self._validate(sample_dir)

    def test_template_readme_path_present_passes(self):
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "agents" / "x.md").write_text("# X\n")
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                    readme_path: agents/x.md
            """),
        )
        self._validate(sample_dir)

    def test_template_readme_path_escaping_sample_dir_is_rejected(self):
        # `_require_local_file` also rejects `..` traversal, matching
        # the backend's SolutionRelativePath rules.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                    readme_path: ../escape.md
            """),
        )
        with self.assertRaisesRegex(
            SampleError, "readme_path '../escape.md' escapes the sample directory"
        ):
            self._validate(sample_dir)

    def test_tool_template_via_template_ref_also_requires_display_name(self):
        # template_ref takes a different resolution path than
        # template_path, but the wrapped-template body check fires
        # either way. The lookup_key resolver only walks under agents/
        # right now, so the fixture parks the tool template there.
        sample_dir = self._make_solution_sample_dir()
        self._write_path_template(sample_dir)
        (sample_dir / "agents" / "query-osv.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            lookup_key: query-osv
            tool_type: custom
            name: query_osv
            description: stub
            handler_type: script
            config_ref: query-osv
        """))
        self._write_solution(
            sample_dir,
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_ref: query-osv
            """),
        )
        with self.assertRaisesRegex(
            SampleError,
            r"'query-osv'.*AgentToolTemplate.*display_name",
        ):
            self._validate(sample_dir)


# --- bundle lookup_key uniqueness ----------------------------------------


class ValidateBundleLookupKeyUniquenessTest(unittest.TestCase):
    """
    The platform's per-(app, org, sandbox) config namespace is flat
    across kinds — a Script and an AgentToolTemplate that both want
    lookup_key 'foo' collide at import time with a 422. validate_steps
    runs a final cross-artifact dedupe pass so a sample that passes
    `validate` also passes `/api/solutions/import`.
    """

    _MINIMAL_SOLUTION_HEADER = textwrap.dedent("""\
        kind: Solution
        lookup_key: x-solution
        solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
        solution_version: v0.1.0
        name: X
        description: X
    """)

    def _make_solution_sample_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        sample_dir = tmp / "agents" / "x"
        sample_dir.mkdir(parents=True)
        (sample_dir / "scripts").mkdir()
        (sample_dir / "agents").mkdir()
        (sample_dir / "agents" / "x.yaml").write_text(
            "kind: AgentTemplate\nname: X\n"
        )
        (sample_dir / "sample.yaml").write_text(textwrap.dedent("""\
            schema_version: 2
            version: v0.1.0
            name: X
            tagline: A sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_solution
                solution_file: solution.yaml
        """))
        return sample_dir

    def _validate(self, sample_dir: Path) -> None:
        validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_script_and_bundled_tool_template_with_same_lookup_key_rejected(self):
        # The exact production case: scripts/query-osv.aascript derives
        # lookup_key 'query-osv'; tools/query-osv.yaml's body declares
        # `lookup_key: query-osv`. Same final sol-<uuid>-query-osv slot.
        sample_dir = self._make_solution_sample_dir()
        (sample_dir / "scripts" / "query-osv.aascript").write_text("// stub\n")
        (sample_dir / "tools").mkdir()
        (sample_dir / "tools" / "query-osv.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            lookup_key: query-osv
            tool_type: custom
            name: query_osv
            description: stub
            handler_type: script
            config_ref: query-osv
        """))
        (sample_dir / "solution.yaml").write_text(
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/query-osv.yaml
            """)
        )
        with self.assertRaisesRegex(
            SampleError,
            r"lookup_key 'query-osv' is used by two bundle artifacts:.*"
            r"Script scripts/query-osv\.aascript.*"
            r"AgentToolTemplate tools/query-osv\.yaml",
        ):
            self._validate(sample_dir)

    def test_two_bundled_templates_with_same_lookup_key_rejected(self):
        # Two AgentToolTemplate files in the same bundle that both
        # declare `lookup_key: foo` would collide at import — the
        # second insert hits the unique constraint.
        sample_dir = self._make_solution_sample_dir()
        (sample_dir / "tools").mkdir()
        (sample_dir / "tools" / "a.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            lookup_key: shared
            tool_type: custom
            name: a
            description: stub
            handler_type: script
            config_ref: a
        """))
        (sample_dir / "tools" / "b.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            lookup_key: shared
            tool_type: custom
            name: b
            description: stub
            handler_type: script
            config_ref: b
        """))
        (sample_dir / "solution.yaml").write_text(
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/a.yaml
                  - template_path: tools/b.yaml
            """)
        )
        with self.assertRaisesRegex(
            SampleError, r"lookup_key 'shared'.*tools/a\.yaml.*tools/b\.yaml"
        ):
            self._validate(sample_dir)

    def test_script_collision_under_deploy_agent_flow_is_rejected(self):
        # Same script-vs-template collision but exercised via the
        # deploy_agent path (no solution.yaml). Here the AgentTemplate
        # itself declares the colliding lookup_key.
        tmp = Path(tempfile.mkdtemp())
        (tmp / "scripts").mkdir()
        (tmp / "scripts" / "shared.aascript").write_text("// stub\n")
        (tmp / "agent.yaml").write_text(textwrap.dedent("""\
            kind: AgentTemplate
            lookup_key: shared
            name: X
        """))
        (tmp / "sample.yaml").write_text(textwrap.dedent("""\
            schema_version: 2
            version: v0.1.0
            name: X
            tagline: A sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
        """))
        with self.assertRaisesRegex(
            SampleError,
            r"lookup_key 'shared'.*Script scripts/shared\.aascript.*"
            r"AgentTemplate agent\.yaml",
        ):
            validate_sample("x", _parsed(tmp), tmp / "sample.yaml")

    def test_prefixed_atomic_template_lookup_keys_pass(self):
        # Happy path: prefixing the AgentToolTemplate's lookup_key
        # breaks the collision and the bundle validates clean. Mirrors
        # the production fix where tools/query-osv.yaml declares
        # `lookup_key: st-tool-query-osv` alongside
        # scripts/query-osv.aascript (`query-osv`).
        sample_dir = self._make_solution_sample_dir()
        (sample_dir / "scripts" / "query-osv.aascript").write_text("// stub\n")
        (sample_dir / "tools").mkdir()
        (sample_dir / "tools" / "query-osv.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            lookup_key: st-tool-query-osv
            tool_type: custom
            name: query_osv
            display_name: Query OSV
            description: stub
            handler_type: script
            config_ref: query-osv
        """))
        (sample_dir / "solution.yaml").write_text(
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/query-osv.yaml
            """)
        )
        self._validate(sample_dir)

    def test_template_without_explicit_lookup_key_skipped(self):
        # The check is explicit-only — a template body that doesn't
        # declare `lookup_key:` is not registered. (The platform
        # auto-derives a key, but that derivation rule isn't reliably
        # observable from authoring side, so we don't speculate.)
        sample_dir = self._make_solution_sample_dir()
        (sample_dir / "scripts" / "shared.aascript").write_text("// stub\n")
        (sample_dir / "tools").mkdir()
        # No `lookup_key:` declared — collision-by-derivation possible
        # but not registered, so validate passes.
        (sample_dir / "tools" / "shared.yaml").write_text(textwrap.dedent("""\
            kind: AgentToolTemplate
            tool_type: custom
            name: shared
            display_name: Shared
            description: stub
            handler_type: script
            config_ref: shared
        """))
        (sample_dir / "solution.yaml").write_text(
            self._MINIMAL_SOLUTION_HEADER
            + textwrap.dedent("""\
                templates:
                  - template_path: agents/x.yaml
                  - template_path: tools/shared.yaml
            """)
        )
        self._validate(sample_dir)


# --- lint -----------------------------------------------------------------


class LintTest(unittest.TestCase):
    """
    `sample_tool lint` surfaces best-practice warnings without failing
    by default. --strict flips the exit code so CI can opt in.
    """

    _MINIMAL_SOLUTION_HEADER = textwrap.dedent("""\
        kind: Solution
        lookup_key: x-solution
        solution_id: 7a1c4f10-1e2b-4d6f-9a8d-2b71f2c6a103
        solution_version: v0.1.0
        name: X
    """)

    def _make_agents_root(self) -> _TmpAgentsRoot:
        return _TmpAgentsRoot()

    def _write_minimal_sample(
        self,
        root: _TmpAgentsRoot,
        slug: str,
        *,
        with_solution: bool = False,
        with_readme: bool = False,
        solution_extra: str = "",
    ) -> Path:
        sample_dir = root.agents_dir / slug
        sample_dir.mkdir()
        (sample_dir / "scripts").mkdir()
        (sample_dir / "agent.yaml").write_text(
            "kind: AgentTemplate\nname: X\n"
        )
        (sample_dir / "sample.yaml").write_text(textwrap.dedent("""\
            schema_version: 2
            version: v0.1.0
            name: X
            tagline: A sample.
            min_cli_version: "0.28.0"
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
        """))
        if with_readme:
            (sample_dir / "README.md").write_text("# X\n")
        if with_solution:
            (sample_dir / "agents").mkdir(exist_ok=True)
            (sample_dir / "agents" / "x.yaml").write_text(
                "kind: AgentTemplate\nname: X\n"
            )
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    tag_keys: [demo]
                    readme: "Body."
                    templates:
                      - template_path: agents/x.yaml
                """)
                + solution_extra
            )
        return sample_dir

    def _run(self, slug: str | None, strict: bool) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stderr(buf):
            code = lint_mod.run_lint(slug, strict=strict)
        return code, buf.getvalue()

    def test_clean_sample_with_solution_passes(self):
        with self._make_agents_root() as root:
            self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            code, output = self._run(None, strict=True)
        self.assertEqual(code, 0, output)
        self.assertIn("clean", output)

    def test_missing_readme_warns(self):
        with self._make_agents_root() as root:
            self._write_minimal_sample(root, "alpha", with_readme=False)
            code_default, output = self._run(None, strict=False)
            code_strict, _ = self._run(None, strict=True)
        self.assertEqual(code_default, 0)
        self.assertEqual(code_strict, 1)
        self.assertIn("missing README.md", output)

    def test_missing_category_keys_warns(self):
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    tag_keys: [demo]
                    readme: "Body."
                    templates:
                      - template_path: agents/x.yaml
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 1)
        self.assertIn("category_keys", output)
        self.assertNotIn("tag_keys", output)

    def test_missing_tag_keys_warns(self):
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    readme: "Body."
                    templates:
                      - template_path: agents/x.yaml
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 1)
        self.assertIn("tag_keys", output)

    def test_missing_solution_readme_warns(self):
        # No top-level readme: AND no per-template readme_path: → warn
        # the inspector will fall back to a placeholder.
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    tag_keys: [demo]
                    templates:
                      - template_path: agents/x.yaml
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 1)
        self.assertIn("no `readme:`", output)

    def test_per_template_readme_path_satisfies_readme_check(self):
        # The shared/top-level readme check is satisfied if EVERY
        # template entry carries its own readme_path:, so authors who
        # split docs per template don't get nagged.
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "TEMPLATE_README.md").write_text("body")
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    tag_keys: [demo]
                    templates:
                      - template_path: agents/x.yaml
                        readme_path: TEMPLATE_README.md
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 0, output)
        self.assertNotIn("readme", output)

    def test_partial_readme_coverage_warns_per_entry(self):
        # One template has readme_path, the other doesn't, and there's
        # no shared top-level readme: the second entry would render as
        # a placeholder.
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "agents" / "y.yaml").write_text(
                "kind: AgentTemplate\nname: Y\n"
            )
            (sample_dir / "TEMPLATE_README.md").write_text("body")
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    tag_keys: [demo]
                    templates:
                      - template_path: agents/x.yaml
                        readme_path: TEMPLATE_README.md
                      - template_path: agents/y.yaml
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 1)
        self.assertIn("templates[1] has no `readme_path:`", output)
        self.assertNotIn("templates[0]", output)

    def test_shared_readme_covers_per_template_gaps(self):
        # When the Solution declares a top-level readme:, every
        # template falls back to it and the per-template gap is not
        # worth nagging about.
        with self._make_agents_root() as root:
            sample_dir = self._write_minimal_sample(
                root, "alpha", with_solution=True, with_readme=True
            )
            (sample_dir / "agents" / "y.yaml").write_text(
                "kind: AgentTemplate\nname: Y\n"
            )
            (sample_dir / "solution.yaml").write_text(
                self._MINIMAL_SOLUTION_HEADER
                + textwrap.dedent("""\
                    description: A solution.
                    category_keys: [operations]
                    tag_keys: [demo]
                    readme: "Shared body."
                    templates:
                      - template_path: agents/x.yaml
                      - template_path: agents/y.yaml
                """)
            )
            code_strict, output = self._run(None, strict=True)
        self.assertEqual(code_strict, 0, output)
        self.assertNotIn("readme", output)

    def test_single_slug_target(self):
        with self._make_agents_root() as root:
            self._write_minimal_sample(root, "alpha", with_readme=False)
            self._write_minimal_sample(root, "beta", with_readme=True)
            code, output = self._run("alpha", strict=True)
        self.assertEqual(code, 1)
        self.assertIn("alpha", output)
        self.assertNotIn("WARN beta", output)

    def test_unknown_slug_errors(self):
        with self._make_agents_root() as root:
            self._write_minimal_sample(root, "alpha", with_readme=True)
            code, output = self._run("nope", strict=False)
        self.assertEqual(code, 1)
        self.assertIn("not a sample", output)


# --- rendering ------------------------------------------------------------


class RenderAaignoreTest(unittest.TestCase):

    def test_lists_every_top_level_entry_with_dir_slash(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "agent.yaml").write_text("x")
        (tmp / "sample.yaml").write_text("schema_version: 2")
        (tmp / "scripts").mkdir()
        (tmp / "schemas").mkdir()

        body = render_aaignore(tmp)
        self.assertIn("Auto-generated", body)
        self.assertIn("install agentsample", body)
        self.assertIn("\nagent.yaml\n", body)
        self.assertIn("\nsample.yaml\n", body)
        self.assertIn("\nscripts/\n", body)
        self.assertIn("\nschemas/\n", body)

    def test_aaignore_skips_itself(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".aaignore").write_text("stale\n")
        (tmp / "agent.yaml").write_text("x")
        body = render_aaignore(tmp)
        self.assertNotIn(".aaignore", body)

    def test_header_points_at_sample_tool(self):
        # Header reference is part of the API — version-bump script
        # tells authors to run the same command, so a typo here would
        # spread.
        tmp = Path(tempfile.mkdtemp())
        (tmp / "agent.yaml").write_text("x")
        body = render_aaignore(tmp)
        self.assertIn("uv run scripts/sample_tool.py", body)


class RenderManifestTest(unittest.TestCase):

    def _sample(self, slug="alpha", **overrides) -> dict:
        sample = {
            "slug": slug,
            "version": "v0.2.0",
            "name": f"{slug.title()} Sample",
            "tagline": "An example.",
            "min_cli_version": "0.28.0",
            "steps": [{"type": "deploy_agent", "template_file": "agent.yaml"}],
        }
        sample.update(overrides)
        return sample

    def test_manifest_is_deterministic_json(self):
        samples = [self._sample("alpha"), self._sample("beta")]
        a = render_manifest(samples)
        b = render_manifest(samples)
        self.assertEqual(a, b)

    def test_manifest_includes_required_fields(self):
        body = render_manifest([self._sample("alpha")])
        parsed = json.loads(body)
        self.assertEqual(parsed["$schema_version"], paths_mod.MANIFEST_SCHEMA_VERSION)
        entry = parsed["samples"][0]
        for key in ("slug", "name", "tagline", "current_version", "min_cli_version"):
            self.assertIn(key, entry)
        self.assertNotIn("steps", entry)

    def test_manifest_preserves_unicode(self):
        body = render_manifest([self._sample("alpha", tagline="A sample — with a dash.")])
        self.assertIn("—", body)
        self.assertNotIn("\\u", body)


# --- `new` ---------------------------------------------------------------


class NewSampleTest(unittest.TestCase):
    """
    `new` should land a directory that passes `generate` immediately.
    The check below uses the swapped-out AGENTS_DIR so we don't pollute
    the real tree.
    """

    def _redirect_stderr(self):
        # Swallow the "scaffolded / next steps" output so test runs stay clean.
        return _RedirectStderr()

    def test_new_creates_minimum_layout(self):
        # Pass target_dir explicitly: the default is now cwd, but these
        # tests are about the catalog-write path (AGENTS_DIR target).
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world", name=None, tagline=None, target_dir=root.agents_dir
            )

            sample_dir = root.agents_dir / "hello-world"
            self.assertTrue((sample_dir / "sample.yaml").is_file())
            self.assertTrue((sample_dir / "agent.yaml").is_file())
            self.assertTrue((sample_dir / "scripts").is_dir())
            self.assertTrue((sample_dir / "scripts" / ".gitkeep").is_file())
            self.assertTrue((sample_dir / "env.example").is_file())
            self.assertTrue((sample_dir / "README.md").is_file())

    def test_new_passes_validation(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world", name=None, tagline=None, target_dir=root.agents_dir
            )
            # `generate` validates every sample under AGENTS_DIR; if the
            # scaffold drifts from the validator, this fails loudly.
            rc = gen_mod.run_generate(check=False)
            self.assertEqual(rc, 0)
            self.assertTrue((root.agents_dir / "hello-world" / ".aaignore").is_file())
            manifest = json.loads(root.manifest_path.read_text())
            slugs = [s["slug"] for s in manifest["samples"]]
            self.assertIn("hello-world", slugs)

    def test_new_refuses_existing_dir(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            (root.agents_dir / "hello-world").mkdir()
            with self.assertRaisesRegex(SampleError, "already exists"):
                scaffold_mod.run_new(
                    "hello-world", name=None, tagline=None, target_dir=root.agents_dir
                )

    def test_new_rejects_bad_slug(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            for bad in ("Hello_World", "trailing-", "UPPER"):
                with self.assertRaisesRegex(SampleError, "kebab-case"):
                    scaffold_mod.run_new(
                        bad, name=None, tagline=None, target_dir=root.agents_dir
                    )

    def test_new_uses_supplied_name_and_tagline(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world",
                name="Custom Name",
                tagline="Custom tagline goes here.",
                target_dir=root.agents_dir,
            )
            sample_yaml = (root.agents_dir / "hello-world" / "sample.yaml").read_text()
            self.assertIn('name: "Custom Name"', sample_yaml)
            self.assertIn('tagline: "Custom tagline goes here."', sample_yaml)

    def test_new_target_dir_scaffolds_outside_catalog(self):
        # Standalone scaffold: writes to the requested target dir and
        # does NOT touch the catalog (no .aaignore, no samples.json).
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            external = root.tmp / "external-checkout"
            external.mkdir()
            scaffold_mod.run_new("hello-world", name=None, tagline=None, target_dir=external)

            scaffolded = external / "hello-world"
            self.assertTrue((scaffolded / "sample.yaml").is_file())
            self.assertTrue((scaffolded / "agent.yaml").is_file())
            # No catalog-side artifacts because target_dir != AGENTS_DIR.
            self.assertFalse((scaffolded / ".aaignore").exists())
            self.assertFalse(root.manifest_path.exists())

    def test_new_target_dir_pointing_at_agents_runs_generate(self):
        # When --target-dir resolves to AGENTS_DIR exactly, we still get
        # the catalog refresh (it's the same code path as the default).
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world", name=None, tagline=None, target_dir=root.agents_dir
            )
            self.assertTrue((root.agents_dir / "hello-world" / ".aaignore").is_file())
            self.assertTrue(root.manifest_path.is_file())

    def test_new_target_dir_must_exist(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            with self.assertRaisesRegex(SampleError, "does not exist"):
                scaffold_mod.run_new(
                    "hello-world",
                    name=None,
                    tagline=None,
                    target_dir=root.tmp / "does-not-exist",
                )

    def test_new_default_omits_solution_files(self):
        # Without --solution, the scaffold stays minimal — no solution.yaml,
        # no diagrams/.
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world", name=None, tagline=None, target_dir=root.agents_dir
            )
            sample_dir = root.agents_dir / "hello-world"
            self.assertFalse((sample_dir / "solution.yaml").exists())
            self.assertFalse((sample_dir / "diagrams").exists())

    def test_new_with_solution_scaffolds_solution_and_diagrams(self):
        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            sample_dir = root.agents_dir / "hello-world"
            self.assertTrue((sample_dir / "solution.yaml").is_file())
            self.assertTrue((sample_dir / "agents" / "hello-world.yaml").is_file())
            self.assertTrue((sample_dir / "diagrams").is_dir())
            self.assertTrue((sample_dir / "diagrams" / "architecture.svg").is_file())
            # solution.yaml refs the SVG directly via asset_path — no
            # wrapper yaml file in the diagrams/ directory.
            self.assertFalse(
                (sample_dir / "diagrams" / "architecture.image.yaml").exists()
            )
            # README should reference the placeholder diagram so the
            # scaffold renders on GitHub out of the box.
            readme = (sample_dir / "README.md").read_text()
            self.assertIn("diagrams/architecture.svg", readme)
            # sample.yaml should drive the solution import flow — no
            # deploy_agent step in solution-mode scaffolds.
            sample_yaml_text = (sample_dir / "sample.yaml").read_text()
            self.assertIn("type: deploy_solution", sample_yaml_text)
            self.assertIn("solution_file: solution.yaml", sample_yaml_text)
            self.assertNotIn("type: deploy_agent", sample_yaml_text)

    def test_new_with_solution_generates_valid_solution_yaml(self):
        # The scaffolded solution.yaml should have a UUID solution_id, a
        # semver solution_version matching the sample.yaml default, and
        # template_path / asset_path entries pointing at the wrapped
        # template + placeholder SVG.
        import yaml as pyyaml

        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "hello-world",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            sample_dir = root.agents_dir / "hello-world"
            solution = pyyaml.safe_load((sample_dir / "solution.yaml").read_text())

            self.assertEqual(solution["kind"], "Solution")
            self.assertEqual(solution["lookup_key"], "hello-world-solution")
            self.assertRegex(
                solution["solution_id"],
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            )
            self.assertRegex(solution["solution_version"], r"^v\d+\.\d+\.\d+$")
            # template_path / asset_path are resolved relative to the
            # bundle root and match the platform path-mode Solution
            # designators. `templates:` is the canonical shape — a list,
            # even when only one template ships in the bundle.
            self.assertNotIn("template", solution)
            self.assertEqual(
                solution["templates"],
                [{"template_path": "agents/hello-world.yaml"}],
            )
            self.assertEqual(
                solution["assets"],
                [{"asset_path": "diagrams/architecture.svg"}],
            )

    def test_new_with_solution_mints_a_fresh_uuid_per_scaffold(self):
        import yaml as pyyaml

        with _TmpAgentsRoot() as root, self._redirect_stderr():
            scaffold_mod.run_new(
                "alpha",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            scaffold_mod.run_new(
                "beta",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            a = pyyaml.safe_load(
                (root.agents_dir / "alpha" / "solution.yaml").read_text()
            )
            b = pyyaml.safe_load(
                (root.agents_dir / "beta" / "solution.yaml").read_text()
            )
            self.assertNotEqual(a["solution_id"], b["solution_id"])


# --- `pack` --------------------------------------------------------------


class PackSampleTest(unittest.TestCase):

    def _scaffold(self, root: _TmpAgentsRoot, slug: str = "hello-world"):
        # Pack tests target the catalog path, so write into root.agents_dir
        # explicitly now that run_new's default is cwd.
        with _RedirectStderr():
            scaffold_mod.run_new(slug, name=None, tagline=None, target_dir=root.agents_dir)

    def test_pack_writes_tarball_with_expected_layout(self):
        with _TmpAgentsRoot() as root, _RedirectStderr():
            self._scaffold(root)
            output_dir = root.tmp / "dist"
            # pack is cwd-relative; pass the full path to the scaffolded sample.
            pack_mod.run_pack(str(root.agents_dir / "hello-world"), output_dir)

            tarball = output_dir / "hello-world-v0.1.0.tar.gz"
            self.assertTrue(tarball.is_file())

            with tarfile.open(tarball, "r:gz") as tar:
                names = tar.getnames()
            # Every entry should be rooted at the slug, matching what
            # the CI shell version produced. The consumer doesn't care
            # who built the archive.
            self.assertTrue(all(n.startswith("hello-world/") or n == "hello-world" for n in names))
            self.assertIn("hello-world/sample.yaml", names)
            self.assertIn("hello-world/agent.yaml", names)
            self.assertIn("hello-world/scripts", names)
            self.assertIn("hello-world/README.md", names)

    def test_pack_validates_before_writing(self):
        # An invalid sample.yaml should fail pack and not leave a
        # half-written tarball behind.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            self._scaffold(root)
            broken = root.agents_dir / "hello-world" / "sample.yaml"
            broken.write_text("schema_version: 99\nversion: bad\n")

            output_dir = root.tmp / "dist"
            with self.assertRaises(SampleError):
                pack_mod.run_pack(str(root.agents_dir / "hello-world"), output_dir)
            # No partial tarball in dist/ — validation runs before
            # tarfile.open touches the disk.
            self.assertFalse(output_dir.exists() and any(output_dir.iterdir()))

    def test_pack_refuses_missing_path(self):
        with _TmpAgentsRoot() as root, _RedirectStderr():
            with self.assertRaisesRegex(SampleError, "does not exist"):
                pack_mod.run_pack(str(root.tmp / "never-scaffolded"), root.tmp / "dist")

    def test_pack_includes_solution_yaml_and_diagrams_when_present(self):
        # When `new --solution` was used, the resulting tarball must
        # carry solution.yaml + every file under diagrams/ — those are
        # the catalog-facing artifacts the installer needs.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            scaffold_mod.run_new(
                "hello-world",
                name=None,
                tagline=None,
                target_dir=root.agents_dir,
                with_solution=True,
            )
            output_dir = root.tmp / "dist"
            pack_mod.run_pack(str(root.agents_dir / "hello-world"), output_dir)

            tarball = output_dir / "hello-world-v0.1.0.tar.gz"
            with tarfile.open(tarball, "r:gz") as tar:
                names = set(tar.getnames())

            self.assertIn("hello-world/solution.yaml", names)
            self.assertIn("hello-world/diagrams/architecture.svg", names)

    def test_pack_accepts_path_to_sample_directory(self):
        # `pack ./some-sample` (or any path with a separator / leading
        # dot) treats the arg as a directory and derives the tarball
        # name from its basename. Makes the smoke-test-in-tmp flow work.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            external = root.tmp / "external-checkout"
            external.mkdir()
            scaffold_mod.run_new(
                "external-sample", name=None, tagline=None, target_dir=external
            )

            sample_path = external / "external-sample"
            output_dir = root.tmp / "dist"
            pack_mod.run_pack(str(sample_path), output_dir)

            tarball = output_dir / "external-sample-v0.1.0.tar.gz"
            self.assertTrue(tarball.is_file())
            with tarfile.open(tarball, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("external-sample/sample.yaml", names)
            self.assertIn("external-sample/agent.yaml", names)

    def test_pack_skips_apple_double_companion_files(self):
        # macOS spawns `._<name>` AppleDouble companions when files
        # cross HFS+ ↔ non-HFS+ boundaries (SMB shares, ExFAT USB
        # drives, some Docker bind mounts). The extractor on the
        # platform side doesn't strip them; left in the tarball, they
        # silently double-register every config and the resulting
        # duplicate-row error is cryptic. Pack must filter them.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            self._scaffold(root)
            sample_dir = root.agents_dir / "hello-world"
            # Sprinkle AppleDouble files at the sample root, under
            # scripts/, and an entire `._foo` directory whose children
            # should also be skipped.
            (sample_dir / "._sample.yaml").write_text("stray xattr blob\n")
            (sample_dir / "scripts" / "._agent.aascript").write_text("blob\n")
            apple_double_dir = sample_dir / "._foo"
            apple_double_dir.mkdir()
            (apple_double_dir / "nested.txt").write_text("blob\n")

            output_dir = root.tmp / "dist"
            pack_mod.run_pack(str(sample_dir), output_dir)

            tarball = output_dir / "hello-world-v0.1.0.tar.gz"
            with tarfile.open(tarball, "r:gz") as tar:
                names = tar.getnames()

            # None of the AppleDouble entries (file or nested) made it
            # into the archive…
            self.assertFalse(
                any(n.startswith("hello-world/._") for n in names),
                msg=f"AppleDouble entry leaked into tarball: {names}",
            )
            self.assertFalse(
                any("/._" in n for n in names),
                msg=f"AppleDouble entry leaked into tarball: {names}",
            )
            # …but the legitimate sibling entries are still there.
            self.assertIn("hello-world/sample.yaml", names)
            self.assertIn("hello-world/scripts", names)

    def test_pack_sets_copyfile_disable_env_on_macos(self):
        # Defensive: COPYFILE_DISABLE=1 is the macOS-wide off-switch
        # for AppleDouble emission on `cp`/`mv`/`bsdtar`. We set it
        # only on darwin so child processes inheriting our env also
        # get clean output.
        if sys.platform != "darwin":
            self.skipTest("COPYFILE_DISABLE only meaningful on darwin")
        with _TmpAgentsRoot() as root, _RedirectStderr():
            self._scaffold(root)
            os.environ.pop("COPYFILE_DISABLE", None)
            try:
                pack_mod.run_pack(
                    str(root.agents_dir / "hello-world"), root.tmp / "dist"
                )
                self.assertEqual(os.environ.get("COPYFILE_DISABLE"), "1")
            finally:
                os.environ.pop("COPYFILE_DISABLE", None)

    def test_pack_accepts_catalog_bare_slug(self):
        # The public usage examples advertise `pack code-review-agent`.
        # Preserve path-first behavior, but let a bare slug resolve
        # through agents/<slug> when present.
        with _TmpAgentsRoot() as root, _RedirectStderr():
            self._scaffold(root)
            output_dir = root.tmp / "dist"
            pack_mod.run_pack("hello-world", output_dir)

            tarball = output_dir / "hello-world-v0.1.0.tar.gz"
            self.assertTrue(tarball.is_file())
            with tarfile.open(tarball, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("hello-world/sample.yaml", names)
            self.assertIn("hello-world/agent.yaml", names)


# --- `validate` (script semantic validation via the CLI) ----------------


def _write_validate_sample(
    repo: Path,
    slug: str,
    sample_yaml: str,
    files: dict[str, str] | None = None,
) -> None:
    sample_dir = repo / "agents" / slug
    sample_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "sample.yaml").write_text(textwrap.dedent(sample_yaml))
    for rel_path, content in (files or {}).items():
        path = sample_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class DiscoverSampleScriptFilesTest(unittest.TestCase):
    def test_discovers_scripts_from_upload_scripts_steps_recursively(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {
                "scripts/one.aascript": "1 + 1",
                "scripts/nested/three.aascript": "3 + 3",
                "scripts/two.aascript": "2 + 2",
                "scripts/readme.md": "ignore me",
                "agent.yaml": "kind: AgentTemplate\n",
            },
        )
        _write_validate_sample(
            repo,
            "beta",
            """\
            schema_version: 2
            steps:
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {"agent.yaml": "kind: AgentTemplate\n"},
        )

        discovered = vs_mod.discover_sample_script_files(repo)

        self.assertEqual(
            [p.relative_to(repo).as_posix() for p in discovered],
            [
                "agents/alpha/scripts/nested/three.aascript",
                "agents/alpha/scripts/one.aascript",
                "agents/alpha/scripts/two.aascript",
            ],
        )

    def test_honors_simple_upload_scripts_extension_glob(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: scripts
                glob: "*.agentscript"
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {
                "scripts/published/ship.agentscript": "1",
                "scripts/draft.aascript": "2",
                "agent.yaml": "kind: AgentTemplate\n",
            },
        )

        discovered = vs_mod.discover_sample_script_files(repo)

        self.assertEqual(
            [p.relative_to(repo).as_posix() for p in discovered],
            ["agents/alpha/scripts/published/ship.agentscript"],
        )

    def test_matches_all_files_for_complex_glob_to_mirror_installer(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: scripts
                glob: "published/*.aascript"
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {
                "scripts/published/ship.aascript": "1",
                "scripts/draft.aascript": "2",
                "scripts/readme.md": "also uploaded by current installer semantics",
                "agent.yaml": "kind: AgentTemplate\n",
            },
        )

        discovered = vs_mod.discover_sample_script_files(repo)

        self.assertEqual(
            [p.relative_to(repo).as_posix() for p in discovered],
            [
                "agents/alpha/scripts/draft.aascript",
                "agents/alpha/scripts/published/ship.aascript",
                "agents/alpha/scripts/readme.md",
            ],
        )

    def test_rejects_source_dir_parent_traversal(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: ../secrets
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {"agent.yaml": "kind: AgentTemplate\n"},
        )

        with self.assertRaisesRegex(vs_mod.SampleScriptValidationError, "must stay inside"):
            vs_mod.discover_sample_script_files(repo)

    def test_rejects_symlink_sample_directory(self) -> None:
        repo = Path(tempfile.mkdtemp())
        (repo / "agents").mkdir()
        outside = repo / "outside-sample"
        outside.mkdir()
        (outside / "sample.yaml").write_text(
            textwrap.dedent("""\
                schema_version: 2
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
            """)
        )
        (repo / "agents" / "evil").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(
            vs_mod.SampleScriptValidationError, "sample directory must not be a symlink"
        ):
            vs_mod.discover_sample_script_files(repo)

    def test_rejects_symlink_sample_yaml(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {"agent.yaml": "kind: AgentTemplate\n"},
        )
        sample_yaml = repo / "agents" / "alpha" / "sample.yaml"
        external_yaml = repo / "outside.yaml"
        external_yaml.write_text(sample_yaml.read_text())
        sample_yaml.unlink()
        sample_yaml.symlink_to(external_yaml)

        with self.assertRaisesRegex(
            vs_mod.SampleScriptValidationError, "sample.yaml must not be a symlink"
        ):
            vs_mod.discover_sample_script_files(repo)

    def test_rejects_symlink_source_dir(self) -> None:
        repo = Path(tempfile.mkdtemp())
        outside = repo / "outside"
        outside.mkdir()
        (outside / "secret.aascript").write_text("secret")
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {"agent.yaml": "kind: AgentTemplate\n"},
        )
        sample_dir = repo / "agents" / "alpha"
        (sample_dir / "scripts").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(vs_mod.SampleScriptValidationError, "must not be a symlink"):
            vs_mod.discover_sample_script_files(repo)

    def test_skips_symlinked_script_files(self) -> None:
        repo = Path(tempfile.mkdtemp())
        outside = repo / "outside.aascript"
        outside.write_text("secret")
        _write_validate_sample(
            repo,
            "alpha",
            """\
            schema_version: 2
            steps:
              - type: upload_scripts
                source_dir: scripts
              - type: deploy_agent
                template_file: agent.yaml
            """,
            {
                "scripts/ok.aascript": "1",
                "agent.yaml": "kind: AgentTemplate\n",
            },
        )
        (repo / "agents" / "alpha" / "scripts" / "leak.aascript").symlink_to(outside)

        discovered = vs_mod.discover_sample_script_files(repo)

        self.assertEqual(
            [p.relative_to(repo).as_posix() for p in discovered],
            ["agents/alpha/scripts/ok.aascript"],
        )


class ValidateScriptsTest(unittest.TestCase):
    def test_returns_nonzero_when_any_cli_validation_fails(self) -> None:
        repo = Path(tempfile.mkdtemp())
        good = repo / "agents" / "alpha" / "scripts" / "good.aascript"
        bad = repo / "agents" / "alpha" / "scripts" / "bad.aascript"
        good.parent.mkdir(parents=True)
        good.write_text("1")
        bad.write_text("let = bad")
        calls: list[list[str]] = []

        def fake_run(
            command: list[str],
            *,
            cwd: Path,
            text: bool,
            capture_output: bool,
            timeout: int,
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            self.assertNotEqual(cwd, repo)
            self.assertEqual(timeout, 60)
            failed = Path(command[-1]).name == "bad.aascript"
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "valid": not failed,
                        "ok": not failed,
                        "error": "syntax error" if failed else None,
                    }
                ),
                stderr="",
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = vs_mod.validate_scripts([good, bad], repo, "archagent", fake_run)

        self.assertEqual(exit_code, 1)
        self.assertIn("Validating agents/alpha/scripts/good.aascript", stdout.getvalue())
        self.assertIn('"valid": false', stdout.getvalue())
        self.assertIn("Script validation failed for:", stderr.getvalue())
        self.assertEqual(
            calls,
            [
                [
                    "archagent",
                    "--output",
                    "json",
                    "validate",
                    "script",
                    "--file",
                    str(good.resolve()),
                ],
                [
                    "archagent",
                    "--output",
                    "json",
                    "validate",
                    "script",
                    "--file",
                    str(bad.resolve()),
                ],
            ],
        )

    def test_returns_nonzero_when_cli_validation_times_out(self) -> None:
        repo = Path(tempfile.mkdtemp())
        script = repo / "agents" / "alpha" / "scripts" / "slow.aascript"
        script.parent.mkdir(parents=True)
        script.write_text("1")

        def fake_run(
            command: list[str],
            *,
            cwd: Path,
            text: bool,
            capture_output: bool,
            timeout: int,
        ) -> subprocess.CompletedProcess:
            raise subprocess.TimeoutExpired(command, timeout, output="partial output\n")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = vs_mod.validate_scripts([script], repo, "archagent", fake_run, 5)

        self.assertEqual(exit_code, 1)
        self.assertIn("partial output", stdout.getvalue())
        self.assertIn("Validation timed out after 5s", stderr.getvalue())
        self.assertIn("agents/alpha/scripts/slow.aascript", stderr.getvalue())


# --- support --------------------------------------------------------------


class _RedirectStderr:
    """Capture stderr during a `with` block — used to keep test output tidy."""

    def __enter__(self):
        self._saved = sys.stderr
        sys.stderr = io.StringIO()
        return sys.stderr

    def __exit__(self, *exc):
        sys.stderr = self._saved


if __name__ == "__main__":
    unittest.main()
