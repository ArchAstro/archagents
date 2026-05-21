# ArchAstro

The default ArchAstro project concierge.

This template is based on the production ArchAstro concierge. It helps users
understand and operate their ArchAstro project, keeps account-maintenance
questions moving, checks what peer agents exist in the org, and hands off or
escalates when another agent or a human is the better owner.

The ArchAgents onboarding and setup skill bundle lives in
[ArchAstro Onboarding](../archastro-onboarding).

## Deploy

```bash
archagent install agentsample archastro
```

The agent works out of the box. If you want the `escalate` tool to
post to Slack or email, open the agent in the developer portal and
resolve the optional entries in its "Finish setup" panel
(`CONCIERGE_ESCALATION_CHANNEL`, `CONCIERGE_ESCALATION_EMAIL`, and the
Slack bot install).

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
