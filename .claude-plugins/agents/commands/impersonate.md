---
description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation from Claude Code.

Command forms:

```text
/agents:impersonate start <agent-id-or-flags>
/agents:impersonate status
/agents:impersonate sync
/agents:impersonate stop
```

## Instructions

1. **Check the installed CLI version first**:
   ```
   archagent --version
   ```
   If the command is missing, or the version is older than `0.3.1`, tell the user to run `/cli:install`.

2. **Interpret the first argument** from `$ARGUMENTS` as the action. Supported actions are:
   - `start`
   - `status`
   - `sync`
   - `stop`

3. **Dispatch to the matching CLI command**:
   - `start`:
     ```
     archagent impersonate start <remaining-arguments>
     ```
     Then:
     ```
     archagent impersonate status --json
     ```
     Read the returned `identity_file`, adopt that identity for the current Claude Code session, and report the active agent, app, state file, and identity file.
   - `status`:
     ```
     archagent impersonate status --json
     ```
     Summarize whether impersonation is active. If active, report the agent name and ID, app ID, scope, tool count, skill count, state file path, identity file path, and timestamps.
   - `sync`:
     ```
     archagent impersonate sync <remaining-arguments>
     ```
     Then:
     ```
     archagent impersonate status --json
     ```
     Re-read the `identity_file`, re-adopt the refreshed identity, and summarize visible changes.
   - `stop`:
     ```
     archagent impersonate stop <remaining-arguments>
     ```
     Confirm that local impersonation state was removed and drop any impersonated identity from the current session.

4. **If the action is missing or unsupported**, explain the supported forms and show the command syntax.

5. **If authentication or app selection fails**, tell the user to run `/cli:auth` or provide `--app <id>`.
