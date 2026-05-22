# Platform Health Agent Sample

Daily report on your repo's health, GitHub event alerts, and a 5xx
digest from production logs — all delivered to one Slack channel.
Five routines (two cron, one webhook, two thread-listeners) fan into
a single agent.

## Architecture

![Architecture overview](diagrams/architecture.svg)

Each routine emits a prompt into a dedicated thread
(`health-reports` at 09:05 UTC, `health-alerts` on GitHub webhooks,
`5xx-digest` at 14:30 UTC). The agent responds in-thread; a delivery
routine strips `<thought>`/`<thinking>`/`<summary>` blocks and
forwards the response to `SLACK_OUTPUT_CHANNEL`. A capture routine
persists the agent's `<summary>` trailer for next-run continuity.

## Install

```sh
archagent install agentsample platform-health-agent-sample
```

## Required env vars

| Variable | Required | What it is |
|---|---|---|
| `GITHUB_TOKEN` | Required | Fine-grained PAT (or classic `repo` token) the scripts use to read issues, PRs, and PR comments. The sample writes to GitHub via the GitHub App, not this PAT. Recommended scopes: Issues: read, Pull requests: read, Metadata: read. |
| `MONITORED_REPO` | Required | `owner/name` of the repo to monitor. Webhook events from other repos are silently ignored. |
| `SLACK_OUTPUT_CHANNEL` | Required | Slack channel for the daily report, event alerts, and 5xx digest. Include the leading `#`. |
| `GCLOUD_PROJECT_ID` | Required | GCP project hosting the K8s cluster whose logs to scan. |
| `LOG_NAMESPACE` | Required | K8s namespace for the 5xx digest's `severity>=ERROR` query. |
| `LOG_CONTAINERS` | Optional but recommended | Comma-separated K8s container names to scope the 5xx digest to (e.g. `app,admin-app`). Without it, sidecars at ERROR severity often dominate the digest. |
| `GCLOUD_SA_CLIENT_EMAIL` | Required | Service account email. SA needs `roles/logging.viewer`. |
| `GCLOUD_SA_PRIVATE_KEY` | Required | Service account private key (PEM). Escape newlines as `\n`. |

## Bundle layout

- `agents/platform-health-agent-sample.yaml` — the agent config
- `solution.yaml` — catalog metadata
- `routines/` — five routines: `daily-health-report` (cron 09:05 UTC), `5xx-daily-digest` (cron 14:30 UTC), `github-event-alert` (webhook), and two thread-listeners (`deliver-to-slack`, `capture-summary`)
- `scripts/` — five scripts: `ph-health-report-prompt`, `ph-5xx-digest`, `ph-github-event-alert`, `ph-deliver` (Slack output filter), `ph-capture` (memory persistence)
- `examples/` — sample Slack outputs: `daily-report.md`, `5xx-digest.md`, `github-event-alert.md`
- `env.example` — required env vars (see above)

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/platform-health-agent-sample
```
