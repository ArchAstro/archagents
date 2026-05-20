# Scan Dependencies

Parse a project's lockfile and check every dependency against OSV

Standalone tool. Attach to any existing agent to expand its capabilities.

## Setup

- **`GITHUB_TOKEN`** — GitHub token used to read lockfiles from the target repo. A
- **`DEFAULT_REPO_OWNER`** — Org/user to use when no `owner` argument is provided.
- **`DEFAULT_REPO_NAME`** — Repo name to use when no `repo` argument is provided.
- **Install `integration/github`** — Install the ArchAstro GitHub App so the scanner can read manifests
