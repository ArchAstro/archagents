---
name: archagent-docs-map
description: Curated index of the most useful ArchAgents docs pages, with one-line descriptions. Use when the customer asks for a link, when you need to cite documentation in a thread, or when `fetch_archagents_docs` needs a starting path. Prefer pointing customers at these canonical URLs over paraphrasing from memory.
---

# ArchAgents Docs Map

Linking beats paraphrasing. When a customer asks how something works,
cite the exact doc URL — then summarize in one sentence, not a wall of
text. This skill is the FDE's canonical URL list.

The docs root is `https://docs.archagents.com`. There is also a
machine-readable full index at `https://docs.archagents.com/llms-full.txt`
— pass that URL to `fetch_archagents_docs` when you need an overview.

## Start here (always cite for new customers)

| URL | What it covers |
|-----|----------------|
| `https://archagents.com` | Platform pitch and homepage |
| `https://docs.archagents.com/docs/start-here/getting-started` | Zero-to-one: install, auth, write template, deploy, test |
| `https://docs.archagents.com/docs/start-here/concepts` | Canonical concept reference (Agent, Routine, Script, Workflow, Skill) |
| `https://docs.archagents.com/docs/start-here/cli` | CLI reference for the full terminal workflow |
| `https://docs.archagents.com/llms-full.txt` | Full docs as a single text file — best input for coding agents |

## Build

| URL | What it covers |
|-----|----------------|
| `https://docs.archagents.com/docs/build-agents/agents` | Agent model, routine lifecycle, handler types |
| `https://docs.archagents.com/docs/build-agents/scripts` | Script language reference (syntax, namespaces, validation) |
| `https://docs.archagents.com/docs/build-agents/workflows` | WorkflowGraph node model and authoring |
| `https://docs.archagents.com/docs/build-agents/configs` | Config file management and `configs/` directory layout |
| `https://docs.archagents.com/docs/build-agents/skills` | Authoring SKILL.md bundles |

## Operate

| URL | What it covers |
|-----|----------------|
| `https://docs.archagents.com/docs/operate-agents/installations` | Installation model — tools, knowledge, memory entry point |
| `https://docs.archagents.com/docs/operate-agents/memory` | Long-term memory semantics and inspection |
| `https://docs.archagents.com/docs/operate-agents/knowledge` | Knowledge ingestion and search |
| `https://docs.archagents.com/docs/operate-agents/threads` | Threads, participants, and session lifecycle |

## Collaborate

| URL | What it covers |
|-----|----------------|
| `https://docs.archagents.com/docs/collaborate/agent-network` | Cross-company threads and shared teams |

## Reference

| URL | What it covers |
|-----|----------------|
| `https://docs.archagents.com/docs/reference/events` | Full event-type catalog with payload schemas |
| `https://docs.archagents.com/docs/reference/builtin-tools` | Every builtin tool the agent can be granted |
| `https://docs.archagents.com/docs/reference/script-namespaces` | Script standard library: `requests`, `string`, `array`, `slack`, `email` |

## When to cite which

- **"What IS this platform?"** → homepage + concepts page.
- **"How do I start?"** → getting-started.
- **"What should the YAML look like?"** → build-agents/agents.
- **"How do I write a script?"** → build-agents/scripts + run
  `archagent describe scriptdocs` live.
- **"What events can I listen to?"** → reference/events.
- **"Which builtin tools exist?"** → reference/builtin-tools.
- **"How do my agents talk to another company's agents?"** →
  collaborate/agent-network (and note this requires coordination
  with ArchAstro).

## Recovery

If a URL above 404s, the docs have been restructured. Fall back to
`https://docs.archagents.com/llms-full.txt` via
`fetch_archagents_docs`, grep for the nearest heading, and tell the
customer the canonical index moved. Do not fabricate replacement URLs.
