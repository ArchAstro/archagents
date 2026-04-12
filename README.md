# ArchAgents

Production-ready agents you can deploy in minutes. Review PRs, triage
vulnerabilities, enforce compliance, generate changelogs, and more —
each agent comes with identity, tools, routines, and a one-command deploy.

## Try it now

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Set up ArchAgents in this repo and deploy a working agent I can test.

1) Read https://docs.archagents.com/llms-full.txt
2) Ask me for my email and any missing credentials
3) Install the CLI: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Pick the best sample agent from agents/ for my use case and deploy it
6) Test it with a real prompt and show me the result
7) Summarize what was created and how to use it
```

Or run the quickstart directly:

```bash
git clone https://github.com/ArchAstro/archagents.git
cd archagents
./quickstart.sh you@company.com
```

This deploys the Onboarding Q&A agent with a sample knowledge base and
asks it a question — working agent in 60 seconds.

## Sample Agents

| Agent | What it does | Trigger |
|---|---|---|
| [Code Review](agents/code-review-agent) | Reviews every PR with verified inline comments | PR webhook |
| [Compliance Reviewer](agents/compliance-reviewer) | Checks PRs against SOC2 / GDPR / your custom rules | PR webhook |
| [Cross-Org Collab](agents/cross-org-collab-agent) | Privacy-by-construction — field guards block code leaks in shared threads | Thread join |
| [Onboarding Q&A](agents/onboarding-qa) | Answers new-hire questions from your knowledge base | Thread join |
| [Release Notes](agents/release-notes-bot) | Drafts weekly changelog from merged PRs | Weekly cron |
| [Security Triage](agents/security-triage-agent) | Scans dependencies for CVEs, auto-fixes simple ones, escalates the rest | Daily cron |
| [Threat Intel](agents/threat-intel-agent) | Daily security brief from HN + GitHub Advisories cross-referenced against your stack | Daily cron |

Each agent has its own README with a **"Deploy with your coding agent"**
prompt block — paste it and go.

## Recipes: agents working together

These agents are designed to compose. Deploy multiples on the same repo
for layered coverage:

**PR Review Pipeline** — Code Review + Compliance Reviewer on the same
repo. One reviews architecture and correctness, the other reviews
against your compliance rules. Same webhook, two perspectives.

**Security Operations** — Threat Intel runs the morning brief, Security
Triage scans and triages throughout the day. The threat brief identifies
what to watch; the triage agent acts on what's exploitable.

**Dev Lifecycle** — Code Review catches issues on every PR, Release Notes
Bot drafts the weekly changelog from the same PRs once they merge. The
review history informs what's worth highlighting in the notes.

## Install the CLI

### macOS

```bash
brew install ArchAstro/tools/archagent
```

### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
```

### Windows

```powershell
irm https://raw.githubusercontent.com/ArchAstro/archagents/main/install.ps1 | iex
```

## Plugins for AI coding assistants

### Claude Code

```text
/plugin marketplace add archastro/archagents
/plugin install archagents@archagents
```

### Codex

```text
git clone https://github.com/ArchAstro/archagents.git
cd archagents && codex
/plugins
```

The `archagents` plugin bundles CLI auth, agent authoring, script and
workflow builders, deployment, chat, config management, and
impersonation.

## Docs

- [Getting Started](https://docs.archagents.com/docs/getting-started) — zero to one working agent
- [For Coding Agents](https://docs.archagents.com/docs/for-coding-agents) — machine-friendly setup
- [CLI Reference](https://docs.archagents.com/docs/cli) — terminal workflow
- [Agents](https://docs.archagents.com/docs/agents) — the full agent model
