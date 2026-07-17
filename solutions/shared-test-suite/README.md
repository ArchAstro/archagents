# Shared Test Suite

Turn automated CI results into an internal shared test channel. This Solution
accepts signed `test_run` webhooks, posts a deterministic summary to one
team-owned thread per suite, and has a reporter agent generate a Markdown run
artifact.

```text
GitHub Actions → generic webhook → Test Ingest automation → tests:<suite_id>
                                      └→ Test Reporter agent → run artifact
```

## Included components

- `custom_objects/` — `TestSuite`, `Test`, `TestRun`, and `TestResult`
  schemas for structured suite/run history.
- `workflows/test-ingest-workflow.yaml` — mode resolution, internal thread
  routing, summary posting, and best-effort object writes.
- `automations/test-ingest.yaml` — trigger automation for
  `webhook.external.test_run`.
- `agents/shared-test-suite.yaml` — agent template for mode-aware Markdown
  artifact reports.

## Validate and package

```sh
archastro validate solution .
archastro package solution .
```

## Install checklist

1. Import this Solution.
2. Provision a dedicated agent from **Test Reporter**.
3. Add it only to the one internal team that will own test threads. The signed
   payload supplies `team_id`, so this membership is the destination allowlist.
4. Configure **Test Ingest** to run as that agent.
5. Create a signed generic webhook, then add the URL, secret, and team ID to
   your GitHub repository secrets.
6. Add the GitHub Actions step from [docs/github-actions.md](docs/github-actions.md).

See [the catalog guide](docs/github-actions.md) for the webhook payload,
GitHub Actions example, and mode/routing rules.

## Current limitations

- Custom-object writes are best effort until the agent-created team
  custom-object authorization fix is available in the platform.
- Artifact creation is agent-routine driven; deterministic workflow thread
  messages are the reliable immediate signal.
- The package is internal-first. Sharing a network team is a deliberate later
  policy decision, not an install default. Do not reuse one reporter across
  multiple destination teams while `team_id` is payload-supplied.
