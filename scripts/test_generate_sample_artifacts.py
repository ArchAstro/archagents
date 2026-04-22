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


def _generated_sample(slug: str = "alpha", **overrides) -> dict:
    """A minimal valid `generated`-mode parsed sample, for render tests."""
    sample = {
        "slug": slug,
        "version": "v0.1.0",
        "name": f"{slug.title()} Sample",
        "tagline": "An example sample.",
        "min_cli_version": "0.25.0",
        "deploy_mode": "generated",
        "capabilities": {
            "scripts": True,
            "skills": False,
            "agent": True,
            "env_example": True,
        },
    }
    sample.update(overrides)
    return sample


class ValidateSampleTest(unittest.TestCase):
    """Focused validator tests — every error path should produce a useful message."""

    def _write(self, body: str) -> Path:
        # tempdir survives the test method; unittest cleans /tmp eventually.
        tmpdir = Path(tempfile.mkdtemp())
        path = tmpdir / "sample.yaml"
        path.write_text(body)
        return path

    def test_minimal_generated_passes(self):
        # Set up a fake sample dir with the files capabilities expects.
        path = self._write(
            textwrap.dedent("""\
                schema_version: 1
                version: v0.1.0
                name: Alpha
                tagline: An alpha sample.
                min_cli_version: "0.25.0"
                deploy_mode: generated
                capabilities:
                  scripts: true
                  skills: false
                  agent: true
                  env_example: true
            """)
        )
        sample_dir = path.parent
        (sample_dir / "scripts").mkdir()
        (sample_dir / "agent.yaml").write_text("name: x\n")
        (sample_dir / "env.example").write_text("FOO=bar\n")

        import yaml as pyyaml
        sample = gen.validate_sample("alpha", pyyaml.safe_load(path.read_text()), path)
        self.assertEqual(sample["slug"], "alpha")
        self.assertEqual(sample["version"], "v0.1.0")
        self.assertEqual(sample["deploy_mode"], "generated")
        self.assertTrue(sample["capabilities"]["scripts"])

    def test_custom_does_not_require_capabilities(self):
        path = self._write(
            textwrap.dedent("""\
                schema_version: 1
                version: v0.2.0
                name: Beta
                tagline: A custom sample.
                min_cli_version: "0.25.0"
                deploy_mode: custom
            """)
        )
        import yaml as pyyaml
        sample = gen.validate_sample("beta", pyyaml.safe_load(path.read_text()), path)
        self.assertEqual(sample["deploy_mode"], "custom")
        self.assertEqual(sample["capabilities"], {})

    def test_custom_with_capabilities_block_is_rejected(self):
        # Silently-ignored config is a foot-gun. Reject loudly.
        path = self._write(
            textwrap.dedent("""\
                schema_version: 1
                version: v0.1.0
                name: X
                tagline: X
                min_cli_version: "0.25.0"
                deploy_mode: custom
                capabilities:
                  scripts: true
            """)
        )
        import yaml as pyyaml
        with self.assertRaisesRegex(gen.SampleError, "capabilities"):
            gen.validate_sample("x", pyyaml.safe_load(path.read_text()), path)

    def test_bad_version_format_is_rejected(self):
        path = self._write(
            textwrap.dedent("""\
                schema_version: 1
                version: 1.0.0
                name: X
                tagline: X
                min_cli_version: "0.25.0"
                deploy_mode: custom
            """)
        )
        import yaml as pyyaml
        with self.assertRaisesRegex(gen.SampleError, "version"):
            gen.validate_sample("x", pyyaml.safe_load(path.read_text()), path)

    def test_capabilities_must_match_disk(self):
        # capabilities.skills=true with no skills/ dir -> generator catches it
        # before deploying a script that loops over nothing.
        path = self._write(
            textwrap.dedent("""\
                schema_version: 1
                version: v0.1.0
                name: X
                tagline: X
                min_cli_version: "0.25.0"
                deploy_mode: generated
                capabilities:
                  scripts: false
                  skills: true
                  agent: false
                  env_example: false
            """)
        )
        import yaml as pyyaml
        with self.assertRaisesRegex(gen.SampleError, "skills/"):
            gen.validate_sample("x", pyyaml.safe_load(path.read_text()), path)

    def test_unknown_schema_version_is_rejected(self):
        path = self._write(
            textwrap.dedent("""\
                schema_version: 99
                version: v0.1.0
                name: X
                tagline: X
                min_cli_version: "0.25.0"
                deploy_mode: custom
            """)
        )
        import yaml as pyyaml
        with self.assertRaisesRegex(gen.SampleError, "schema_version"):
            gen.validate_sample("x", pyyaml.safe_load(path.read_text()), path)


