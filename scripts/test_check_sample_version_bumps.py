#!/usr/bin/env python3
"""
Unit tests for scripts/check_sample_version_bumps.py.

Each test builds a tmp git repo with two commits (base + head) and runs
find_unbumped_slugs against it. Covers the full matrix of bump-required
vs bump-not-required cases.

Run directly:

    python3 scripts/test_check_sample_version_bumps.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = SCRIPTS_DIR / "check_sample_version_bumps.py"

_spec = importlib.util.spec_from_file_location("version_bump_check", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["version_bump_check"] = mod
_spec.loader.exec_module(mod)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.STDOUT,
    ).decode()


def _init_repo() -> Path:
    repo = Path(tempfile.mkdtemp())
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "agents").mkdir()
    return repo


def _write_sample(repo: Path, slug: str, version: str, extra_files: dict[str, str] | None = None) -> None:
    sample_dir = repo / "agents" / slug
    sample_dir.mkdir(exist_ok=True)
    (sample_dir / "sample.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            version: {version}
            name: "Test {slug}"
            tagline: "Test sample {slug}"
            min_cli_version: "0.28.0"
            steps:
              - type: deploy_agent
                template_file: agent.yaml
            """
        )
    )
    for name, content in (extra_files or {}).items():
        (sample_dir / name).write_text(content)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


class FindUnbumpedSlugsTest(unittest.TestCase):
    def test_no_changes_under_agents_returns_empty(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        # Touch a top-level file outside agents/.
        (repo / "README.md").write_text("hello")
        _commit(repo, "non-agent change")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [])

    def test_sample_changed_without_version_bump_is_flagged(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0", extra_files={"agent.yaml": "kind: AgentTemplate\n"})
        _commit(repo, "initial")
        # Edit agent.yaml without touching sample.yaml's version.
        (repo / "agents" / "alpha" / "agent.yaml").write_text("kind: AgentTemplate\nname: edited\n")
        _commit(repo, "edit agent")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [("alpha", "v0.1.0")])

    def test_sample_changed_with_version_bump_is_clean(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0", extra_files={"agent.yaml": "kind: AgentTemplate\n"})
        _commit(repo, "initial")
        _write_sample(repo, "alpha", "v0.1.1", extra_files={"agent.yaml": "kind: AgentTemplate\nname: edited\n"})
        _commit(repo, "bump + edit")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [])

    def test_only_sample_yaml_changed_without_version_bump_is_flagged(self) -> None:
        # E.g., editing tagline but forgetting the version bump.
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        (repo / "agents" / "alpha" / "sample.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: 2
                version: v0.1.0
                name: "Test alpha"
                tagline: "Updated tagline"
                min_cli_version: "0.28.0"
                steps:
                  - type: deploy_agent
                    template_file: agent.yaml
                """
            )
        )
        _commit(repo, "edit tagline only")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [("alpha", "v0.1.0")])

    def test_new_sample_with_no_base_version_is_skipped(self) -> None:
        repo = _init_repo()
        # Initial commit has no samples.
        (repo / ".gitkeep").write_text("")
        _commit(repo, "initial empty")
        _write_sample(repo, "newcomer", "v0.1.0")
        _commit(repo, "add new sample")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [])

    def test_deleted_sample_is_skipped(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "departing", "v0.1.0")
        _commit(repo, "initial")
        sample_dir = repo / "agents" / "departing"
        for child in sample_dir.iterdir():
            child.unlink()
        sample_dir.rmdir()
        _commit(repo, "remove sample")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [])

    def test_multiple_samples_only_reports_unbumped_ones(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0", extra_files={"agent.yaml": "a\n"})
        _write_sample(repo, "beta", "v0.2.0", extra_files={"agent.yaml": "b\n"})
        _commit(repo, "initial")
        # alpha: bumped + edited. beta: edited but NOT bumped.
        _write_sample(repo, "alpha", "v0.1.1", extra_files={"agent.yaml": "a-edit\n"})
        (repo / "agents" / "beta" / "agent.yaml").write_text("b-edit\n")
        _commit(repo, "alpha bumped, beta forgot")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [("beta", "v0.2.0")])

    def test_nested_file_change_without_bump_is_flagged(self) -> None:
        # Real samples ship subdirectories (scripts/, schemas/, examples/).
        # Editing a nested file is the most common change shape and must
        # require a bump.
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        nested = repo / "agents" / "alpha" / "scripts"
        nested.mkdir()
        (nested / "tool.aascript").write_text('def main(): "hi"\n')
        _commit(repo, "initial with nested")
        (nested / "tool.aascript").write_text('def main(): "edited"\n')
        _commit(repo, "edit nested without bump")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [("alpha", "v0.1.0")])

    def test_unparseable_sample_yaml_at_head_is_silently_skipped(self) -> None:
        # check-sample-artifacts.yml owns parse-validation; this check
        # must not double-report. An unparseable sample.yaml at HEAD
        # should produce zero findings here.
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        (repo / "agents" / "alpha" / "sample.yaml").write_text("{[unclosed\n")
        _commit(repo, "broken yaml")

        self.assertEqual(mod.find_unbumped_slugs("HEAD~1", repo), [])


class VerifyRefTest(unittest.TestCase):
    def test_accepts_valid_ref(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        # Does not raise.
        mod._verify_ref("HEAD", repo)

    def test_rejects_flag_shaped_ref(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        with self.assertRaises(ValueError):
            mod._verify_ref("--exec=evil", repo)

    def test_rejects_unknown_ref(self) -> None:
        repo = _init_repo()
        _write_sample(repo, "alpha", "v0.1.0")
        _commit(repo, "initial")
        with self.assertRaises(ValueError):
            mod._verify_ref("origin/no-such-branch", repo)


if __name__ == "__main__":
    unittest.main()
