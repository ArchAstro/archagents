#!/usr/bin/env python3
"""
Unit tests for scripts/check_plugin_repo.py repo-validation checks.

Run directly:

    python3 scripts/test_check_plugin_repo.py

Currently covers check_manifest_consistency and check_compat_key_refs.
Test classes for the remaining #9 checks (slash commands, hardcoded
versions, version-bump-on-change) will be added as those checks are
implemented.
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


if __name__ == "__main__":
    unittest.main()
