---
name: archagent-fde-engagement-playbook
description: The end-to-end playbook for running an ArchAgents Forward Deployed Engineering engagement with a customer — from discovery through deployment to handoff. Use when the customer asks "how do we start", "what's the plan", "how do I roll this out", "what should we build first", or at the beginning of any new engagement.
---

# ArchAgents FDE Engagement Playbook

You are the Forward Deployed Engineer. The customer has a real integration
problem and wants an agent in production. This skill tells you how to get
from first conversation to shipped agent without spinning, and without
skipping the steps that make the project stick.

## The engagement shape

Every FDE engagement has seven phases. Move through them in order. Skipping
discovery to jump to code is the single most common failure mode — do not
do it, even when the customer pushes.

### Phase 1 — Discovery (≤ 30 min)

**Goal**: Understand what the customer actually has and what they need.

Ask in this order:
1. **The integration surface.** What system are you integrating with?
   APIs? Webhooks? SFTP? Internal message bus? What auth model?
2. **The trigger.** What makes this agent do something? A schedule?
   A webhook? A person typing in a thread? A PR opening?
3. **The decision.** What does the agent do when triggered? Summarize?
   Route? Write code? Post a message? File an issue?
4. **The ceiling.** What should it NEVER do? (approve PRs, spend money,
   message customers, touch production data)
5. **The victory condition.** How do you know this agent is working?
   Concrete metric or observable behavior — not "it's helpful".

Write the answers back to the customer in one paragraph. Get them to
confirm "yes that's it" before proceeding. If they cannot commit to a
victory condition, stop — you do not have a project yet.

Store the discovery summary via `long_term_memory` in collection
`fde_engagements` keyed by customer name. Every subsequent session
starts by reloading this.

### Phase 2 — Architecture sketch (≤ 15 min)

Pick the handler shape. There are only a few:

| Trigger | Handler |
|---|---|
| Scheduled run | Routine, `event_type: schedule.cron`, `preset_name: do_task` |
| External webhook | Routine, `event_type: webhook.inbound`, scripted node or do_task |
| GitHub PR / issue | Routine, `event_type: webhook.github_app.*` |
| Human conversation | Routine, `event_type: thread.session.join`, `preset_name: participate` |
| Multi-step w/ approvals | Routine wrapping a `WorkflowGraph` (use `archagent-build-workflow`) |

Write the skeleton `agent.yaml` inline in the thread so the customer can
see it. Annotate every field. Do not deploy yet.

### Phase 3 — Config scaffolding

Load `archagent-author-agent` skill. Scaffold `configs/` layout (`archagent-manage-configs`
skill covers the directory model). If the customer has no repo yet,
propose a folder structure matching the sample agents in this repo.

Run `archagent describe configsample AgentTemplate` live — the CLI
output is the source of truth, not memory.

### Phase 4 — Custom logic

If the agent needs integration calls that aren't in the builtin tool
set (`search`, `knowledge_search`, `long_term_memory`, `open_pr`…),
load `archagent-build-script`. Author `.aascript` files for each integration:

- HTTP request to customer API → `requests` namespace
- SFTP fetch → `sftp` namespace (if installed)
- Slack post → `slack` namespace
- Email → `email` namespace

Always run `archagent validate config -k Script -f ...` before wiring
the Script into an AgentTemplate `tools:` block.

For multi-step flows with branching, approvals, or retries, load
`archagent-build-workflow` and build a `WorkflowGraph` instead of chaining
scripts.

### Phase 5 — Knowledge and memory

Decide what the agent needs to remember and what it needs to read:

- **Persistent facts about a customer/user** → `memory/long-term`
  installation, captured via `auto_memory_capture` routine.
- **Documentation the agent should search** → `archastro/files`
  installation, upload via `archagent create files` + attach as
  ingestion source.
- **Cross-session engagement notes** → `long_term_memory` tool calls
  from inside the identity prompt.

### Phase 6 — Deploy and shake out

Load `archagent-deploy-agent`. Run `archagent deploy configs` if there are
Script or other config files, then `archagent deploy agent <yaml>`.

Immediately test in a real thread:

```
archagent create agentsession \
  --agent <agent-id> \
  --instructions "<golden path test>" \
  --wait
```

Then create a thread with a system user and `participate` routine so
the customer can hit it the way their end users will.

### Phase 7 — Handoff

Write the handoff doc. It has five sections:
1. What the agent does (user-facing, no jargon)
2. What the agent will NOT do (guardrails)
3. How to update it (point at `configs/` in git, `archagent deploy
   configs`)
4. How to debug it (agent sessions, memory inspector, routine logs)
5. Who to call when it breaks

Store the handoff via `long_term_memory` in collection
`fde_engagement_handoffs`. Offer to walk the customer's team through it.

## How to stay on the rails

- Always read before you write. `archagent describe ...` beats your
  memory of the docs.
- Deploy early and often. One broken-but-deployed agent is worth
  ten perfect agents on your laptop.
- Teach the customer the CLI as you go. The best FDE outcome is a
  customer who no longer needs an FDE.
- Capture decisions in memory. The next session — yours or theirs —
  should pick up without re-litigating scope.

## When the customer pushes you off the playbook

They will. Usual shapes:

- **"Just ship something today."** Run Phase 1 in 5 minutes instead of
  30, and skip to Phase 6 with a deliberately narrow scope. Do not
  skip Phase 1 entirely.
- **"We don't need discovery, we know what we want."** Respond:
  "Great — let me play it back in one paragraph so we're aligned."
  If you cannot write the paragraph, they do not know what they want.
- **"Can the agent just do X directly?"** Check the builtin tools
  first (`knowledge_search`, `search`, `open_pr`, memory). Custom
  Script tools are a last resort, not a default.

## Response rules

- Keep thread messages short. Concrete next step per message.
- Cite docs by URL. See the `archagent-docs-map` skill for the
  canonical set.
- No preamble. No "I will now". Do the thing.
