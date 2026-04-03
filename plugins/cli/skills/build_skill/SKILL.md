---
name: build_skill
description: Use when the user wants to create, edit, or publish an ArchAstro skill — a reusable package of instructions and supporting files that agents can use. Trigger phrases include "build a skill", "create a skill", "write a skill", "author a skill", "new skill", "skill template", "SKILL.md".
allowed-tools: ["Bash(archagent:*)"]
---

# Build Skill for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/cli/build_skill.md`](../../../../shared/skills/cli/build_skill.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
