#!/usr/bin/env python3
"""
Unit tests for scripts/check_plugin_repo.py repo-validation checks.

Run directly:

    python3 scripts/test_check_plugin_repo.py

Covers check_manifest_consistency, check_compat_key_refs,
check_slash_command_refs, check_hardcoded_versions, and
check_version_bump_on_content_change.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

# scripts/check_plugin_repo.py has no hyphen, so it imports cleanly
# unlike generate-plugin-content.py which needs importlib.
import check_plugin_repo


class ManifestConsistencyTest(unittest.TestCase):
    """Tests for check_manifest_consistency()."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.marketplace_path = self.tmp / "marketplace.json"
        self.claude_path = self.tmp / "claude-plugin.json"
        self.codex_path = self.tmp / "codex-plugin.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, marketplace: dict, claude: dict, codex: dict) -> None:
        self.marketplace_path.write_text(json.dumps(marketplace))
        self.claude_path.write_text(json.dumps(claude))
        self.codex_path.write_text(json.dumps(codex))

    def _check(self) -> list[str]:
        return check_plugin_repo.check_manifest_consistency(
            marketplace_path=self.marketplace_path,
            claude_plugin_path=self.claude_path,
            codex_plugin_path=self.codex_path,
        )

    def _valid_triplet(self) -> tuple[dict, dict, dict]:
        marketplace = {
            "name": "archagents",
            "plugins": [{"name": "archagents", "version": "0.7.2"}],
        }
        claude = {"name": "archagents", "version": "0.7.2"}
        codex = {"name": "archagents", "version": "0.7.2"}
        return marketplace, claude, codex

    # Happy path ----------------------------------------------------------

    def test_all_three_consistent_passes(self):
        self._write(*self._valid_triplet())
        self.assertEqual(self._check(), [])

    # Missing-field handling (regression for None == None == None bypass) -

    def test_all_three_missing_version_fails(self):
        mp, cp, xp = self._valid_triplet()
        del mp["plugins"][0]["version"]
        del cp["version"]
        del xp["version"]
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`version` field missing or empty", errors[0])
        self.assertIn(str(self.marketplace_path), errors[0])
        self.assertIn(str(self.claude_path), errors[0])
        self.assertIn(str(self.codex_path), errors[0])

    def test_one_missing_version_fails(self):
        mp, cp, xp = self._valid_triplet()
        del cp["version"]
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`version` field missing or empty", errors[0])
        self.assertIn(str(self.claude_path), errors[0])
        self.assertNotIn(str(self.marketplace_path), errors[0])

    def test_all_three_missing_name_fails(self):
        mp, cp, xp = self._valid_triplet()
        del mp["plugins"][0]["name"]
        del cp["name"]
        del xp["name"]
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`name` field missing or empty", errors[0])

    def test_all_three_empty_string_version_fails(self):
        # Empty strings must be rejected alongside missing fields, otherwise
        # three files agreeing at "" would pass set-equality.
        mp, cp, xp = self._valid_triplet()
        mp["plugins"][0]["version"] = ""
        cp["version"] = ""
        xp["version"] = ""
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`version` field missing or empty", errors[0])
        self.assertIn(str(self.marketplace_path), errors[0])
        self.assertIn(str(self.claude_path), errors[0])
        self.assertIn(str(self.codex_path), errors[0])

    def test_one_empty_string_version_fails(self):
        # Mixed case: one empty, two populated. The empty-string file
        # must surface as missing-or-empty, not as a drift disagreement.
        mp, cp, xp = self._valid_triplet()
        xp["version"] = ""
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`version` field missing or empty", errors[0])
        self.assertIn(str(self.codex_path), errors[0])

    # plugins[] arity (regression for silent `plugins[0]` indexing) --------

    def test_empty_plugins_list_fails(self):
        mp, cp, xp = self._valid_triplet()
        mp["plugins"] = []
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("exactly one entry in `plugins`", errors[0])
        self.assertIn("found 0", errors[0])

    def test_two_plugin_entries_fails(self):
        # Extra entries must fail loudly rather than being silently ignored
        # by [0] indexing.
        mp, cp, xp = self._valid_triplet()
        mp["plugins"].append({"name": "ghost", "version": "99.99.99"})
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("exactly one entry in `plugins`", errors[0])
        self.assertIn("found 2", errors[0])

    def test_plugins_not_a_list_fails(self):
        mp, cp, xp = self._valid_triplet()
        mp["plugins"] = {"name": "archagents", "version": "0.7.2"}
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins` to be a list", errors[0])

    def test_plugins_entry_not_a_dict_fails(self):
        mp, cp, xp = self._valid_triplet()
        mp["plugins"] = ["a string, not a plugin entry"]
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins[0]` is not an object", errors[0])

    # Disagreement detection -----------------------------------------------

    def test_version_drift_fails(self):
        mp, cp, xp = self._valid_triplet()
        mp["plugins"][0]["version"] = "0.7.3"
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("versions disagree", errors[0])
        self.assertIn("'0.7.3'", errors[0])
        self.assertIn("'0.7.2'", errors[0])

    def test_name_drift_fails(self):
        mp, cp, xp = self._valid_triplet()
        cp["name"] = "archagents-renamed"
        self._write(mp, cp, xp)
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("names disagree", errors[0])
        self.assertIn("'archagents-renamed'", errors[0])

    # File-level errors ----------------------------------------------------

    def test_missing_file_fails(self):
        self._write(*self._valid_triplet())
        self.codex_path.unlink()
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot read", errors[0])
        self.assertIn("codex-plugin.json", errors[0])

    def test_invalid_json_fails(self):
        self.marketplace_path.write_text("{not valid json")
        self.claude_path.write_text(
            json.dumps({"name": "archagents", "version": "0.7.2"})
        )
        self.codex_path.write_text(
            json.dumps({"name": "archagents", "version": "0.7.2"})
        )
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON", errors[0])

    def test_marketplace_top_level_not_object_fails(self):
        self.marketplace_path.write_text(json.dumps([1, 2, 3]))
        self.claude_path.write_text(
            json.dumps({"name": "archagents", "version": "0.7.2"})
        )
        self.codex_path.write_text(
            json.dumps({"name": "archagents", "version": "0.7.2"})
        )
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("top-level JSON is not an object", errors[0])

    # Multi-error reporting ------------------------------------------------

    def test_multiple_file_errors_reported_together(self):
        # Two broken files — both should surface in a single check call.
        self.marketplace_path.write_text("{not valid json")
        self.claude_path.write_text(
            json.dumps({"name": "archagents", "version": "0.7.2"})
        )
        self.codex_path.write_text("{also not valid")
        errors = self._check()
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("marketplace.json" in e for e in errors))
        self.assertTrue(any("codex-plugin.json" in e for e in errors))


