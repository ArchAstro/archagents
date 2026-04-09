---
name: impersonate
description: Use when the user wants to impersonate an ArchAgent, asks about the active impersonation state, wants to refresh or stop impersonation, or refers to working as a specific ArchAgent inside Codex. Trigger phrases include "impersonate agent", "act as this agent", "be this agent", "start impersonation", "sync impersonation", "stop impersonation", "what agent am I impersonating", and "use the active agent identity".
allowed-tools: ["Bash(archagent:*)"]
---

# Impersonate for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/archagents/impersonate.md`](../../../../shared/skills/archagents/impersonate.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection fails, have the user authenticate `archagent` or provide `--app <id>` before continuing.
