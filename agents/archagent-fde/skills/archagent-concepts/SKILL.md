---
name: archagent-concepts
description: Canonical one-line reference for every ArchAgents concept — AgentTemplate, Agent, Thread, Routine, Automation, Script, Workflow, Skill, Installation, Tool, Config. Use when the customer asks "what is an X", "what's the difference between X and Y", "do I need an automation or a routine", or when you need to ground a design discussion in the platform's vocabulary.
---

# ArchAgents Concept Map

Every FDE conversation eventually hits a concept question. Answer it
with the platform's real vocabulary, not your own paraphrase. When you
are unsure, link the customer to the canonical doc (see the
`archagent-docs-map` skill) rather than inventing a definition.

## Primary nouns

### AgentTemplate
A YAML file with `kind: AgentTemplate` that declaratively defines an
agent's identity, tools, routines, and installations. Version-controlled
in git. Deployed with `archagent deploy agent <file>.yaml`. The source
of truth for what an agent is.

### Agent
A deployed, persistent AI worker created from an AgentTemplate. Has a
name, identity prompt, tools, knowledge, memory, and routines. Lives on
the ArchAgents platform and is addressable across threads, webhooks,
schedules, and API calls.

### Thread
A persistent conversation where human users, system users, and agents
exchange messages over time. Supports multiple participants and
cross-company collaboration. Agents join threads via
`thread.session.join` routines and leave via `thread.session.leave`.

### Routine
An **agent-scoped** event handler. Attached to a specific agent; fires
when a matching event (`schedule.cron`, `webhook.*`,
`thread.session.join`, etc.) occurs. Routines are the primary way an
agent reacts to the world.

### Automation
A **project-scoped** event handler. Same event-and-handler shape as a
routine, but not tied to a single agent. Use for project-wide jobs
(e.g., a webhook that fans out to multiple agents).

### Script
The smallest unit of custom logic. A functional, expression-oriented
language (no loops, no `return` statement) authored in `.aascript`
files. Used as a tool handler, a workflow node handler, or a routine
handler. Authoritative syntax: `archagent describe scriptdocs`.

### Workflow
A directed JSON graph of nodes (`WorkflowGraph` kind) referenced by a
routine when a handler needs branching, approvals, retries, or
multi-step state. Prefer a routine + single script for simple handlers;
reach for a workflow only when you need structure.

### Skill
A file-backed instruction bundle anchored by a `SKILL.md` file with
optional supporting files. Agents invoke skills at runtime via the
`get_skill` tool (listed as `skills` in the tool catalog). Use skills
to keep identity prompts small and load detailed playbooks on demand.

### Installation
The attachment point that enables tools, knowledge sources, and memory
on an agent in one step. Installing the GitHub App installation, for
example, grants GitHub-flavored tools and a scoped token. Common
installations:
- `memory/long-term` — persistent facts across sessions
- `archastro/thread` — live in threads
- `archastro/files` — ingest files as searchable knowledge
- `integration/github` — GitHub App tools and webhooks

### Tool
An action the agent can call during an LLM session. Three kinds:
- **Builtin** — `search`, `knowledge_search`, `long_term_memory`,
  `open_pr`, `skills`, etc. Declared as `kind: builtin`.
- **Custom (script)** — `kind: custom`, `handler_type: script`,
  `config_ref: <script-slug>`. Backed by a Script config.
- **MCP** — tools exposed by an attached MCP server.

### Config
The file-backed, version-controllable representation of any platform
resource: AgentTemplate, Script, WorkflowGraph, Skill, File, etc.
Managed via a local `configs/` directory and deployed with
`archagent deploy configs`.

## Easy confusions

- **Routine vs Automation.** Agent-scoped vs project-scoped. Start with
  routine. Reach for automation when two+ agents need the same handler.
- **Tool vs Skill.** A tool is an action the agent can call. A skill
  is a bundle of instructions the agent reads. Tools do things; skills
  tell the agent how to do things.
- **Script vs Workflow.** One expression vs a graph. Ship a script
  until branching or approvals force you to a workflow.
- **AgentTemplate vs Agent.** The YAML config vs the deployed instance.
  Templates are declarative and reproducible; agents are live and have
  IDs.
- **Installation vs Tool.** An installation is the wiring
  (credentials + capability attach). The tools it exposes are what the
  agent actually calls.

## When a customer asks "which do I want?"

1. **"I want the agent to react to something."** → Routine.
2. **"I want the agent to do something on a schedule."** → Routine with
   `event_type: schedule.cron`.
3. **"I want the agent to live in a Slack / thread conversation."** →
   `archastro/thread` installation + `participate` preset routine.
4. **"I want the agent to call my API."** → Custom tool backed by a
   Script in the `requests` namespace.
5. **"I want the agent to remember things about a user."** →
   `memory/long-term` installation + `auto_memory_capture` routine.
6. **"I want multi-step logic with approvals / branches."** → Workflow.
7. **"I want reusable playbooks the agent loads on demand."** → Skill.
8. **"I want it across customers / companies."** → Agent Network
   (cross-company threads + shared teams).
