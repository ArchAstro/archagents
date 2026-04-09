---
description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation from Claude Code.

Claude command aliases:

```text
/archagents:impersonate start <agent-id-or-flags>
/archagents:impersonate status
/archagents:impersonate sync
/archagents:impersonate stop
```

Shared workflow details:

- [`shared/skills/archagents/impersonate.md`](../../../shared/skills/archagents/impersonate.md)

Claude-specific notes:

- If the CLI is missing or too old, route the user to `/archagents:install`.
- If authentication or app selection fails, route the user to `/archagents:auth` or provide `--app <id>`.