class RenderAaignoreTest(unittest.TestCase):

    def test_lists_every_top_level_entry_with_dir_slash(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "agent.yaml").write_text("x")
        (tmp / "deploy.sh").write_text("#!/bin/bash")
        (tmp / "scripts").mkdir()
        (tmp / "schemas").mkdir()
        # Files the generator owns must not appear (they'd self-list).
        (tmp / "sample.yaml").write_text("schema_version: 1")

        body = gen.render_aaignore(tmp)
        # Header is always present so consumers know it's generated.
        self.assertIn("Auto-generated", body)
        # Files appear bare.
        self.assertIn("\nagent.yaml\n", body)
        self.assertIn("\ndeploy.sh\n", body)
        self.assertIn("\nsample.yaml\n", body)
        # Dirs appear with trailing slash.
        self.assertIn("\nscripts/\n", body)
        self.assertIn("\nschemas/\n", body)

    def test_aaignore_skips_itself(self):
        # If the .aaignore file already exists from a prior run, the
        # generator should not list itself in its own output (which would
        # be tautological and grow on every regen if we weren't careful).
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".aaignore").write_text("stale\n")
        (tmp / "agent.yaml").write_text("x")
        body = gen.render_aaignore(tmp)
        self.assertNotIn(".aaignore", body)


class RenderDeployShTest(unittest.TestCase):

    def test_full_capabilities_includes_all_blocks(self):
        sample = _generated_sample()
        body = gen.render_deploy_sh(sample)
        self.assertIn("set -euo pipefail", body)
        self.assertIn("ARCHASTRO_CLI", body)              # CLI detection block
        self.assertIn("source .env", body)                # env loader
        self.assertIn("Deploying scripts", body)          # scripts block
        self.assertIn("Deploying agent", body)            # agent block
        self.assertIn('describe agent alpha', body)       # finished hint

    def test_disabled_blocks_are_omitted(self):
        sample = _generated_sample(
            capabilities={"scripts": False, "skills": False, "agent": True, "env_example": False}
        )
        body = gen.render_deploy_sh(sample)
        self.assertNotIn("source .env", body)
        self.assertNotIn("Deploying scripts", body)
        self.assertIn("Deploying agent", body)

    def test_generated_script_is_syntactically_valid_bash(self):
        # Catch template typos early — bash -n parses without executing.
        import subprocess
        sample = _generated_sample()
        body = gen.render_deploy_sh(sample)
        result = subprocess.run(
            ["bash", "-n", "/dev/stdin"],
            input=body,
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"generated deploy.sh failed bash -n:\n{result.stderr}\n--- script ---\n{body}",
        )


class RenderManifestTest(unittest.TestCase):

    def test_manifest_is_deterministic_json(self):
        # Run twice with the same input; output must byte-match. Drift in
        # this property would make --check fail on every PR.
        samples = [_generated_sample("alpha"), _generated_sample("beta", deploy_mode="custom", capabilities={})]
        a = gen.render_manifest(samples)
        b = gen.render_manifest(samples)
        self.assertEqual(a, b)

    def test_manifest_includes_required_fields(self):
        samples = [_generated_sample("alpha")]
        body = gen.render_manifest(samples)
        parsed = json.loads(body)
        self.assertEqual(parsed["$schema_version"], gen.SCHEMA_VERSION)
        entry = parsed["samples"][0]
        for key in ("slug", "name", "tagline", "current_version", "min_cli_version"):
            self.assertIn(key, entry)

    def test_manifest_preserves_unicode(self):
        # ensure_ascii=False — em-dashes and friends should be readable.
        samples = [_generated_sample("alpha", tagline="A sample — with a dash.")]
        body = gen.render_manifest(samples)
        self.assertIn("—", body)
        self.assertNotIn("\\u", body)


if __name__ == "__main__":
    unittest.main()
