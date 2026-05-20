# Daily Dependency Scan

Scan all monitored repos for vulnerable dependencies and triage

Standalone routine. Attach to any existing agent in your org to schedule it on that agent's cadence.

## Setup

- **`GITHUB_TOKEN`** — GitHub token used by the scanning tools this routine calls. A
- **`MONITORED_REPOS`** — Comma-separated `owner/repo` list to scan daily.
- **Install `integration/github`** — Install the ArchAstro GitHub App on every repo in MONITORED_REPOS
- **Verify the bot can read every monitored repo** — Iterates `MONITORED_REPOS` and hits each repo's
