#!/usr/bin/env python3
"""
Unit tests for scripts/check_plugin_repo.py repo-validation checks.

Run directly:

    python3 scripts/test_check_plugin_repo.py

Currently covers check_manifest_consistency. Test classes for the four
additional #9 checks (compat refs, slash commands, hardcoded versions,
version-bump-on-change) will be added as those checks are implemented.
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
        # Plain substring check: when `missing` has a single entry,
        # "\n".join(...) produces no trailing newline after the final
        # path, so a "+ \\n" suffix would fail to catch a buggy impl
        # that put marketplace_path in `missing` instead of claude_path
        # (the exact failure this assertion exists to catch).
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
        # Regression: three files all setting `"version": ""` (explicit empty
        # string, not missing) must be treated the same as missing. Without
        # this branch, set-equality would collapse to `{""}` and silently
        # pass — same shape of bug as the all-None case.
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
        # The mixed case: two files have real versions, one is "". The
        # empty-string file must surface in the missing-or-empty branch,
        # not in the disagreement branch.
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


if __name__ == "__main__":
    unittest.main()
