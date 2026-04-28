# ArchAstro

The default ArchAgents concierge for agent network orgs. This sample is
designed to be preinstalled wherever a team should always have access to an
ArchAgents-native helper that can answer platform questions, troubleshoot
agents, draft configs, and point users at the right docs.

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the ArchAstro concierge agent from this repo.

1) Read agents/archastro/agent.yaml and agents/archastro/env.example
2) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
3) Run: archagent auth login <my-email> && archagent init
4) Deploy: archagent install agentsample archastro
5) Start a thread:
     archagent create agentsession \
       --agent archastro \
       --instructions "Help me understand what I can do in this org." \
       --wait
6) Show me the result
```

## What this agent is

ArchAstro is an ArchAgents support concierge. It:

- answers ArchAgents setup, CLI, config, routine, workflow, and script questions
- cites live docs through `fetch_archagents_docs`
- uses bundled skills before giving platform-specific guidance
- drafts real `agent.yaml` and `.aascript` files when users are ready to build
- troubleshoots failed deploys, routines, scripts, and memory setup
- persists useful org context and handoff notes across sessions
- can be impersonated into Claude Code, Codex, or OpenCode for local support

## The bundle

Fifteen skills ship with the agent. Ten are canonical ArchAgents CLI
workflows copied from `plugins/archagents/skills/`. Five are support-layer
skills that cover platform concepts, docs, integration patterns, engagement
flow, and troubleshooting.

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
| `archagent-impersonate` | Install the agent's skill set into Claude Code / Codex / OpenCode |

### Support skills

| Skill | Purpose |
|---|---|
| `archastro-engagement-playbook` | The end-to-end phase-by-phase engagement playbook |
| `archagent-concepts` | One-line canonical reference for every platform concept |
| `archagent-docs-map` | Curated index of the most useful docs URLs |
| `archagent-integration-patterns` | Seven trigger/handler shapes that cover most integrations |
| `archagent-troubleshooting` | Debug broken agents, scripts, routines, memory, and configs |

## The custom tool

- `fetch_archagents_docs` fetches a docs.archagents.com page as Markdown.
  Pass a path like `/docs/start-here/getting-started`, a full URL, or
  `"llms-full.txt"` for the full machine-readable index.

Everything else is builtin tools: `skills`, `knowledge_search`,
`long_term_memory`, `memory`, and `search`.

## Setup

```bash
# The concierge has no required env vars.
# Deploy scripts + agent + all 15 skills in one shot:
archagent install agentsample archastro
```

## Using ArchAstro

```bash
archagent create agentsession \
  --agent archastro \
  --instructions "Help me debug why my routine is not firing." \
  --wait
```

## Customization

For a specific agent network org, fork the YAML and add org-specific context
to the `identity` block. Keep the bundled skills and docs-fetch tool intact
unless the org needs a narrower support surface.

## Files

```
archastro/
├── README.md
├── agent.yaml
├── env.example
├── sample.yaml
├── scripts/
│   └── archastro-fetch-archagents-docs.aascript
└── skills/
    ├── archastro-engagement-playbook/SKILL.md
    ├── archagent-concepts/SKILL.md
    ├── archagent-docs-map/SKILL.md
    ├── archagent-integration-patterns/SKILL.md
    ├── archagent-troubleshooting/SKILL.md
    ├── archagent-install/SKILL.md
    ├── archagent-auth/SKILL.md
    ├── archagent-manage-configs/SKILL.md
    ├── archagent-author-agent/SKILL.md
    ├── archagent-build-script/SKILL.md
    ├── archagent-build-workflow/SKILL.md
    ├── archagent-build-skill/SKILL.md
    ├── archagent-deploy-agent/SKILL.md
    ├── archagent-chat/SKILL.md
    └── archagent-impersonate/SKILL.md
```
