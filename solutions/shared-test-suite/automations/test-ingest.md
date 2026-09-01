# Test Ingest

Test Ingest is a trigger automation for `webhook.external.test_run`. It runs
the deterministic `test-ingest-workflow` before the reporter agent has to
interpret the payload.

## What it does

1. Resolves a run mode: `suite`, `single`, `batch`, or `ad-hoc`.
2. Uses `team_id` from the payload to ensure an internal team thread.
3. Routes every run with a `suite_id` to `tests:<suite_id>`, including
   single-test and batch runs, so each suite has one chronological channel.
4. Posts a concise result summary and failure list.
5. Best-effort upserts `TestRun` and `TestResult` custom objects.

## Required post-install binding

A Solution import cannot provision a runtime agent or choose a team. After
installing the Test Reporter template:

```sh
archastro update automation shared-test-suite-ingest \
  --run-as-agent <test-reporter-agent-id>
```

Add the dedicated reporter agent only to the team whose ID GitHub Actions
sends as `team_id`. Because the signed payload selects the destination, this
single membership is the allowlist. Without both bindings, the automation
cannot access the internal team thread; do not reuse the reporter across
multiple destination teams.

## Visibility model

This sample is internal-first. Do not send a partner/network team ID until
both organizations agree on membership and incident-notification behavior.
