---
name: deploy-agent
description: Use when the user wants to deploy an ArchAstro agent, turn a config-driven agent repo into a running agent, or get an existing agent running in a thread. Trigger phrases include "deploy agent", "deploy this agent", "set up an agent", "launch agent", "ship this agent", "get this agent running".
allowed-tools: ["Bash(archagent:*)"]
---

# Agent Deploy for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/cli/deploy-agent.md`](../../../../shared/skills/cli/deploy-agent.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
