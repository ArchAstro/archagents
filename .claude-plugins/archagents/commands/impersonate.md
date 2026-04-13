---
description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation (CLI passthrough)

Pass arguments directly to `archagent impersonate`.

```text
/archagents:impersonate start <agent-id-or-flags>
/archagents:impersonate status
/archagents:impersonate sync
/archagents:impersonate stop
/archagents:impersonate list skills
/archagents:impersonate install skill <id> [--harness codex] [--install-scope project]
```

## Instructions

1. Read `plugin-compatibility.json`. Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
2. Run `archagent --version`. If missing or too old, tell the user to run `/archagents:install`.
3. Run:
   ```
   archagent impersonate $ARGUMENTS
   ```
4. If the command was `start` or `sync`, also run `archagent impersonate status --json`, read the `identity_file`, and adopt the identity for the current session.
5. If the command was `stop`, drop any impersonated identity from the current session.
6. If auth or app selection fails, direct the user to `/archagents:auth` or `--app <id>`.
