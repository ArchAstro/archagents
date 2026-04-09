---
name: build-script
description: Use when the user wants to write, test, or deploy an ArchAstro script — custom logic for agent tools, workflow nodes, and routines. Trigger phrases include "build a script", "write a script", "create a script", "test a script", "script syntax", "script reference", "script language".
allowed-tools: ["Bash(archagent:*)"]
---

# Build Script for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/archagents/build-script.md`](../../../../shared/skills/archagents/build-script.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
