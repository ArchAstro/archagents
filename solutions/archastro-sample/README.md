# ArchAstro Sample

The default ArchAstro project concierge. Answers project and
account-maintenance questions on direct user messages, lists peer
agents in the org, hands off to a specialist when one is a better
owner, and escalates to a human (Slack or email) when nothing else
fits.

## Architecture

![Architecture overview](diagrams/architecture.svg)

Triggered by user messages in a thread. Each turn the agent decides
whether to answer directly, call `org_overview` / `describe_agent` to
locate a specialist, `handoff` to that specialist's thread, or
`escalate` to `CONCIERGE_ESCALATION_CHANNEL` and optionally
`CONCIERGE_ESCALATION_EMAIL`.

## Install

```sh
archagent install agentsample archastro-sample
```

## Required env vars

| Variable | Required | What it is |
|---|---|---|
| `CONCIERGE_ESCALATION_CHANNEL` | Optional | Slack channel the `escalate` tool posts to. Without it, escalation is logged but not delivered. |
| `CONCIERGE_ESCALATION_EMAIL` | Optional | Email address `escalate` also emails. |

## Bundle layout

- `agents/archastro-sample.yaml` — the agent config
- `solution.yaml` — catalog metadata
- `tools/` — the four concierge tools (`org_overview`, `describe_agent`, `handoff`, `escalate`)
- `scripts/` — implementations of the concierge tools (org-graph queries, escalation delivery)
- `env.example` — optional env vars

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/archastro-sample
```
