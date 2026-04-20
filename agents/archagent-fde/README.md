# ArchAgents FDE (Forward Deployed Engineer)

> 🧑‍💻 **The engineer who sits with your developer and gets their agent live —
> except they scale, because they're an agent.**

The ArchAgents pitch is "hiring another FDE doesn't scale. One agent per
customer does." This sample is the pitch embodied. Every customer adopting
ArchAgents gets their own FDE agent that knows the platform cold and walks
them from "we have an integration problem" to "our agent is live" without
stalling, guessing, or handing them the docs site.

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the ArchAgents FDE agent from this repo.

1) Read agents/archagent-fde/agent.yaml and agents/archagent-fde/env.example
2) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
3) Run: archagent auth login <my-email> && archagent init
4) Deploy: cd agents/archagent-fde && ./deploy.sh
5) Start an FDE thread:
     archagent create agentsession \
       --agent archagent-fde \
       --instructions "Help me deploy my first agent." \
       --wait
6) Show me the result
```

## What this agent is

A Forward Deployed Engineer for ArchAgents. It:

- Runs a **seven-phase engagement playbook** (discovery → architecture →
  scaffolding → custom logic → knowledge/memory → deploy → handoff)
- Cites **live docs** via `fetch_archagents_docs` instead of paraphrasing
  from memory
- Teaches the **ArchAgents vocabulary** precisely (AgentTemplate vs Agent,
  Routine vs Automation, Script vs Workflow, Tool vs Skill…)
- Produces **working YAML and `.aascript` files**, not pseudocode
- **Persists engagement memory** across sessions — the next thread resumes
  in context
- Can be **impersonated into Claude Code, Codex, or OpenCode** so the
  customer's own coding harness becomes an ArchAgents FDE

## The bundle

Fifteen skills ship with the agent. Ten are canonical ArchAgents CLI
workflows (copied from `plugins/archagents/skills/`). Five are FDE-layer
skills written specifically for this agent.

### ArchAgents CLI skills

| Skill | Purpose |
|---|---|
| `archagent-install` | Install or upgrade the `archagent` binary |
| `archagent-auth` | Authenticate the CLI with the platform |
| `archagent-manage-configs` | Set up and sync the `configs/` directory |
| `archagent-author-agent` | Author AgentTemplate and Script configs |
| `archagent-build-script` | Write, validate, test, and deploy `.aascript` files |
| `archagent-build-workflow` | Author `WorkflowGraph` JSON configs for multi-step flows |
| `archagent-build-skill` | Create reusable `SKILL.md` bundles |
| `archagent-deploy-agent` | Deploy an agent from a YAML template |
| `archagent-chat` | Send messages and inspect agent responses |
| `archagent-impersonate` | Install this agent's skill set into Claude Code / Codex / OpenCode |

### FDE-layer skills

| Skill | Purpose |
|---|---|
| `archagent-fde-engagement-playbook` | The end-to-end phase-by-phase engagement playbook |
| `archagent-concepts` | One-line canonical reference for every platform concept |
| `archagent-docs-map` | Curated index of the most useful docs URLs |
| `archagent-integration-patterns` | Seven trigger/handler shapes that cover most integrations |
| `archagent-troubleshooting` | Debug broken agents, scripts, routines, memory, configs |

## The one custom tool

- **`fetch_archagents_docs`** — fetch a docs.archagents.com page as
  Markdown. Pass a path like `/docs/start-here/getting-started`, a full
  URL, or `"llms-full.txt"` for the full machine-readable index.

Everything else is builtin tools: `skills`, `knowledge_search`,
`long_term_memory`, `search`.

## Setup

```bash
# The FDE has no required env vars. .env is optional.
cp env.example .env   # optional

# Deploy scripts + agent + all 15 skills
./deploy.sh
```

## Using the FDE

### In a thread (the normal path)

```bash
archagent create agentsession \
  --agent archagent-fde \
  --instructions "Help me build an agent that reviews PRs on acme/api." \
  --wait
```

The FDE runs the engagement playbook. See
[examples/first-engagement.md](examples/first-engagement.md) for a full
transcript.

### Impersonated into your coding harness (the power move)

```bash
archagent impersonate start archagent-fde
archagent impersonate install skill <skill-id> --harness claude
```

Your Claude Code / Codex / OpenCode now has the FDE's 15 skills locally.
See [examples/impersonate-into-claude-code.md](examples/impersonate-into-claude-code.md).

## Customization

### Specialize for a specific customer

The FDE is generic by design. For a specific engagement, fork the YAML
and add customer context to the `identity` block — their stack, their
integration surface, their victory condition. The bundled skills stay
the same; only the identity changes.

### Add a customer-specific skill

When an engagement produces repeatable steps that don't fit the generic
playbook, author a new skill (load the `archagent-build-skill` skill for the
authoring flow), drop it in `skills/<slug>/SKILL.md`, re-run
`./deploy.sh`, and the FDE picks it up on the next session.

### Different model

```bash
archagent update agents archagent-fde --default-model openrouter/anthropic/claude-opus-latest
```

Claude Opus is recommended for FDE work — the reasoning cost matters more
than the token cost when the output is production code and customer
commitments.

## What this demonstrates

- **Skill bundles** — 15 skills shipped in-tree, deployed via `archagent
  create skill`
- **Engagement memory** — `long_term_memory` as the spine of
  cross-session continuity
- **Docs-grounded answers** — a single custom Script tool for live docs
  fetch instead of heavy scraping or stale caches
- **Impersonation as a distribution channel** — the same agent that
  lives on the platform becomes a CLI skill-pack via
  `archagent impersonate install skill --harness ...`
- **The FDE motion encoded as software** — discovery, architecture,
  scaffold, build, deploy, handoff: repeatable, reviewable, transferable

## Files

```
archagent-fde/
├── README.md                                      # this file
├── agent.yaml                                     # AgentTemplate
├── env.example                                    # (optional) env vars
├── deploy.sh                                      # scripts + agent + skills
├── scripts/
│   └── fde-fetch-archagents-docs.aascript        # docs-fetch tool
├── skills/
│   ├── archagent-fde-engagement-playbook/SKILL.md  # FDE playbook
│   ├── archagent-concepts/SKILL.md                 # concept reference
│   ├── archagent-docs-map/SKILL.md                 # curated doc URLs
│   ├── archagent-integration-patterns/SKILL.md     # 7 trigger/handler shapes
│   ├── archagent-troubleshooting/SKILL.md          # debugging playbook
│   ├── archagent-install/SKILL.md                  # ArchAgent CLI skills
│   ├── archagent-auth/SKILL.md
│   ├── archagent-manage-configs/SKILL.md
│   ├── archagent-author-agent/SKILL.md
│   ├── archagent-build-script/SKILL.md
│   ├── archagent-build-workflow/SKILL.md
│   ├── archagent-build-skill/SKILL.md
│   ├── archagent-deploy-agent/SKILL.md
│   ├── archagent-chat/SKILL.md
│   └── archagent-impersonate/SKILL.md
└── examples/
    ├── first-engagement.md                       # full engagement transcript
    └── impersonate-into-claude-code.md           # impersonation walkthrough
```
