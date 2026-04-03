---
description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation from Claude Code.

Claude command aliases:

```text
/agents:impersonate start <agent-id-or-flags>
/agents:impersonate status
/agents:impersonate sync
/agents:impersonate stop
```

Shared workflow details:

- [`shared/skills/agents/impersonate.md`](../../../shared/skills/agents/impersonate.md)

Claude-specific notes:

- If the CLI is missing or too old, route the user to `/cli:install`.
- If authentication or app selection fails, route the user to `/cli:auth` or provide `--app <id>`.
