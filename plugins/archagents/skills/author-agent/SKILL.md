---
name: author-agent
description: Use when the user wants to create or edit an ArchAstro agent's config files before deployment, including AgentTemplate files, Script configs, custom tools, routines, and environment setup. Trigger phrases include "build this agent", "write the template", "create the scripts", "set up the routines", "author this agent config".
allowed-tools: ["Bash(archagent:*)"]
---

# Agent Authoring for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/archagents/author-agent.md`](../../../../shared/skills/archagents/author-agent.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
