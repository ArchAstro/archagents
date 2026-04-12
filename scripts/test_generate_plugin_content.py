#!/usr/bin/env python3
"""
Unit tests for scripts/generate-plugin-content.py internal functions.

Run directly:

    python3 scripts/test_generate_plugin_content.py
"""
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPTS_DIR / "generate-plugin-content.py"

# The generator filename has a hyphen, so it needs importlib to load.
# Register in sys.modules before exec_module because @dataclass looks
# up its own module via cls.__module__ during class construction.
_spec = importlib.util.spec_from_file_location("plugin_generator", GENERATOR_PATH)
assert _spec is not None and _spec.loader is not None
plugin_generator = importlib.util.module_from_spec(_spec)
sys.modules["plugin_generator"] = plugin_generator
_spec.loader.exec_module(plugin_generator)


class SplitFrontmatterTest(unittest.TestCase):

    def test_valid_frontmatter(self):
        fm, body = plugin_generator.split_frontmatter(
            "---\nname: test\ndescription: hello\n---\nbody content\n"
        )
        self.assertEqual(fm["name"], "test")
        self.assertEqual(fm["description"], "hello")
        self.assertEqual(body, "body content\n")

    def test_multi_line_body(self):
        fm, body = plugin_generator.split_frontmatter(
            "---\nname: x\n---\nline1\nline2\nline3\n"
        )
        self.assertEqual(fm["name"], "x")
        self.assertEqual(body, "line1\nline2\nline3\n")

    def test_empty_body(self):
        fm, body = plugin_generator.split_frontmatter(
            "---\nname: x\n---\n"
        )
        self.assertEqual(fm["name"], "x")
        self.assertEqual(body, "")

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(ValueError, msg="no frontmatter block"):
            plugin_generator.split_frontmatter("no frontmatter here")

    def test_unterminated_frontmatter_raises(self):
        with self.assertRaises(ValueError, msg="unterminated frontmatter"):
            plugin_generator.split_frontmatter("---\nname: x\nno closing")

    def test_non_mapping_frontmatter_raises(self):
        # YAML that parses to a list, not a dict
        with self.assertRaises(ValueError, msg="not a mapping"):
            plugin_generator.split_frontmatter("---\n- item1\n- item2\n---\nbody\n")


class ApplySubstitutionsTest(unittest.TestCase):

    def test_claude_harness(self):
        text = "Use {{HARNESS_NAME}} and {{SESSION}} for setup."
        result = plugin_generator.apply_substitutions(text, "claude")
        self.assertIn("Claude Code", result)
        self.assertIn("Claude Code session", result)
        self.assertNotIn("{{", result)

    def test_codex_harness(self):
        text = "Use {{HARNESS_NAME}} and {{SESSION}} for setup."
        result = plugin_generator.apply_substitutions(text, "codex")
        self.assertIn("Codex", result)
        self.assertIn("Codex session", result)
        self.assertNotIn("{{", result)

    def test_install_route_differs(self):
        text = "{{INSTALL_ROUTE}}"
        claude = plugin_generator.apply_substitutions(text, "claude")
        codex = plugin_generator.apply_substitutions(text, "codex")
        self.assertNotEqual(claude, codex)
        self.assertIn("/archagents:install", claude)
        self.assertNotIn("/archagents:install", codex)

    def test_unknown_placeholder_left_as_is(self):
        text = "{{UNKNOWN_PLACEHOLDER}} stays"
        result = plugin_generator.apply_substitutions(text, "claude")
        self.assertIn("{{UNKNOWN_PLACEHOLDER}}", result)

    def test_multiple_on_same_line(self):
        text = "{{HARNESS_NAME}} uses {{AUTH_ROUTE}}"
        result = plugin_generator.apply_substitutions(text, "claude")
        self.assertNotIn("{{", result)


