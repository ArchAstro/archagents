#!/usr/bin/env python3
"""
Unit tests for scripts/generate_sample_artifacts.py.

Run directly:

    python3 scripts/test_generate_sample_artifacts.py

Tests use tmp dirs to validate the pure functions (validation, rendering)
without touching the real agents/ tree. The integration check (committed
artifacts match what the generator would produce) is covered by running
the generator with --check in CI; we don't duplicate that here.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPTS_DIR / "generate_sample_artifacts.py"

_spec = importlib.util.spec_from_file_location("sample_generator", GENERATOR_PATH)
assert _spec is not None and _spec.loader is not None
gen = importlib.util.module_from_spec(_spec)
sys.modules["sample_generator"] = gen
_spec.loader.exec_module(gen)


def _make_sample_dir(**overrides) -> Path:
    """
    Build a minimal-valid sample directory in a tmp path and return it.
    Callers override `sample_yaml` (string) or specific fields.
    """
    tmp = Path(tempfile.mkdtemp())
    # Default directory layout — matches what the default `steps:` expects.
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


class ValidateSampleTest(unittest.TestCase):
    """Every error path should produce a useful, pointed message."""

    def test_minimal_sample_passes(self):
        sample_dir = _make_sample_dir()
        parsed = gen.validate_sample(
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
        with self.assertRaisesRegex(gen.SampleError, "schema_version"):
            gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

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
        with self.assertRaisesRegex(gen.SampleError, "version"):
            gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

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
        with self.assertRaisesRegex(gen.SampleError, "steps"):
            gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

    def test_legacy_deploy_mode_field_is_rejected(self):
        # Authors migrating from schema v1 shouldn't accidentally leave
        # deploy_mode or capabilities behind — the generator would silently
        # ignore them under the new schema, so fail loud.
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
        with self.assertRaisesRegex(gen.SampleError, "deploy_mode"):
            gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

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
        with self.assertRaisesRegex(gen.SampleError, "capabilities"):
            gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")


class ValidateStepsTest(unittest.TestCase):

    def _run(self, sample_yaml: str) -> None:
        sample_dir = _make_sample_dir(sample_yaml=sample_yaml)
        # Also create skills/ so upload_skills tests work with real dirs.
        (sample_dir / "skills").mkdir(exist_ok=True)
        (sample_dir / "schemas").mkdir(exist_ok=True)
        (sample_dir / "rules").mkdir(exist_ok=True)
        (sample_dir / "knowledge").mkdir(exist_ok=True)
        gen.validate_sample("x", _parsed(sample_dir), sample_dir / "sample.yaml")

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
        with self.assertRaisesRegex(gen.SampleError, "unknown_verb"):
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
            # upload_files requires installation_kind + source_type
        """)
        with self.assertRaisesRegex(gen.SampleError, "installation_kind|source_type"):
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
        with self.assertRaisesRegex(gen.SampleError, "extra_junk"):
            self._run(yaml)

    def test_missing_source_dir_is_caught(self):
        # `upload_scripts source_dir: nonexistent` should fail the
        # on-disk reality check.
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
        with self.assertRaisesRegex(gen.SampleError, "nope"):
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
        with self.assertRaisesRegex(gen.SampleError, "deploy_agent"):
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
        with self.assertRaisesRegex(gen.SampleError, "deploy_agent"):
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
        with self.assertRaisesRegex(gen.SampleError, "exactly one deploy_agent"):
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
        # Should not raise
        self._run(yaml)


class RenderAaignoreTest(unittest.TestCase):

    def test_lists_every_top_level_entry_with_dir_slash(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "agent.yaml").write_text("x")
        (tmp / "sample.yaml").write_text("schema_version: 2")
        (tmp / "scripts").mkdir()
        (tmp / "schemas").mkdir()

        body = gen.render_aaignore(tmp)
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
        body = gen.render_aaignore(tmp)
        self.assertNotIn(".aaignore", body)


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
        a = gen.render_manifest(samples)
        b = gen.render_manifest(samples)
        self.assertEqual(a, b)

    def test_manifest_includes_required_fields(self):
        body = gen.render_manifest([self._sample("alpha")])
        parsed = json.loads(body)
        self.assertEqual(parsed["$schema_version"], gen.MANIFEST_SCHEMA_VERSION)
        entry = parsed["samples"][0]
        for key in ("slug", "name", "tagline", "current_version", "min_cli_version"):
            self.assertIn(key, entry)
        # steps: is sample-internal and must NOT leak into the manifest —
        # the CLI only needs the catalog metadata.
        self.assertNotIn("steps", entry)

    def test_manifest_preserves_unicode(self):
        body = gen.render_manifest([self._sample("alpha", tagline="A sample — with a dash.")])
        self.assertIn("—", body)
        self.assertNotIn("\\u", body)


if __name__ == "__main__":
    unittest.main()
