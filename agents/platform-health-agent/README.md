# Platform Health Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Platform Health Agent from this repo.

1) Read agents/platform-health-agent/agent.yaml and agents/platform-health-agent/env.example
2) Ask me for: GITHUB_TOKEN (PAT with repo scope), MONITORED_REPO (owner/name),
   SLACK_OUTPUT_CHANNEL (e.g. #platform-health), GCLOUD_PROJECT_ID,
   LOG_NAMESPACE, GCLOUD_SA_CLIENT_EMAIL, GCLOUD_SA_PRIVATE_KEY
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key NAME --value VAL (one per env var)
6) Deploy: archagent install agentsample platform-health-agent
7) Install the GitHub App and Slack bot on the agent's installations
8) Test it: create an agent session and ask "What's the state of the queue?"
9) Show me the result
```

> 🩺 **A scheduled monitoring agent that runs your daily standup, alerts on
> GitHub events, and digests production 5xx errors — all to one Slack channel.**

Three signals, one channel:

- **Daily health report** — every morning at 09:05 UTC, a TL;DR + Notable + CI status + open issues grouped by theme + recently-resolved issues + customer-facing ships, posted to Slack.
- **GitHub event alerts** — issues opened/closed/reopened, PRs merged, CI failures. Memory-gated so closure events post a `✅ resolved` only when there was a prior alert; reopens re-escalate; routine noise (P3-Polish, dependency bumps, bot issues) is filtered out.
- **5xx daily digest** — afternoon scan of Cloud Logging for the last 24h of ERROR-severity entries in your platform namespace, grouped by exception class, with per-signature drill-down URLs into the Cloud Logging Console.

## What makes this different

**Thread-mediated architecture.** Every output is generated as an agent response to a prompt posted in a dedicated thread (`health-reports`, `health-alerts`, `5xx-digest`). This gives you:
- **Replay**: every report is a re-runnable thread message, viewable in the portal.
- **Continuity**: the agent appends a `<summary>` block to each response, captured by a separate routine and persisted as next-run context. The daily report knows what was happening yesterday; the 5xx digest knows which signatures are recurring.
- **Slack as a destination, not a transport.** A separate delivery routine forwards thread messages to Slack with `<thought>`/`<thinking>`/`<summary>` stripping and `SKIP:` suppression — so internal agent reasoning never leaks to the channel.

**Memory-gated alerting.** `working_memory_set('alerted_issue_<N>', ...)` on alert; closure events look up the same key. No "PR closed an issue we never alerted on" noise. The corresponding `storage.get` lookup is pre-fetched in the script before the agent runs, so the agent doesn't burn a tool call on it.

**No tool calls during the 5xx digest.** All data — last-24h log entries grouped by signature, recent open issues, recent merged PRs, previous digest summary — is assembled in the prompt-emitter script. The agent's job is only to format the Slack post. Zero tool calls per turn keeps it well under the turn-coordinator timeout.

## Trust model

The sample makes trust assumptions you should verify before deploying:

- **GitHub issue and PR titles from `MONITORED_REPO` flow into agent prompts** (event alerts, daily report, 5xx digest), whose responses are forwarded to Slack. The sample assumes contributors to the monitored repo are trusted. Public repos with anonymous issue creation are outside this model — a crafted title could attempt prompt injection. The anti-interpretation rules in the prompts are LLM-level guards, not deterministic filters.
- **`SLACK_OUTPUT_CHANNEL` audience** sees issue titles, PR titles, exception class signatures, and PR author handles unredacted. Pick a channel whose audience matches.
- **Minimum-privilege tokens.** `GITHUB_TOKEN` — for strict minimum-privilege, use a fine-grained PAT (`github_pat_*`) with read-only access to Issues, Pull requests, and Metadata. A classic `repo`-scoped PAT (`ghp_*`) also works but grants write capability the sample's identity instructs against (the agent has tool-level access to GitHub via `integrations` + `integration/github`; the only thing keeping it read-only is its identity instructions). `GCLOUD_SA_*` needs only `roles/logging.viewer`.

## Setup

```bash
# 1. Set each required env var on your ArchAstro org. The agent's scripts
#    read these at runtime — env.example lists what's needed.
for var in $(grep -oE '^[A-Z_]+' env.example); do
  read -rsp "$var: " value; echo
  archagent create orgenvvar --key "$var" --value "$value"
done

# 2. Deploy
archagent install agentsample platform-health-agent

# 3. Install the GitHub App on the monitored repo and the Slack bot on the
#    output channel. Both are agent installations — see "Post-deploy steps".
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope. Used to read issues, PRs, and PR comments — the sample does not write to GitHub. |
| `MONITORED_REPO` | `owner/name` of the repo to monitor. Webhook events from other repos are silently ignored. |
| `SLACK_OUTPUT_CHANNEL` | Slack channel for delivery. Include the leading `#`. |
| `GCLOUD_PROJECT_ID` | GCP project hosting the K8s cluster whose logs to scan. |
| `LOG_NAMESPACE` | K8s namespace for the 5xx digest's `severity>=ERROR` query. |
| `GCLOUD_SA_CLIENT_EMAIL` | Service account email. SA needs `roles/logging.viewer`. |
| `GCLOUD_SA_PRIVATE_KEY` | Service account private key (PEM). Escape newlines as `\n`. |

