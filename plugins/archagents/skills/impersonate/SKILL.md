---
name: impersonate
description: Use when the user wants to impersonate an ArchAgent, asks about the active impersonation state, wants to refresh or stop impersonation, or refers to working as a specific ArchAgent inside Codex. Trigger phrases include "impersonate agent", "act as this agent", "be this agent", "start impersonation", "sync impersonation", "stop impersonation", "what agent am I impersonating", and "use the active agent identity".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent Impersonation

Manage ArchAgent impersonation through the ArchAgent CLI and keep the Codex session aligned with the active identity file.

This skill assumes the ArchAgent CLI is already installed and authenticated. Install or upgrade `archagent` if missing, and run `archagent auth login` if not authenticated.

## Core Workflow

1. Ensure the CLI layer is ready:
   - Read `plugin-compatibility.json` from the plugin root. Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
   - Run `archagent --version`. If missing or older than the resolved minimum, instruct the user to install or upgrade `archagent`.
   - If authentication or app selection is missing, instruct the user to run `archagent auth login`.

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
- If the CLI is missing or too old, instruct the user to install or upgrade `archagent`.
- If auth or app selection is missing, instruct the user to run `archagent auth login` or supply `--app <id>`.
- Do not inspect or edit credential files directly. Use the CLI only.
