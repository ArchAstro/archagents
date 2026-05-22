# FDE Agent

> A Forward Deployed Engineer agent that runs a discovery → implementation
> → validation → handoff playbook on customer threads, grounded in your
> project's knowledge base and memory.

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
6) Show me the result
```

## How it triggers

The FDE agent uses a `participate` routine and joins any thread it
is added to. Start a session with:

```bash
archagent create agentsession \
  --agent fde-agent \
  --instructions "Help me scope my first engagement." \
  --wait
```

The agent has no cron routines and is not webhook-triggered.

## What this agent is

An FDE agent for scoped technical engagements — discovery, implementation,
validation, and handoff. The agent works from the project context in the
thread, long-term memory, the knowledge base, and any configured tools and
integrations. Specialize it for a customer by attaching their docs as
knowledge sources; the engagement playbook is generic enough to apply to
most workflows.

## What it does

- Runs an FDE engagement playbook from discovery through handoff
- Searches configured project knowledge before answering project-specific
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
| `fde-engagement-playbook` | A phase-by-phase FDE playbook for discovery, architecture, thin-slice implementation, validation, memory capture, and handoff |

The agent also uses builtin tools: `skills`, `knowledge_search`,
`long_term_memory`, `memory`, and `search`.

## Setup

```bash
# The FDE agent has no required env vars.
archagent install agentsample fde-agent
```

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

- **FDE engagement template** - an operational agent pattern for embedded
  discovery, implementation, and handoff work
- **Knowledge-grounded FDE work** - configured project context is the source of truth
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
