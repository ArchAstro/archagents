# ArchAgent Impersonation

Manage ArchAgent impersonation through the ArchAgent CLI and keep the current session aligned with the active identity file.

This workflow depends on the `cli` plugin for CLI installation and authentication. Use the current harness's CLI install and authentication flows instead of handling that setup inline.

## Core Workflow

1. Ensure the CLI layer is ready:
   - If the `archagent` command is missing, or the installed version is older than `0.3.1`, route the user to the current harness's CLI install flow.
   - If authentication or app selection is missing, route the user to the current harness's CLI authentication flow.

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
- If the CLI is missing or too old, route the user to the current harness's CLI install flow.
- If auth or app selection is missing, route the user to the current harness's CLI authentication flow or supply `--app <id>`.
- Do not inspect or edit credential files directly. Use the CLI only.
