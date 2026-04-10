#!/usr/bin/env python3
"""
Unit tests for scripts/generate-plugin-content.py internal functions.

Run directly or via unittest:

    python3 scripts/test_generate_plugin_content.py
    python3 -m unittest scripts.test_generate_plugin_content
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPTS_DIR / "generate-plugin-content.py"

# The generator filename has a hyphen, so `import generate-plugin-content`
# is not legal Python. Load it via importlib. The module must be registered
# in sys.modules before exec_module() runs, because the generator's
# @dataclass decorator looks up its own module via cls.__module__ during
# class construction and crashes with NoneType if the lookup fails.
_spec = importlib.util.spec_from_file_location("plugin_generator", GENERATOR_PATH)
assert _spec is not None and _spec.loader is not None
plugin_generator = importlib.util.module_from_spec(_spec)
sys.modules["plugin_generator"] = plugin_generator
_spec.loader.exec_module(plugin_generator)


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
        return plugin_generator.check_manifest_consistency(
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

    # H1: missing-field handling (regression for None == None == None bypass)

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
        # Only the file actually missing the field should appear in the error.
        # Plain substring check (no trailing-newline suffix): when `missing`
        # has a single entry, "\n".join(...) produces no trailing newline
        # after the final path, so appending "\n" to the needle would fail
        # to catch a buggy implementation that put `marketplace_path` in the
        # missing list instead of `claude_path` — the exact failure mode
        # this assertion exists to catch.
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

    # H2: plugins[] arity (regression for silent `plugins[0]` indexing) ----

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

    # Disagreement detection (original PR scenarios) ----------------------

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

    # File-level errors ---------------------------------------------------

    def test_missing_file_fails(self):
        self._write(*self._valid_triplet())
        self.codex_path.unlink()
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot read", errors[0])
        self.assertIn("codex-plugin.json", errors[0])

    def test_invalid_json_fails(self):
        self.marketplace_path.write_text("{not valid json")
        self.claude_path.write_text(json.dumps({"name": "archagents", "version": "0.7.2"}))
        self.codex_path.write_text(json.dumps({"name": "archagents", "version": "0.7.2"}))
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON", errors[0])

    def test_marketplace_top_level_not_object_fails(self):
        self.marketplace_path.write_text(json.dumps([1, 2, 3]))
        self.claude_path.write_text(json.dumps({"name": "archagents", "version": "0.7.2"}))
        self.codex_path.write_text(json.dumps({"name": "archagents", "version": "0.7.2"}))
        errors = self._check()
        self.assertEqual(len(errors), 1)
        self.assertIn("top-level JSON is not an object", errors[0])

    # Multi-error reporting -----------------------------------------------

    def test_multiple_file_errors_reported_together(self):
        # Two broken files — both should surface in a single check call.
        self.marketplace_path.write_text("{not valid json")
        self.claude_path.write_text(json.dumps({"name": "archagents", "version": "0.7.2"}))
        self.codex_path.write_text("{also not valid")
        errors = self._check()
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("marketplace.json" in e for e in errors))
        self.assertTrue(any("codex-plugin.json" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
