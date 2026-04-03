# Shared ArchAgent CLI Authentication Workflow

Authenticate the user with the ArchAstro developer platform via browser-based login.

## Workflow

1. Check the installed CLI version first:
   ```
   archagent --version
   ```
   If the command is missing, or the version is older than `0.3.1`, route to the harness-specific CLI install flow.

2. Check whether the user is already authenticated:
   ```
   archagent auth status
   ```
   If the user is already authenticated, show their status and ask whether they want to re-authenticate.

3. Reset any stale settings overrides that may point to localhost:
   ```
   archagent settings reset
   ```
   This ensures the CLI uses the production URLs.

4. Start the login flow:
   ```
   archagent auth login
   ```
   Keep the session responsive while the browser-based auth flow runs.

5. Tell the user the auth flow is running and they should complete login in their browser. The CLI opens `https://developers.archastro.ai` and prints a URL if the browser does not open automatically.

6. When the user says they have logged in, or when it is time to re-check, wait for the login command to finish and then run:
   ```
   archagent auth status
   ```

7. On failure, show the error and suggest:
   - Check their internet connection.
   - Try `archagent settings reset` if URLs look wrong.
   - Try again with `archagent auth login`.
