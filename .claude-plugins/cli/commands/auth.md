---
description: Authenticate with the ArchAstro developer platform
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAgent CLI Authentication

Authenticate the user with the ArchAstro developer platform via browser-based login.

## Instructions

1. **Check the installed CLI version first**:
   ```
   archagent --version
   ```
   If the command is missing, or the version is older than `0.3.1`, tell the user to run `/cli:install`.

2. **Check if already authenticated**:
   ```
   archagent auth status
   ```
   If the user is already authenticated, show their status and ask if they want to re-authenticate.

3. **Reset any stale settings overrides** that may point to localhost:
   ```
   archagent settings reset
   ```
   This ensures the CLI uses the production URLs.

4. **Start the login flow**:
   ```
   archagent auth login
   ```
   Use `run_in_background: true` so the browser-based auth flow runs while you remain responsive.

   The CLI will open the user's browser to https://developers.archastro.ai for authentication and print a URL in case the browser doesn't open automatically.

5. **Tell the user** the auth flow is running and they should complete login in their browser. Let them know you're available to keep working on other things while waiting.

6. **When the user says they've logged in** (or you're ready to check), wait for the command to finish and then re-check status.

7. **On success**, confirm authentication succeeded and show their status:
   ```
   archagent auth status
   ```

8. **On failure**, show the error and suggest:
   - Check their internet connection
   - Try `archagent settings reset` if URLs look wrong
   - Try again with `archagent auth login`