class CompatKeyRefsTest(unittest.TestCase):
    """Tests for check_compat_key_refs()."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.compat_path = self.tmp / "plugin-compatibility.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_compat(self, data: dict) -> None:
        self.compat_path.write_text(json.dumps(data))

    def _write_content(self, name: str, text: str) -> Path:
        """Write a content file and return its path."""
        path = self.tmp / name
        path.write_text(text)
        return path

    def _check(self, *content_files: Path) -> list[str]:
        return check_plugin_repo.check_compat_key_refs(
            compat_path=self.compat_path,
            content_files=list(content_files),
        )

    def _valid_compat(self) -> dict:
        return {
            "minimumCliVersion": "0.3.1",
            "plugins": {"archagents": {"minimumCliVersion": "0.3.1"}},
        }

    # Happy path ----------------------------------------------------------

    def test_valid_reference_passes(self):
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "valid.md",
            "Look up `plugins.archagents.minimumCliVersion` for the floor.",
        )
        self.assertEqual(self._check(f), [])

    def test_no_references_passes(self):
        self._write_compat(self._valid_compat())
        f = self._write_content("plain.md", "This file has no compat keys.")
        self.assertEqual(self._check(f), [])

    def test_empty_content_file_list_passes(self):
        self._write_compat(self._valid_compat())
        self.assertEqual(self._check(), [])

    # Stale-reference detection --------------------------------------------

    def test_stale_plugin_name_fails(self):
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "stale.md",
            "Check `plugins.cli.minimumCliVersion` before invoking.",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("plugins.cli.minimumCliVersion", errors[0])
        self.assertIn("`cli` is", errors[0])
        self.assertIn("not declared", errors[0])
        self.assertIn("'archagents'", errors[0])
        self.assertIn(":1:", errors[0])

    def test_line_number_accurate(self):
        # Error line number must match the actual ref location, not line 1.
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "offset.md",
            "header line\n"
            "second line\n"
            "third line with `plugins.ghost.minimumCliVersion` ref\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn(":3:", errors[0])

    def test_stale_ref_in_multiple_files(self):
        self._write_compat(self._valid_compat())
        f1 = self._write_content("a.md", "`plugins.foo.minimumCliVersion`")
        f2 = self._write_content("b.md", "`plugins.bar.minimumCliVersion`")
        errors = self._check(f1, f2)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("a.md" in e and "foo" in e for e in errors))
        self.assertTrue(any("b.md" in e and "bar" in e for e in errors))

    def test_multiple_refs_on_same_line(self):
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "dense.md",
            "ref `plugins.foo.minimumCliVersion` then `plugins.bar.minimumCliVersion`",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(":1:" in e for e in errors))

    def test_valid_and_stale_mixed_in_same_file(self):
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "mixed.md",
            "valid `plugins.archagents.minimumCliVersion`\n"
            "stale `plugins.oldname.minimumCliVersion`\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("oldname", errors[0])
        self.assertIn(":2:", errors[0])
        self.assertNotIn("archagents.minimumCliVersion", errors[0])

    def test_case_sensitivity(self):
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "case.md",
            "Wrong case: `plugins.Archagents.minimumCliVersion`",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("Archagents", errors[0])

    # Compat file error modes --------------------------------------------

    def test_missing_compat_file_fails(self):
        # compat_path doesn't exist
        self.assertFalse(self.compat_path.exists())
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot read", errors[0])

    def test_invalid_json_compat_file_fails(self):
        self.compat_path.write_text("{not valid json")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON", errors[0])

    def test_compat_top_level_not_object_fails(self):
        self.compat_path.write_text(json.dumps([1, 2, 3]))
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("top-level JSON is not an object", errors[0])

    def test_compat_missing_plugins_key_fails(self):
        # {minimumCliVersion: ...} but no top-level plugins object.
        self.compat_path.write_text(
            json.dumps({"minimumCliVersion": "0.3.1"})
        )
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins` to be an object", errors[0])

    def test_compat_plugins_not_an_object_fails(self):
        # plugins is a list, not an object.
        self.compat_path.write_text(
            json.dumps({"plugins": ["archagents"]})
        )
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins` to be an object", errors[0])

    # Multi-plugin support -----------------------------------------------

    def test_multiple_valid_plugins_all_accepted(self):
        # When compat declares multiple plugins, all declared names are valid.
        self._write_compat(
            {
                "plugins": {
                    "archagents": {"minimumCliVersion": "0.3.1"},
                    "other": {"minimumCliVersion": "0.5.0"},
                }
            }
        )
        f = self._write_content(
            "multi.md",
            "`plugins.archagents.minimumCliVersion`\n"
            "`plugins.other.minimumCliVersion`\n",
        )
        self.assertEqual(self._check(f), [])

    def test_compat_with_empty_plugins_dict_rejects_all_refs(self):
        # An empty plugins object means no valid names — every ref must fail,
        # not pass as "no enforcement".
        self._write_compat({"plugins": {}})
        f = self._write_content(
            "x.md",
            "`plugins.archagents.minimumCliVersion`",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("`archagents` is", errors[0])
        self.assertIn("not declared", errors[0])

    def test_regex_requires_word_boundaries(self):
        # Substrings of larger identifiers must not match.
        # Uses `ghost` (invalid name) so a regex that substring-matches
        # will emit false-positive errors this assertion catches; a valid
        # name here would be silent under regression.
        self._write_compat(self._valid_compat())
        f = self._write_content(
            "wordboundaries.md",
            "xplugins.ghost.minimumCliVersion\n"
            "my_plugins.ghost.minimumCliVersion\n"
            "plugins.ghost.minimumCliVersionZ\n"
            "plugins.ghost.minimumCliVersion_suffix\n",
        )
        self.assertEqual(self._check(f), [])


class SlashCommandRefsTest(unittest.TestCase):
    """Tests for check_slash_command_refs()."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # Mirror the real repo layout: marketplace.json lives in
        # <repo>/.claude-plugin/, and plugin trees hang off <repo> via
        # `source` paths like "./.claude-plugins/<name>".
        self.marketplace_dir = self.tmp / ".claude-plugin"
        self.marketplace_dir.mkdir()
        self.marketplace_path = self.marketplace_dir / "marketplace.json"
        self.plugin_root = self.tmp / ".claude-plugins" / "archagents"
        self.commands_dir = self.plugin_root / "commands"
        self.commands_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_marketplace(self, plugins: list | None = None) -> None:
        if plugins is None:
            plugins = [
                {"name": "archagents", "source": "./.claude-plugins/archagents"}
            ]
        self.marketplace_path.write_text(json.dumps({"plugins": plugins}))

    def _add_command(self, name: str) -> None:
        (self.commands_dir / f"{name}.md").write_text("# command body\n")

    def _write_content(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.write_text(text)
        return path

    def _check(self, *content_files: Path) -> list[str]:
        return check_plugin_repo.check_slash_command_refs(
            marketplace_path=self.marketplace_path,
            content_files=list(content_files),
        )

    # Happy path ----------------------------------------------------------

    def test_valid_plugin_and_command_passes(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content("ref.md", "Run `/archagents:install` now.")
        self.assertEqual(self._check(f), [])

    def test_no_refs_passes(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content("plain.md", "no slash commands here")
        self.assertEqual(self._check(f), [])

    def test_empty_content_file_list_passes(self):
        self._write_marketplace()
        self._add_command("install")
        self.assertEqual(self._check(), [])

    # Stale references ----------------------------------------------------

    def test_stale_plugin_name_fails(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content("stale.md", "Run `/oldname:install`")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("/oldname:install", errors[0])
        self.assertIn("plugin `oldname` is", errors[0])
        self.assertIn("not declared", errors[0])
        self.assertIn("'archagents'", errors[0])
        self.assertIn(":1:", errors[0])

    def test_stale_command_name_fails(self):
        # Plugin exists, command file doesn't.
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content("stale.md", "Run `/archagents:uninstall`")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("/archagents:uninstall", errors[0])
        self.assertIn("command `uninstall`", errors[0])
        self.assertIn("does not exist", errors[0])
        self.assertIn("archagents's commands/ directory", errors[0])
        self.assertIn("'install'", errors[0])

    def test_both_stale_reports_plugin_error_only(self):
        # If plugin is unknown, command existence isn't checked (plugin
        # error is terminal).
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content("both.md", "`/oldname:uninstall`")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("plugin `oldname`", errors[0])
        self.assertNotIn("command `uninstall`", errors[0])

    def test_line_number_accurate(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content(
            "offset.md",
            "header\n"
            "second\n"
            "ref `/archagents:ghost` on line 3\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn(":3:", errors[0])

    def test_multiple_files(self):
        self._write_marketplace()
        self._add_command("install")
        f1 = self._write_content("a.md", "`/archagents:foo`")
        f2 = self._write_content("b.md", "`/archagents:bar`")
        errors = self._check(f1, f2)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("a.md" in e and "foo" in e for e in errors))
        self.assertTrue(any("b.md" in e and "bar" in e for e in errors))

    def test_multiple_refs_on_same_line(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content(
            "dense.md", "`/archagents:foo` and `/archagents:bar`"
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(":1:" in e for e in errors))

    def test_valid_and_stale_mixed(self):
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content(
            "mixed.md",
            "valid `/archagents:install`\n"
            "stale `/archagents:missing`\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing", errors[0])
        self.assertIn(":2:", errors[0])

    # Multi-command and multi-plugin -------------------------------------

    def test_multiple_commands_all_valid(self):
        self._write_marketplace()
        for cmd in ("install", "auth", "impersonate"):
            self._add_command(cmd)
        f = self._write_content(
            "multi.md",
            "`/archagents:install`\n`/archagents:auth`\n`/archagents:impersonate`\n",
        )
        self.assertEqual(self._check(f), [])

    def test_multi_plugin_marketplace(self):
        # Two plugins, each with their own commands directory. Each plugin
        # only accepts its own commands.
        other_dir = self.tmp / ".claude-plugins" / "other" / "commands"
        other_dir.mkdir(parents=True)
        (other_dir / "foo.md").write_text("# foo")
        self._write_marketplace(
            [
                {"name": "archagents", "source": "./.claude-plugins/archagents"},
                {"name": "other", "source": "./.claude-plugins/other"},
            ]
        )
        self._add_command("install")
        f = self._write_content(
            "multi.md",
            "`/archagents:install`\n"      # valid
            "`/other:foo`\n"               # valid
            "`/archagents:foo`\n"          # invalid: archagents has no `foo`
            "`/other:install`\n",          # invalid: other has no `install`
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("/archagents:foo" in e for e in errors))
        self.assertTrue(any("/other:install" in e for e in errors))

    # Marketplace error modes --------------------------------------------

    def test_missing_marketplace_fails(self):
        # Don't write marketplace.json at all
        self._add_command("install")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot read", errors[0])

    def test_invalid_json_marketplace_fails(self):
        self.marketplace_path.write_text("{nope")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON", errors[0])

    def test_marketplace_top_level_not_object_fails(self):
        self.marketplace_path.write_text(json.dumps([1, 2, 3]))
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("top-level JSON is not an object", errors[0])

    def test_marketplace_plugins_not_list_fails(self):
        self.marketplace_path.write_text(json.dumps({"plugins": {}}))
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins` to be a list", errors[0])

    def test_plugin_with_no_commands_dir_rejects_refs(self):
        # Plugin declared but its commands/ directory is missing entirely.
        import shutil
        shutil.rmtree(self.commands_dir)
        self._write_marketplace()
        f = self._write_content("ref.md", "`/archagents:install`")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("command `install`", errors[0])
        self.assertIn("does not exist", errors[0])

    def test_empty_commands_dir_rejects_refs(self):
        # commands/ exists but contains no .md files. Distinct from the
        # missing-directory case; same outcome (empty valid set).
        self._write_marketplace()
        # setUp already created self.commands_dir empty; no _add_command call
        f = self._write_content("ref.md", "`/archagents:install`")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("command `install`", errors[0])
        self.assertIn("does not exist", errors[0])

    def test_empty_plugins_list_fails(self):
        self._write_marketplace(plugins=[])
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("`plugins` list is empty", errors[0])

    def test_plugin_entry_not_a_dict_fails(self):
        self._write_marketplace(
            plugins=["not a dict", 42, {"name": "archagents",
                                         "source": "./.claude-plugins/archagents"}]
        )
        self._add_command("install")
        errors = self._check()
        # Two errors: one for index 0 (string), one for index 1 (int).
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("plugins[0]" in e and "str" in e for e in errors))
        self.assertTrue(any("plugins[1]" in e and "int" in e for e in errors))

    def test_plugin_entry_missing_name_surfaces_error(self):
        self._write_marketplace(
            plugins=[{"source": "./.claude-plugins/archagents"}]  # no name
        )
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("plugins[0]", errors[0])
        self.assertIn("missing or non-string", errors[0])
        self.assertIn("name=None", errors[0])

    def test_partial_malformed_entry_still_surfaces(self):
        # One valid entry + one malformed entry. Both produce output: the
        # malformed entry gets its per-entry error (early return means the
        # valid entry's commands aren't used, but that's fine — fix the
        # corrupt entry first, then re-run).
        self._write_marketplace(
            plugins=[
                {"name": "archagents", "source": "./.claude-plugins/archagents"},
                {"name": "broken"},  # missing source
            ]
        )
        self._add_command("install")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("plugins[1]", errors[0])
        self.assertIn("source=None", errors[0])

    # Path containment ---------------------------------------------------

    def test_source_with_absolute_path_outside_repo_fails(self):
        # A `source` pointing at an absolute path outside the repo must
        # surface as a boundary error, not be followed. Uses a separate
        # TemporaryDirectory so the fixture doesn't pollute self.tmp.parent.
        with tempfile.TemporaryDirectory() as outside_root:
            outside_commands = Path(outside_root) / "commands"
            outside_commands.mkdir()
            (outside_commands / "secret.md").write_text("# evil")

            self._write_marketplace(
                [{"name": "archagents", "source": outside_root}]
            )
            f = self._write_content("ref.md", "`/archagents:secret`")
            errors = self._check(f)
            self.assertEqual(len(errors), 1)
            self.assertIn("resolves outside the repo", errors[0])
            self.assertIn("archagents", errors[0])

    def test_source_with_relative_traversal_fails(self):
        # Same failure mode via `../` traversal instead of absolute path.
        with tempfile.TemporaryDirectory() as outside_root:
            outside_commands = Path(outside_root) / "commands"
            outside_commands.mkdir()
            (outside_commands / "secret.md").write_text("# evil")

            # `source` uses `..` from the marketplace's nominal repo base
            # (self.tmp) to escape — we compute the relative path.
            import os
            relative_source = os.path.relpath(outside_root, start=self.tmp)
            self._write_marketplace(
                [{"name": "archagents", "source": relative_source}]
            )
            f = self._write_content("ref.md", "`/archagents:secret`")
            errors = self._check(f)
            self.assertEqual(len(errors), 1)
            self.assertIn("resolves outside the repo", errors[0])

    # Regex capture discipline -------------------------------------------

    def test_regex_captures_full_command_name(self):
        # Regression guard: the regex must capture the full command
        # identifier, not a prefix. `/archagents:installer` must report
        # `installer` as the unknown command, not silently succeed by
        # matching just the `install` prefix.
        self._write_marketplace()
        self._add_command("install")
        f = self._write_content(
            "suffix.md",
            "`/archagents:installer`\n"
            "`/archagents:install_extended`\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("`installer`" in e for e in errors))
        self.assertTrue(any("`install_extended`" in e for e in errors))


class HardcodedVersionsTest(unittest.TestCase):
    """Tests for check_hardcoded_versions()."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.write_text(text)
        return path

    def _check(self, *files: Path) -> list[str]:
        return check_plugin_repo.check_hardcoded_versions(
            content_files=list(files)
        )

    # Happy path ----------------------------------------------------------

    def test_no_versions_passes(self):
        f = self._write("clean.md", "No version numbers here.")
        self.assertEqual(self._check(f), [])

    def test_empty_file_passes(self):
        f = self._write("empty.md", "")
        self.assertEqual(self._check(f), [])

    def test_two_segment_version_not_matched(self):
        # `1.2` is not a semver triple and should not fire.
        f = self._write("two.md", "Python 3.12 has new features.")
        self.assertEqual(self._check(f), [])

    def test_four_digit_year_not_matched(self):
        # Date-like strings with 4-digit year components must not match
        # because the regex bounds each segment to 1-3 digits.
        f = self._write("date.md", "Released on 2026.04.10.")
        self.assertEqual(self._check(f), [])

    # Hardcoded version detection ----------------------------------------

    def test_version_in_prose_fails(self):
        f = self._write("bad.md", "Requires archagent 0.3.1 or later.")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("hardcoded version string", errors[0])
        self.assertIn("`0.3.1`", errors[0])
        self.assertIn(":1:", errors[0])

    def test_version_in_inline_code_fails(self):
        # Inline code (single backticks) is still prose — a literal
        # version there is exactly what we want to flag.
        f = self._write("inline.md", "Use `0.7.2` for the plugin cache.")
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("`0.7.2`", errors[0])

    def test_multiple_versions_all_reported(self):
        f = self._write(
            "multi.md",
            "first 0.3.1\nsecond 1.2.3\nthird 10.20.30\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 3)
        self.assertTrue(any("`0.3.1`" in e and ":1:" in e for e in errors))
        self.assertTrue(any("`1.2.3`" in e and ":2:" in e for e in errors))
        self.assertTrue(any("`10.20.30`" in e and ":3:" in e for e in errors))

    def test_line_number_accurate(self):
        f = self._write(
            "offset.md",
            "line 1\n"
            "line 2\n"
            "line 3 with 4.5.6 version\n"
            "line 4\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn(":3:", errors[0])

    def test_multiple_files(self):
        f1 = self._write("a.md", "`1.0.0`")
        f2 = self._write("b.md", "`2.0.0`")
        errors = self._check(f1, f2)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("a.md" in e and "1.0.0" in e for e in errors))
        self.assertTrue(any("b.md" in e and "2.0.0" in e for e in errors))

    # Frontmatter exclusion -----------------------------------------------

    def test_version_in_frontmatter_ignored(self):
        f = self._write(
            "fm.md",
            "---\n"
            "name: test\n"
            "version: 1.2.3\n"
            "---\n"
            "body without versions\n",
        )
        self.assertEqual(self._check(f), [])

    def test_version_after_frontmatter_still_matched(self):
        # Versions in the body after frontmatter must still fire.
        f = self._write(
            "after-fm.md",
            "---\n"
            "name: test\n"
            "---\n"
            "\n"
            "Requires 0.3.1 to run.\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("`0.3.1`", errors[0])
        self.assertIn(":5:", errors[0])

    def test_triple_dash_in_body_not_treated_as_frontmatter(self):
        # A `---` in the body (e.g. a horizontal rule) is not a
        # frontmatter delimiter because the file didn't start with one.
        f = self._write(
            "hr.md",
            "intro\n"
            "---\n"
            "1.2.3 after horizontal rule\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("`1.2.3`", errors[0])
        self.assertIn(":3:", errors[0])

    # Fenced code block exclusion ----------------------------------------

    def test_version_in_fenced_code_block_ignored(self):
        f = self._write(
            "fence.md",
            "Setup:\n"
            "```bash\n"
            "brew install archagent@0.3.1\n"
            "```\n",
        )
        self.assertEqual(self._check(f), [])

    def test_version_in_fenced_code_ignored_with_language(self):
        # Fence opener may include a language tag.
        f = self._write(
            "lang.md",
            "```python\n"
            "VERSION = '0.3.1'\n"
            "```\n",
        )
        self.assertEqual(self._check(f), [])

    def test_mixed_prose_and_fenced_code(self):
        # Prose version before the fence: fires.
        # Version inside the fence: ignored.
        # Prose version after the fence: fires.
        f = self._write(
            "mixed.md",
            "Before 1.0.0 fence\n"
            "```\n"
            "inside 2.0.0 fence\n"
            "```\n"
            "After 3.0.0 fence\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any(":1:" in e and "1.0.0" in e for e in errors))
        self.assertTrue(any(":5:" in e and "3.0.0" in e for e in errors))

    def test_unclosed_fence_skips_to_eof(self):
        # An unclosed fence silently eats everything after it. Defensive
        # behavior: better than crashing, and contributors usually close
        # their fences.
        f = self._write(
            "unclosed.md",
            "Before 1.0.0\n"
            "```\n"
            "inside 2.0.0\n"
            "more lines 3.0.0\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 1)
        self.assertIn("1.0.0", errors[0])

    def test_tilde_fence_ignored(self):
        # Markdown also supports `~~~` as a fence delimiter.
        f = self._write(
            "tilde.md",
            "Setup:\n"
            "~~~bash\n"
            "install archagent@0.3.1\n"
            "~~~\n",
        )
        self.assertEqual(self._check(f), [])

    def test_unclosed_frontmatter_skips_whole_file(self):
        # A file starting with `---` but lacking a closing `---` is
        # treated as all-frontmatter. Lenient: better than crashing, and
        # malformed frontmatter is a different class of defect that the
        # contributor should fix at the file-format level.
        f = self._write(
            "unclosed-fm.md",
            "---\n"
            "name: test\n"
            "version: 1.2.3\n",  # no closing ---
        )
        self.assertEqual(self._check(f), [])

    def test_fence_and_frontmatter_combined(self):
        f = self._write(
            "combo.md",
            "---\n"
            "name: test\n"
            "version: 0.1.0\n"
            "---\n"
            "\n"
            "Body version 1.2.3 in prose\n"
            "```\n"
            "Fenced 4.5.6\n"
            "```\n"
            "Trailing 7.8.9 prose\n",
        )
        errors = self._check(f)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("1.2.3" in e for e in errors))
        self.assertTrue(any("7.8.9" in e for e in errors))
        self.assertFalse(any("0.1.0" in e for e in errors))  # frontmatter
        self.assertFalse(any("4.5.6" in e for e in errors))  # fenced


class MainRunnerTest(unittest.TestCase):
    """
    Tests for main() and the CHECKS registry. Monkey-patches CHECKS with
    fixture lists so each test exercises exactly the shape it cares about;
    one sanity test at the end asserts the real CHECKS registry has the
    expected entries in the expected order.
    """

    def setUp(self) -> None:
        self._original_checks = check_plugin_repo.CHECKS

    def tearDown(self) -> None:
        check_plugin_repo.CHECKS = self._original_checks

    def _run_main(self) -> tuple[int, str, str]:
        """Call main(), return (exit_code, stdout, stderr)."""
        import io
        import contextlib
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = check_plugin_repo.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    # Exit codes ----------------------------------------------------------

    def test_all_checks_pass_returns_zero(self):
        check_plugin_repo.CHECKS = [
            ("fixture-a", lambda: []),
            ("fixture-b", lambda: []),
        ]
        exit_code, stdout, stderr = self._run_main()
        self.assertEqual(exit_code, 0)
        self.assertIn("OK   [fixture-a]", stdout)
        self.assertIn("OK   [fixture-b]", stdout)
        self.assertEqual(stderr, "")

    def test_any_check_fails_returns_one(self):
        check_plugin_repo.CHECKS = [
            ("pass", lambda: []),
            ("fail", lambda: ["something broke"]),
        ]
        exit_code, stdout, stderr = self._run_main()
        self.assertEqual(exit_code, 1)
        self.assertIn("OK   [pass]", stdout)
        self.assertIn("FAIL [fail]", stderr)
        self.assertIn("something broke", stderr)

    def test_all_checks_fail_returns_one(self):
        check_plugin_repo.CHECKS = [
            ("a", lambda: ["a broke"]),
            ("b", lambda: ["b broke"]),
        ]
        exit_code, _, stderr = self._run_main()
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL [a]", stderr)
        self.assertIn("FAIL [b]", stderr)

    def test_empty_checks_list_returns_zero(self):
        # Degenerate case: no checks registered. Trivially passes.
        check_plugin_repo.CHECKS = []
        exit_code, stdout, stderr = self._run_main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    # Ordering ------------------------------------------------------------

    def test_checks_run_in_registry_order(self):
        order: list[str] = []

        def make_check(name: str):
            def check() -> list[str]:
                order.append(name)
                return []
            return check

        check_plugin_repo.CHECKS = [
            ("first", make_check("first")),
            ("second", make_check("second")),
            ("third", make_check("third")),
        ]
        self._run_main()
        self.assertEqual(order, ["first", "second", "third"])

    def test_all_checks_run_even_after_a_failure(self):
        # A failing check must not short-circuit the runner; later checks
        # still run so their errors surface in the same report.
        order: list[str] = []

        def make_check(name: str, errs: list[str]):
            def check() -> list[str]:
                order.append(name)
                return errs
            return check

        check_plugin_repo.CHECKS = [
            ("a", make_check("a", ["a-err"])),
            ("b", make_check("b", [])),
            ("c", make_check("c", ["c-err"])),
        ]
        _, stdout, stderr = self._run_main()
        self.assertEqual(order, ["a", "b", "c"])
        self.assertIn("FAIL [a]", stderr)
        self.assertIn("FAIL [c]", stderr)
        self.assertIn("OK   [b]", stdout)

    # Output formatting ---------------------------------------------------

    def test_failed_check_output_routes_to_stderr(self):
        check_plugin_repo.CHECKS = [("x", lambda: ["boom"])]
        _, stdout, stderr = self._run_main()
        self.assertIn("FAIL [x]:", stderr)
        self.assertIn("boom", stderr)
        # Failures do not leak into stdout.
        self.assertNotIn("FAIL", stdout)
        self.assertNotIn("boom", stdout)

    def test_passed_check_output_routes_to_stdout(self):
        check_plugin_repo.CHECKS = [("y", lambda: [])]
        _, stdout, stderr = self._run_main()
        self.assertIn("OK   [y]", stdout)
        # Passes do not leak into stderr.
        self.assertEqual(stderr, "")

    def test_multiline_error_each_line_indented(self):
        # Errors with embedded newlines (e.g. check_manifest_consistency's
        # multi-file reports) must have each line indented by 2 spaces under
        # the header so the output stays legible.
        check_plugin_repo.CHECKS = [
            ("multi", lambda: ["first line\nsecond line\nthird line"]),
        ]
        _, _, stderr = self._run_main()
        self.assertIn("  first line", stderr)
        self.assertIn("  second line", stderr)
        self.assertIn("  third line", stderr)

    def test_multiple_errors_from_single_check_all_printed(self):
        check_plugin_repo.CHECKS = [
            ("x", lambda: ["err1", "err2", "err3"]),
        ]
        _, _, stderr = self._run_main()
        self.assertIn("err1", stderr)
        self.assertIn("err2", stderr)
        self.assertIn("err3", stderr)

    # Real CHECKS registry sanity ----------------------------------------

    def test_real_checks_registry_has_expected_entries(self):
        # The real CHECKS list should contain all 5 checks in the expected
        # order. This guards against accidental removal or reordering that
        # would break invariants documented in the comment above CHECKS.
        names = [name for name, _ in self._original_checks]
        self.assertEqual(
            names,
            [
                "manifest consistency",
                "compat key refs",
                "slash command refs",
                "hardcoded versions",
                "version bump on content change",
            ],
        )

    def test_manifest_consistency_runs_before_version_bump(self):
        # version-bump-on-content-change assumes check_manifest_consistency
        # has already validated cross-file version agreement, so it can
        # compare just one manifest against the PR base. Enforce the ordering
        # invariant so a future reorder can't silently break it.
        names = [name for name, _ in self._original_checks]
        mc_idx = names.index("manifest consistency")
        vb_idx = names.index("version bump on content change")
        self.assertLess(
            mc_idx,
            vb_idx,
            "manifest consistency must run before version-bump check",
        )

    def test_every_registered_check_is_callable(self):
        for name, check in self._original_checks:
            self.assertTrue(
                callable(check),
                f"CHECKS entry {name!r} is not callable",
            )


class VersionBumpOnContentChangeTest(unittest.TestCase):
    """Tests for check_version_bump_on_content_change().

    Each test sets up a real git repo in a tmpdir with an initial commit
    (base state), then the test body applies whatever changes it wants
    and runs the check against `base_ref=HEAD~1`. This exercises the real
    git shell-out path rather than mocking it.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

        self.marketplace_path = self.tmp / ".claude-plugin" / "marketplace.json"
        self.marketplace_path.parent.mkdir()
        self.sources_dir = self.tmp / "sources"
        self.sources_dir.mkdir()
        self.skills_dir = (
            self.tmp / ".claude-plugins" / "archagents" / "skills"
        )
        self.skills_dir.mkdir(parents=True)

        # Initialize a fresh git repo and make the base commit at 0.1.0.
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        # Environment overrides are also set for commit authorship so the
        # test doesn't depend on the developer's global git config.
        self._write_marketplace("0.1.0")
        self._write_source("baseline.md", "# baseline\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "base state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        """Run `git -C <tmp> <args>`. Test envs force a clean git identity."""
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }
        )
        return subprocess.run(
            ["git", "-C", str(self.tmp), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def _write_marketplace(self, version: str) -> None:
        self.marketplace_path.write_text(
            json.dumps(
                {
                    "plugins": [
                        {"name": "archagents", "version": version}
                    ]
                }
            )
        )

    def _write_source(self, name: str, text: str) -> None:
        (self.sources_dir / name).write_text(text)

    def _write_skill(self, name: str, text: str) -> None:
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(text)

    def _commit(self, message: str) -> None:
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def _check(self, base_ref: str = "HEAD~1") -> list[str]:
        return check_plugin_repo.check_version_bump_on_content_change(
            marketplace_path=self.marketplace_path,
            base_ref=base_ref,
            repo_root=self.tmp,
        )

    # Happy path ----------------------------------------------------------

    def test_no_changes_passes(self):
        # HEAD == HEAD~1 has no diff at the skin level but git's `diff
        # base...HEAD` still returns empty when there's nothing to compare.
        # We create an empty second commit to model "nothing changed".
        self._git("commit", "-q", "--allow-empty", "-m", "empty")
        self.assertEqual(self._check(), [])

    def test_content_change_with_version_bump_passes(self):
        self._write_source("baseline.md", "# baseline\n\nUpdated content.\n")
        self._write_marketplace("0.1.1")
        self._commit("update content and bump version")
        self.assertEqual(self._check(), [])

    def test_non_content_change_without_bump_passes(self):
        # README changes don't require a bump — not plugin content.
        (self.tmp / "README.md").write_text("# repo readme\n")
        self._commit("add readme")
        self.assertEqual(self._check(), [])

    def test_scripts_change_without_bump_passes(self):
        # scripts/ is infra, not plugin content.
        scripts = self.tmp / "scripts"
        scripts.mkdir()
        (scripts / "helper.sh").write_text("#!/bin/sh\n")
        self._commit("add helper script")
        self.assertEqual(self._check(), [])

    def test_manifest_only_change_passes(self):
        # Bumping the manifest without touching content is fine — maybe a
        # metadata update, maybe preparation for a release with no content
        # diff yet. No content changed → no bump required → pass.
        self._write_marketplace("0.2.0")
        self._commit("bump version without touching content")
        self.assertEqual(self._check(), [])

    # Failure cases --------------------------------------------------------

    def test_source_change_without_bump_fails(self):
        self._write_source("baseline.md", "# baseline\n\nEdited body.\n")
        self._commit("edit source without bumping version")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("plugin content changed", errors[0])
        self.assertIn("still '0.1.0'", errors[0])
        self.assertIn("sources/baseline.md", errors[0])

    def test_new_source_file_without_bump_fails(self):
        self._write_source("new-skill.md", "# new skill\n")
        self._commit("add new source")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("sources/new-skill.md", errors[0])

    def test_skill_tree_change_without_bump_fails(self):
        # Changes under .claude-plugins/archagents/skills/ are content.
        self._write_skill("chat", "---\nname: chat\n---\n\nbody\n")
        self._commit("add skill")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn(".claude-plugins/archagents/skills/chat/SKILL.md", errors[0])

    def test_multiple_content_files_listed_in_error(self):
        self._write_source("a.md", "# a\n")
        self._write_source("b.md", "# b\n")
        self._commit("add two sources")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("sources/a.md", errors[0])
        self.assertIn("sources/b.md", errors[0])

    def test_mixed_content_and_docs_still_fails(self):
        # One content file + one non-content file, no bump → still fails
        # (one content change is enough to require a bump).
        self._write_source("content.md", "# content\n")
        (self.tmp / "README.md").write_text("# readme\n")
        self._commit("mixed change")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("sources/content.md", errors[0])
        self.assertNotIn("README.md", errors[0])

    def test_deleted_content_file_without_bump_fails(self):
        # Deleting a skill file is a content change and requires a bump.
        (self.sources_dir / "baseline.md").unlink()
        self._commit("delete baseline")
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("sources/baseline.md", errors[0])

    # Skip conditions ------------------------------------------------------

    def test_unreachable_base_ref_skips_with_warning(self):
        # Skip returns empty (pass), but prints a warning to stderr so a
        # misconfigured CI doesn't silently no-op the check.
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            errors = check_plugin_repo.check_version_bump_on_content_change(
                marketplace_path=self.marketplace_path,
                base_ref="nonexistent-branch",
                repo_root=self.tmp,
            )
        self.assertEqual(errors, [])
        self.assertIn("WARN", stderr.getvalue())
        self.assertIn("unreachable", stderr.getvalue())
        self.assertIn("fetch-depth: 0", stderr.getvalue())

    def test_base_without_marketplace_treats_as_implicit_bump(self):
        # If marketplace.json didn't exist at the base ref (e.g. the file
        # was added in this PR), there's no base version to compare against
        # and the "current version" is definitionally new. Skip with no
        # error — the contributor is bootstrapping the plugin.
        self.marketplace_path.unlink()
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "remove marketplace")
        # Re-create marketplace and touch content — the base (HEAD~1) has no
        # marketplace, so the check should treat this as an implicit bump.
        self._write_marketplace("0.1.0")
        self._write_source("baseline.md", "# baseline\n\nchange\n")
        self._commit("add marketplace back with content change")
        # base=HEAD~1 is the "remove marketplace" commit; marketplace.json
        # does not exist there, so the show fails and we skip cleanly.
        self.assertEqual(self._check(), [])

    def test_push_to_main_scenario_trivially_passes(self):
        # Simulates a push-to-main where HEAD has already advanced past the
        # nominal base. The diff against HEAD itself is empty → pass.
        self._write_source("baseline.md", "# baseline\n\nupdated\n")
        self._write_marketplace("0.1.1")
        self._commit("content update")
        # Diff HEAD...HEAD is empty.
        errors = check_plugin_repo.check_version_bump_on_content_change(
            marketplace_path=self.marketplace_path,
            base_ref="HEAD",
            repo_root=self.tmp,
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
