---
name: manage-configs
description: Use when the user wants to set up or manage local config files for an ArchAstro project — initialize a configs directory, edit configs locally, sync from the server, or deploy local changes. Trigger phrases include "set up configs", "init configs", "configs directory", "sync configs", "deploy configs", "edit config locally", "local config management".
allowed-tools: ["Bash(archagent:*)"]
---

# Local Configs for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/archagents/manage-configs.md`](../../../../shared/skills/archagents/manage-configs.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
