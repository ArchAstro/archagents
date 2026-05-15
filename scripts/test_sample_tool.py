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
        # Patch every module that imported the constants. Because the
        # constants are bound at import time, each module that did
        # `from .paths import AGENTS_DIR` got its own binding — we
        # rewrite all of them. Future drive-by additions: keep this
        # list in sync.
        self._patch(paths_mod, "AGENTS_DIR", self.agents_dir)
        self._patch(paths_mod, "MANIFEST_PATH", self.manifest_path)
        self._patch(paths_mod, "REPO_ROOT", self.tmp)
        self._patch(gen_mod, "AGENTS_DIR", self.agents_dir)
        self._patch(gen_mod, "MANIFEST_PATH", self.manifest_path)
        self._patch(gen_mod, "REPO_ROOT", self.tmp)
        self._patch(scaffold_mod, "AGENTS_DIR", self.agents_dir)
        # pack only uses REPO_ROOT (for tarball path display). It
        # resolves the sample dir from the cwd-relative positional arg,
        # so it doesn't import AGENTS_DIR.
        self._patch(pack_mod, "REPO_ROOT", self.tmp)
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
        with self.assertRaisesRegex(SampleError, "exactly one deploy_agent"):
            self._run(yaml)

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
