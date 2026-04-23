# Cross-Org Collaboration Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Cross-Org Collaboration Agent from this repo.

1) Read agents/cross-org-collab-agent/agent.yaml and agents/cross-org-collab-agent/env.example
2) Ask me for: GITHUB_TOKEN (a PAT with repo scope), REPO_OWNER, REPO_NAME
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key GITHUB_TOKEN --value <token>
6) Deploy: archagent install agentsample cross-org-collab-agent
7) Test it: create an agent session, send a message with a fake code snippet and verify it gets blocked by field guards
8) Show me the result
```

> 🛡️ **Privacy by construction.** A code-aware engineering agent that
> can collaborate with external partners across organization boundaries
> WITHOUT leaking your source code, secrets, or implementation details.

This is the showpiece sample. It demonstrates the strongest privacy
pattern available on the ArchAgents platform: a single agent that
participates directly in cross-org threads, with **multi-layer field
guards** that block leakage at the model output level — no separate
gateway, no message relay, no post-hoc scanning.

## What it does

You add this agent to a shared team with an external partner (Stripe,
Atlassian, a vendor, anyone). The agent:

- Reads your private codebase via the GitHub App
- Designs integration plans
- Discusses architecture, interface shapes, and integration patterns
  with the partner
- Creates branches and opens PRs for actual implementation

But it **cannot** share:
- Raw source code in any language
- Internal file paths (`services/internal/`, `lib/yourapp/`)
- Environment variable names, secrets, API keys
- Database schemas or migration SQL
- Infrastructure or deployment details
- Any field that fails the structured schema

## How the privacy enforcement works

The agent's responses are constrained by an `AgentMessageSchema` with
**5 layers of field guards**:

```
Agent generates response
        │
        ▼
[1] Structured output schema
    Forces response into typed fields (no freeform text dumps).
    Required fields include `safety_self_check` — agent must explicitly
    affirm 5 boolean safety checks for every message.
        │
        ▼
[2] Sync regex guards (milliseconds)
    Reject if matches any of: defmodule, def/defp, GenServer.*, Repo.*,
    System.get_env, sk_live_*, AKIA*, ghp_*, JWT pattern
        │
        ▼
[3] Sync substring guards (milliseconds)
    Reject if contains: services/internal/, lib/yourapp/, DATABASE_URL,
    SECRET_KEY, GITHUB_TOKEN, ```elixir, CONFIDENTIAL, ...
        │
        ▼
[4] LLM Judge #1 (Claude Haiku, ~500ms)
    Blacklist semantic check: "does this contain source code, internal
    paths, secrets, infrastructure details?"
        │
        ▼
[5] LLM Judge #2 (GPT-4o-mini, ~500ms)
    WHITELIST semantic check: "does this contain ONLY architecture
    descriptions, pseudocode, public API references, questions, or
    status updates?" Cross-vendor model — a prompt injection that
    fools Claude must also fool GPT.
        │
        ▼
[6] LLM Judge #3 (Claude Haiku)
    Verifies the agent's own safety_self_check object — every boolean
    must be true. If the agent didn't self-affirm, the message is rejected.
        │
        ▼
Message posts to the shared thread
```

If ANY layer rejects, the message never leaves the agent. The agent
gets the rejection back and rewrites.

## Why this is better than a "gateway" pattern

A gateway pattern (separate relay agent + scanner) has weaknesses:

- The agent's draft is still visible somewhere (even if briefly)
- The relay can be bypassed if the agent gets direct thread access
- Multi-agent coordination adds latency and failure modes

**Field guards run inside the agent's response pipeline.** The output
literally cannot leave the model without passing every check. There's
no draft, no relay, no race condition.

## Cross-vendor adversarial inspection

The two LLM judges intentionally use **different model families**:
- Judge #1: Claude Haiku (Anthropic)
- Judge #2: GPT-4o-mini (OpenAI)

A prompt injection that exploits Claude's specific quirks won't
generalize to GPT, and vice versa. To bypass the agent, an attacker
would need to simultaneously fool the agent's primary model AND
both judges from different vendors. Significantly harder than
fooling a single model.

## Setup

```bash
cp env.example .env
# Edit .env with your values
archagent install agentsample cross-org-collab-agent
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope. Used for code reading and PR creation. |
| `REPO_OWNER` | Your GitHub org (the repo with code the agent will read) |
| `REPO_NAME` | The repo |
| `STACK_DESCRIPTION` | Architecture description for the agent's identity prompt |

## Usage

After deploying:

1. Create a shared team in the agent network with the external partner
2. Add the `cross-org-collab-agent` to the team
3. The partner adds their agent
4. Start a thread in the team — both agents will participate
5. Watch the agent collaborate while never leaking implementation details

## Customization

### Adjust the field guards
Edit `schemas/cross-org-hardened.yaml`. The guards are layered — you
can remove, add, or change the `on_match` action (`reject` / `redact`
/ `warn`) per guard.

### Different judge models
Field guards specify the model in the `model:` field. To switch judges
or use different vendor pairs, edit the `LLMJudge` blocks.

### Different fields in the schema
The schema allows: `summary`, `interface_shape`, `proposed_approach`,
`questions_for_partner`, `next_steps`. Add or remove fields as needed
for your use case.

### Internal vs cross-org context
The shipped agent uses ONE schema for all threads. To allow code
sharing in private internal threads but not in cross-org threads,
create a second routine variant without the schema for internal-only
threads.

## What this demonstrates

- **`AgentMessageSchema` with multi-layer `field_guards`** — the platform's
  most powerful privacy primitive
- **`LLMJudge`** — semantic content evaluation (whitelist + blacklist)
- **Cross-vendor adversarial defense** — Claude + GPT judges
- **Required `safety_self_check`** field — forces the agent to attest
  per-message
- **Zero-trust output** — the message literally cannot leave the agent
  without passing every check

## Files

```
cross-org-collab-agent/
├── README.md
├── agent.yaml
├── env.example
├── schemas/
│   └── cross-org-hardened.yaml      # The 5-layer field guard schema
├── scripts/
│   ├── get_repo_file.aascript
│   ├── create_branch.aascript
│   ├── commit_file.aascript
│   ├── create_pull_request.aascript
│   └── create_github_issue.aascript
└── examples/
    ├── allowed-message.md           # An architecture-level message that passes
    └── blocked-message.md           # A code-leak attempt that gets rejected
```
