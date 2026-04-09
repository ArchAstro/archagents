---
name: impersonate
description: Use when the user wants to impersonate an ArchAgent, asks about the active impersonation state, wants to refresh or stop impersonation, or refers to working as a specific ArchAgent inside Claude Code. Trigger phrases include "impersonate agent", "act as this agent", "be this agent", "start impersonation", "sync impersonation", "stop impersonation", "what agent am I impersonating", and "use the active agent identity".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation through the ArchAgent CLI and keep the Claude Code session aligned with the active identity file.

This skill assumes the ArchAgent CLI is already installed and authenticated. Use the `/archagents:install` and `/archagents:auth` commands in this same plugin instead of trying to install or authenticate the CLI manually inside this skill.

## Core Workflow

1. Ensure the CLI layer is ready:
   - If the `archagent` command is missing, or the installed version is older than `0.3.1`, direct the user to `/archagents:install`.
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
