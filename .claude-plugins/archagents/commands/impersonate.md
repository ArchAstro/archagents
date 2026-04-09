---
description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation from Claude Code and keep the current session aligned with the active identity file.

Command aliases:

```text
/archagents:impersonate start <agent-id-or-flags>
/archagents:impersonate status
/archagents:impersonate sync
/archagents:impersonate stop
```

## Core Workflow

1. Ensure the CLI layer is ready:
   - Read `plugin-compatibility.json` from the plugin root. Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
   - Run `archagent --version`. If missing or older than the resolved minimum, direct the user to `/archagents:install`.
   - If authentication or app selection is missing, direct the user to `/archagents:auth`.

2. Check the current impersonation state:
   ```
   archagent impersonate status --json
   ```

3. If the user wants to start impersonation and none is active:
   - run:
     ```
     archagent impersonate start <agent-or-flags>
     ```
   - then re-run:
     ```
     archagent impersonate status --json
     ```

4. If impersonation is active, read the `identity_file` from the returned state and adopt that identity for the current session while retaining your normal capabilities.

5. If the user wants to refresh impersonation:
   ```
   archagent impersonate sync
   ```
   Then re-run `archagent impersonate status --json` and re-read the identity file.

6. If the user wants to stop impersonation:
   ```
   archagent impersonate stop
   ```
   Then drop the impersonated identity from the current session.

## Response Expectations

- When impersonation is active, report the active agent, app, scope, and local file locations.
- When inactive, say so explicitly.
- If the CLI is missing or too old, route the user to `/archagents:install`.
- If auth or app selection is missing, route the user to `/archagents:auth` or supply `--app <id>`.
- Do not inspect or edit credential files directly. Use the CLI only.