class ApplyConditionalsTest(unittest.TestCase):

    def test_skill_block_kept_for_claude_skill(self):
        text = "before{{#SKILL}}inside{{/SKILL}}after"
        result = plugin_generator.apply_conditionals(text, "claude-skill")
        self.assertEqual(result, "beforeinsideafter")

    def test_skill_block_kept_for_codex_skill(self):
        text = "before{{#SKILL}}inside{{/SKILL}}after"
        result = plugin_generator.apply_conditionals(text, "codex-skill")
        self.assertEqual(result, "beforeinsideafter")

    def test_skill_block_stripped_for_command(self):
        text = "before{{#SKILL}}inside{{/SKILL}}after"
        result = plugin_generator.apply_conditionals(text, "claude-command")
        self.assertEqual(result, "beforeafter")

    def test_command_block_kept_for_command(self):
        text = "before{{#CLAUDE_COMMAND}}inside{{/CLAUDE_COMMAND}}after"
        result = plugin_generator.apply_conditionals(text, "claude-command")
        self.assertEqual(result, "beforeinsideafter")

    def test_command_block_stripped_for_skill(self):
        text = "before{{#CLAUDE_COMMAND}}inside{{/CLAUDE_COMMAND}}after"
        result = plugin_generator.apply_conditionals(text, "claude-skill")
        self.assertEqual(result, "beforeafter")

    def test_multiple_blocks(self):
        text = "{{#SKILL}}A{{/SKILL}}mid{{#CLAUDE_COMMAND}}B{{/CLAUDE_COMMAND}}"
        result = plugin_generator.apply_conditionals(text, "claude-skill")
        self.assertEqual(result, "Amid")

    def test_unbalanced_markers_raise(self):
        text = "{{#SKILL}}open but no close"
        with self.assertRaises(ValueError, msg="unbalanced"):
            plugin_generator.apply_conditionals(text, "claude-skill")

    def test_extra_close_raises(self):
        text = "{{#SKILL}}inside{{/SKILL}}{{/SKILL}}"
        with self.assertRaises(ValueError, msg="unbalanced"):
            plugin_generator.apply_conditionals(text, "claude-skill")

    def test_multiline_block(self):
        text = "before\n{{#SKILL}}\nline1\nline2\n{{/SKILL}}\nafter"
        result = plugin_generator.apply_conditionals(text, "claude-skill")
        self.assertIn("line1", result)
        self.assertIn("line2", result)
        self.assertIn("before", result)
        self.assertIn("after", result)


class FormatFrontmatterTest(unittest.TestCase):

    def test_simple_dict(self):
        result = plugin_generator.format_frontmatter(
            {"name": "test", "description": "a test skill"}
        )
        self.assertTrue(result.startswith("---\n"))
        self.assertTrue(result.endswith("---\n"))
        self.assertIn("name: test", result)
        self.assertIn("description: a test skill", result)

    def test_list_values_flow_style(self):
        result = plugin_generator.format_frontmatter(
            {"allowed-tools": ["Read", "Write", "Bash"]}
        )
        self.assertIn('allowed-tools: ["Read", "Write", "Bash"]', result)

    def test_round_trip_preserves_dict(self):
        import yaml
        fm = {"name": "test", "description": "hello world"}
        result = plugin_generator.format_frontmatter(fm)
        # Strip the --- fences and re-parse
        yaml_body = "\n".join(result.strip().split("\n")[1:-1])
        reparsed = yaml.safe_load(yaml_body)
        self.assertEqual(reparsed, fm)

    def test_yaml_hostile_value_raises(self):
        # A leading dash makes YAML interpret the value as a list item
        with self.assertRaises(ValueError):
            plugin_generator.format_frontmatter(
                {"name": "test", "description": "- starts with dash"}
            )

    def test_colon_space_in_value_raises(self):
        # ` : ` in the middle of a value would be parsed as a YAML mapping
        with self.assertRaises(ValueError):
            plugin_generator.format_frontmatter(
                {"name": "test", "description": "key : value inside"}
            )


if __name__ == "__main__":
    unittest.main()
