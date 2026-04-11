#!/usr/bin/env python3
"""
Unit tests for scripts/check_plugin_repo.py repo-validation checks.

Run directly:

    python3 scripts/test_check_plugin_repo.py

Covers check_manifest_consistency, check_compat_key_refs, and
check_slash_command_refs. Test classes for the remaining #9 checks
(hardcoded versions, version-bump-on-change) will be added as those
checks are implemented.
"""
import json
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


if __name__ == "__main__":
    unittest.main()
