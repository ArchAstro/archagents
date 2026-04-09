---
description: Authenticate with the ArchAstro developer platform
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent CLI Authentication

Claude Code wrapper for the shared ArchAgent CLI authentication workflow.

Shared workflow details:

- [`shared/commands/archagents/auth.md`](../../../shared/commands/archagents/auth.md)

Claude-specific notes:

- If the CLI is missing or too old, route the user to `/archagents:install`.
- Keep follow-up guidance in Claude command terms, not Codex skill names.
