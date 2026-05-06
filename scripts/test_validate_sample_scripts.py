#!/usr/bin/env python3
"""
Unit tests for scripts/validate_sample_scripts.py.

Run directly:

    python3 scripts/test_validate_sample_scripts.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = SCRIPTS_DIR / "validate_sample_scripts.py"

_spec = importlib.util.spec_from_file_location("sample_script_validator", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["sample_script_validator"] = mod
_spec.loader.exec_module(mod)


def _write_sample(
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
        _write_sample(
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
        _write_sample(
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

        discovered = mod.discover_sample_script_files(repo)

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
        _write_sample(
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

        discovered = mod.discover_sample_script_files(repo)

        self.assertEqual(
            [p.relative_to(repo).as_posix() for p in discovered],
            ["agents/alpha/scripts/published/ship.agentscript"],
        )

    def test_matches_all_files_for_complex_glob_to_mirror_installer(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_sample(
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

        discovered = mod.discover_sample_script_files(repo)

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
        _write_sample(
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

        with self.assertRaisesRegex(mod.SampleScriptValidationError, "must stay inside"):
            mod.discover_sample_script_files(repo)

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

        with self.assertRaisesRegex(mod.SampleScriptValidationError, "sample directory must not be a symlink"):
            mod.discover_sample_script_files(repo)

    def test_rejects_symlink_sample_yaml(self) -> None:
        repo = Path(tempfile.mkdtemp())
        _write_sample(
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

        with self.assertRaisesRegex(mod.SampleScriptValidationError, "sample.yaml must not be a symlink"):
            mod.discover_sample_script_files(repo)

    def test_rejects_symlink_source_dir(self) -> None:
        repo = Path(tempfile.mkdtemp())
        outside = repo / "outside"
        outside.mkdir()
        (outside / "secret.aascript").write_text("secret")
        _write_sample(
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

        with self.assertRaisesRegex(mod.SampleScriptValidationError, "must not be a symlink"):
            mod.discover_sample_script_files(repo)

    def test_skips_symlinked_script_files(self) -> None:
        repo = Path(tempfile.mkdtemp())
        outside = repo / "outside.aascript"
        outside.write_text("secret")
        _write_sample(
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

        discovered = mod.discover_sample_script_files(repo)

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
        ) -> subprocess.CompletedProcess[str]:
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
            exit_code = mod.validate_scripts([good, bad], repo, "archagent", fake_run)

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
        ) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(command, timeout, output="partial output\n")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = mod.validate_scripts([script], repo, "archagent", fake_run, 5)

        self.assertEqual(exit_code, 1)
        self.assertIn("partial output", stdout.getvalue())
        self.assertIn("Validation timed out after 5s", stderr.getvalue())
        self.assertIn("agents/alpha/scripts/slow.aascript", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
