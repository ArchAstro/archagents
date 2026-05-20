# PR Security Review

Triggered by GitHub PR webhooks; flag security concerns on opened/updated PRs

Standalone routine. Attach to any existing agent in your org to schedule it on that agent's cadence.

## Setup

- **`GITHUB_TOKEN`** — GitHub token used for any inline read/write the review path
- **Install `integration/github`** — Install the ArchAstro GitHub App on the repos whose PRs should