## Post-deploy steps

The agent template declares two integrations — the platform creates
empty installation rows on deploy, but you connect each one yourself.

### 1. GitHub App

Find the agent's `integration/github` installation and install the
ArchAstro GitHub App on the monitored repo. Without this, the GitHub
Event Alert routine has nothing to react to.

```bash
archagent describe agent platform-health-agent
# Locate the integration/github installation, follow its install URL
```

### 2. Slack bot

Same process for `integration/slack_bot` — link a Slack workspace and
invite the bot to the output channel.

## Sample output

See `examples/`:

- `daily-report.md` — a typical morning post in the Slack channel
- `5xx-digest.md` — afternoon digest with per-signature drill-downs
- `github-event-alert.md` — alert on a newly-opened P1 issue + the matching `✅ resolved` follow-up

## Customization

This sample is a reference implementation, not a finished product. Most teams will fork it and adapt — the agent identity, prompt structure, schedule, log filter, and event-handling rules are all tuned to one specific monitoring story (a single repo, a single Slack channel, an Elixir-on-K8s production deployment). The sub-sections below are the seams where adaptation is expected.

### Schedule

Edit cron expressions in `agent.yaml`:
- `Daily Health Report Prompt`: default `5 9 * * *` (09:05 UTC daily)
- `5xx Daily Digest`: default `30 14 * * *` (14:30 UTC daily)

Cron is evaluated in UTC. If you want a 9am-local report, factor in the offset — e.g., `5 17 * * *` for 09:05 PT.

### Report structure

The daily report's structure is defined in
`scripts/ph-health-report-prompt.aascript` — TL;DR, Notable, CI Status,
Issues needing attention, Possibly resolved, Customer fixes/ships,
Notable activity. Edit the `base_prompt` variable to add/remove sections
or change conventions.

### Adding a new monitored thread

1. Write a new prompter script that posts to a new thread key via
   `threads.ensure_by_key`.
2. Add a new cron routine in `agent.yaml` referencing that script.
3. If the agent's response should be delivered to Slack, add the new
   thread key to `ph-deliver.aascript`'s `is_allowed` allowlist.
4. If the response includes a `<summary>` block to capture for
   continuity, add the new key to `ph-capture.aascript`'s
   `thread.key` → `storage_key` map.

### Different log filter

Edit `scripts/ph-5xx-digest.aascript`'s `log_filter_for_api` if you
need a different severity floor or resource filter. The matching
`base_filter` (used to build the Console drill-down URLs) lives a
few lines below — keep them in sync.

The signature extractor regex in `signature_for` assumes Elixir's
`** (Module.Submodule.Class)` exception format. If your platform uses
a different convention (Python tracebacks, Java stack traces, Go
panics), edit the regex accordingly — otherwise everything will
bucket under `(non-exception entry)`.

### GitHub event filter

`scripts/ph-github-event-alert.aascript` currently filters on issues
(opened/closed/reopened), PR merges, and CI workflow failures. To
react to other events (releases, deployments, security advisories),
add new branches in the if/else chain that builds `prompt`.

## What this demonstrates

- **Cron-driven prompt-emitter pattern** — script posts to a thread; agent
  participates; delivery script forwards to Slack. One pattern, multiple
  scheduled signals.
- **Webhook event handlers with memory-gated state** — `working_memory_set`
  on alert, closure events read it back, no double-alerting and no
  resolution-without-prior-alert noise.
- **Continuity via `<summary>` capture** — agent emits a structured trailer;
  separate routine extracts it; storage key is read by the next run.
- **Cloud Logging API integration via JWT-bearer SA auth** — sign a JWT,
  exchange for an access token, query `entries:list`. Same pattern as
  the security-triage-agent sample.
- **Defensive output stripping** — `<thought>`/`<thinking>`/`<summary>` blocks
  filtered before Slack delivery; tool-call fragments and bare memory-key
  responses trigger SKIP rather than leak.
- **Multi-routine, multi-script agent** — 7 routines (1 participate,
  2 cron, 1 webhook, 2 thread-listener, 1 auto-memory-capture) sharing
  5 scripts.

## Files

```
platform-health-agent/
├── README.md
├── sample.yaml                       # schema-v2 DSL
├── agent.yaml                        # AgentTemplate
├── env.example
├── scripts/
│   ├── ph-health-report-prompt.aascript  # cron → posts to health-reports thread
│   ├── ph-5xx-digest.aascript            # cron → posts to 5xx-digest thread
│   ├── ph-github-event-alert.aascript    # webhook → posts to health-alerts thread
│   ├── ph-deliver.aascript               # thread.message_added → Slack
│   └── ph-capture.aascript               # thread.message_added → storage
└── examples/
    ├── daily-report.md
    ├── 5xx-digest.md
    └── github-event-alert.md
```
