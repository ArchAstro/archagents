---
name: archagent-auth
description: Use when the user wants to authenticate with or log in to the ArchAstro developer platform, or when the CLI reports an authentication error. Trigger phrases include "authenticate archagent", "archagent auth login", "log in to archagent", "log in to archastro", "archagent not authenticated", "archagent auth status", "sign in to archagent".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent CLI Authentication

Authenticate the user with the ArchAstro developer platform via browser-based login.

## Workflow

1. **Check whether the user is already authenticated**:
   ```
   archagent auth status
   ```
   If the user is already authenticated, show their status and ask whether they want to re-authenticate.

2. **Reset any stale settings overrides that may point to localhost**:
   ```
   archagent settings reset
   ```
   This ensures the CLI uses the production URLs.

3. **Start the login flow**:
   ```
   archagent auth login
   ```
   Keep the session responsive while the browser-based auth flow runs.

4. **Tell the user the auth flow is running** and they should complete login in their browser. The CLI opens `https://developers.archastro.ai` and prints a URL if the browser does not open automatically.

5. **When the user says they have logged in**, or when it is time to re-check, wait for the login command to finish and then run:
   ```
   archagent auth status
   ```

6. **On success**, confirm authentication succeeded and show the user their status.

7. **On failure**, show the error and suggest:
   - Check their internet connection.
   - Try `archagent settings reset` if URLs look wrong.
   - Try again with `archagent auth login`.
