# ArchAstro

The default ArchAstro project concierge. Answers project and
account-maintenance questions on direct user messages, lists peer
agents in the org, hands off to a specialist when one is a better
owner, and escalates to a human (Slack or email) when nothing else
fits.

The ArchAgents onboarding and setup skill bundle lives in
[ArchAstro Onboarding](../archastro-onboarding).

## How it triggers

The agent runs a `participate` routine and joins any thread it is
added to. Start a session with:

```bash
archagent create agentsession --agent archastro --wait
```

## Deploy

```bash
archagent install agentsample archastro
```

No required env vars. To enable Slack or email escalation, set
`CONCIERGE_ESCALATION_CHANNEL` and `CONCIERGE_ESCALATION_EMAIL` in
the agent's "Finish setup" panel and install the Slack bot.

## Identity

```text
You are ArchAstro, the default concierge for this project.

On every turn, decide fast: answer directly, hand off to a specialist, or
escalate.
```

## Concierge Tools

- `org_overview` lists peer agents in the org.
- `describe_agent` profiles one peer agent by handle.
- `handoff` relays a user message to a specialist agent's Slack-routed thread.
- `escalate` posts to `CONCIERGE_ESCALATION_CHANNEL` and optionally emails
  `CONCIERGE_ESCALATION_EMAIL`.

## Environment

`CONCIERGE_ESCALATION_CHANNEL` is required only if you want the `escalate` tool
to post human escalations. `CONCIERGE_ESCALATION_EMAIL` is optional.

## Files

```
archastro/
|-- README.md
|-- agent.yaml
|-- env.example
|-- scripts/
|   |-- concierge-handoff.aascript
|   |-- describe-agent.aascript
|   |-- escalate.aascript
|   `-- org-overview.aascript
`-- sample.yaml
```
