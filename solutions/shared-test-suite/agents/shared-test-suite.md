# Test Reporter

The Test Reporter is the artifact-producing half of the Shared Test Suite
Solution. It listens for `webhook.external.test_run` and writes a Markdown
record for each run plus a `latest` report for the suite.

## Inputs

The triggering payload supplies `suite_id`, `run_id`, overall conclusion,
counts, result rows, a CI URL, and the internal `team_id`. See
[the GitHub Actions guide](../docs/github-actions.md) for the full contract.

## Run modes

- **suite** — a complete suite execution.
- **single** — one selected test.
- **batch** — a selected subset of a suite.
- **ad-hoc** — arbitrary tests without a formal suite.

Artifact names avoid path separators so they remain portable through the
artifact store. Examples:

- `tests-stripe-paper-run-123456.md`
- `tests-stripe-paper-run-123456-invoice_void.md`
- `tests-stripe-paper-latest.md`

## Install note

Importing the Solution publishes this template. Provision a dedicated agent
from it, add that agent only to the chosen internal team, and set **Test
Ingest** to run as that agent. Because the signed payload supplies `team_id`,
this single team membership acts as the destination allowlist. The agent must
be a team member to read and post to the team-owned `tests:<suite_id>` thread.
