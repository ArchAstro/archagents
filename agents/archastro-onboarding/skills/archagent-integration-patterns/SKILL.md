---
name: archagent-integration-patterns
description: Reference patterns for the most common ArchAgents integrations — GitHub webhook, Slack bot, scheduled cron, inbound webhook, knowledge ingestion, cross-company collaboration. Use when the customer describes a trigger-shaped integration ("fire when a PR opens", "post to Slack every Monday", "react to our webhook") and needs to know which event type, installation, and handler to wire up.
---

# Integration Patterns

Most customer integrations collapse to one of seven shapes. When a
customer describes what they want, map it to the closest pattern below
and produce the minimal `agent.yaml` snippet. Then load the deeper
skill (`archagent-author-agent`, `archagent-build-script`, `archagent-build-workflow`) to fill in
details.

## Pattern 1 — GitHub PR review

**Use when**: customer wants to review PRs, triage issues, or react to
pushes.

```yaml
installations:
  - kind: integration/github
    config: {}

routines:
  - name: review-prs
    handler_type: preset
    preset_name: do_task
    event_type: webhook.github_app.pull_request
    event_config:
      webhook.github_app.pull_request:
        filters: {}
    status: active
```

**Critical**: GitHub sends multiple events per PR. Enforce
`action in {"opened", "synchronize"}` filter or in the identity
prompt, otherwise the agent reviews the same PR N times.

Reference sample: `agents/code-review-agent` in this repo.

## Pattern 2 — Slack bot

**Use when**: the customer's users should talk to the agent in Slack.

Install the Slack app installation. The simplest shape uses
`thread.session.join` + the `participate` preset — Slack messages get
proxied into threads automatically.

```yaml
installations:
  - kind: archastro/thread
    config: {}
  - kind: integration/slack
    config: {}

routines:
  - name: participate-slack
    handler_type: preset
    preset_name: participate
    event_type: thread.session.join
    event_config:
      thread.session.join:
        filters: {}
```

To post outbound (from scripts/workflows), use the `slack` script
namespace: `let slack = import("slack"); unwrap(slack.post_message(...))`.

## Pattern 3 — Scheduled job

**Use when**: "run every Monday at 9am", "check this feed every hour".

```yaml
routines:
  - name: weekly-digest
    handler_type: preset
    preset_name: do_task
    event_type: schedule.cron
    schedule: "0 9 * * 1"
    event_config:
      schedule.cron:
        filters: {}
```

**Critical**: both `schedule` (at routine level) and
`event_type: schedule.cron` are required. Do not nest the schedule
under `event_config` — it will not fire.

## Pattern 4 — Inbound webhook

**Use when**: an external system should POST into the agent.

```yaml
routines:
  - name: react-to-webhook
    handler_type: script
    config_ref: webhook-handler-script
    event_type: webhook.inbound
    event_config:
      webhook.inbound:
        filters: {}
```

Back it with a Script that reads `$` (the webhook payload) and makes
decisions. For multi-step handling, wrap it in a WorkflowGraph and
reference via `handler_type: workflow_graph` instead.

## Pattern 5 — Knowledge-grounded agent

**Use when**: the customer wants the agent to answer questions from
their docs, PDFs, or internal wikis.

```yaml
installations:
  - kind: archastro/files
    config: {}

tools:
  - kind: builtin
    builtin_tool_key: knowledge_search
    status: active
```

Upload files via `archagent create files` and attach as ingestion
sources to the `archastro/files` installation. The agent searches via
`knowledge_search` at runtime.

Reference sample: `agents/onboarding-qa` in this repo.

## Pattern 6 — Memory-capable agent

**Use when**: the agent should remember users, preferences, history
across sessions.

```yaml
installations:
  - kind: memory/long-term
    config: {}

tools:
  - kind: builtin
    builtin_tool_key: long_term_memory
    status: active

routines:
  - name: capture-memories
    handler_type: preset
    preset_name: auto_memory_capture
    event_type: thread.session.leave
    event_config:
      thread.session.leave:
        filters:
          subject_is_agent: true
```

The `auto_memory_capture` preset is the easiest path — the agent
summarizes sessions as it leaves and stores them automatically.

## Pattern 7 — Cross-company collaboration

**Use when**: the customer's agent needs to coordinate with another
company's agent in a shared thread.

Requires coordination with ArchAstro to set up shared teams and
trust. Start by reading the Agent Network docs (link via
`archagent-docs-map`) and then email `hi@archastro.ai` to provision.
Do not try to route around this — cross-company sharing is an
intentionally gated feature.

## Composing patterns

Real agents usually combine 2–4 patterns. A GitHub review agent that
also answers questions in Slack is Pattern 1 + Pattern 2. A scheduled
digest that pulls from ingested knowledge is Pattern 3 + Pattern 5.
Always add Pattern 6 (memory) unless there is a specific reason not
to — memory is what makes agents feel continuous.

## What NOT to do

- Do not use an automation where a routine will do. Start agent-scoped.
- Do not author a custom tool when a builtin exists. Check
  `archagent list tools` (or the builtin-tools reference) first.
- Do not build a Workflow when a single Script suffices. Workflows
  are for branching + approvals + retries, not for "I have two API
  calls".
- Do not hard-code secrets in scripts. Use env vars: org-scoped first
  (`archagent create orgenvvar`), app-scoped only when required.
