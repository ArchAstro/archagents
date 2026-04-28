# FDE Agent

> A generic Forward Deployed Engineer base agent. Install it, add your
> own docs and knowledge, then specialize the identity for your team.

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the FDE Agent from this repo.

1) Read agents/fde-agent/agent.yaml and agents/fde-agent/env.example
2) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
3) Run: archagent auth login <my-email> && archagent init
4) Deploy: archagent install agentsample fde-agent
5) Start an FDE thread:
     archagent create agentsession \
       --agent fde-agent \
       --instructions "Help me scope my first engagement." \
       --wait
6) Show me the result and the docs/knowledge gaps I should fill next
```

## What this agent is

This is a base Forward Deployed Engineer agent. It is intentionally not
tied to one company, product, or platform. Customers install it, then add:

- product docs
- architecture docs
- API references
- runbooks
- support procedures
- implementation examples
- customer-specific engagement notes

Once those docs are available through knowledge search, the agent uses
them as its source of truth for scoping, implementation planning,
handoff, and follow-up work.

## What it does

- Runs a generic FDE engagement playbook from discovery through handoff
- Searches uploaded knowledge before answering customer-specific
  questions
- Turns ambiguous requests into thin-slice implementation plans
- Produces concrete artifacts such as code, configs, prompts, runbooks,
  rollout checklists, ticket drafts, and test plans
- Captures confirmed decisions and handoff notes in long-term memory
- Participates in customer threads and resumes context across sessions

## The bundle

This sample ships one skill:

| Skill | Purpose |
|---|---|
| `fde-engagement-playbook` | A generic phase-by-phase FDE playbook for discovery, architecture, thin-slice implementation, validation, memory capture, and handoff |

The agent also uses builtin tools: `skills`, `knowledge_search`,
`long_term_memory`, `memory`, and `search`.

## Setup

```bash
# The base FDE has no required env vars.
archagent install agentsample fde-agent
```

## Add customer knowledge

After installing the base agent, ingest customer-specific docs into the
same app and make them available to the agent's files/knowledge
installation. Good first documents are:

- `product-overview.md`
- `architecture.md`
- `api-reference.md`
- `runbooks.md`
- `support-playbook.md`
- `glossary.md`
- `engagement-history.md`

The agent is designed to say when this knowledge is missing instead of
guessing from general background knowledge.

## Specialize the identity

For a customer-specific FDE, fork `agent.yaml` and add a short section to
the `identity` block with:

- the customer or team name
- the primary product or workflow
- systems and repositories it may discuss
- docs it should treat as canonical
- actions it is allowed to take
- actions that require human approval

Keep the generic rules in place. The specialization should add context,
not weaken the safety and grounding behavior.

## Example use

```bash
archagent create agentsession \
  --agent fde-agent \
  --instructions "We want an FDE agent for our support escalation workflow. Help me scope the first shippable version." \
  --wait
```

See [examples/first-thread.md](examples/first-thread.md) for a sample
first engagement.

## What this demonstrates

- **Base agent templates** - a reusable starting point intended to be
  specialized per customer
- **Knowledge-grounded FDE work** - customer docs are the source of truth
- **Long-term engagement memory** - context, decisions, and handoffs
  persist across sessions
- **Skill bundles** - a small playbook shipped with the agent and loaded
  on demand

## Files

```
fde-agent/
|-- README.md
|-- agent.yaml
|-- env.example
|-- sample.yaml
|-- skills/
|   `-- fde-engagement-playbook/SKILL.md
`-- examples/
    `-- first-thread.md
```
