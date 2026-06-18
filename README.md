# ArchAgents

[![check-plugin-content](https://github.com/ArchAstro/archagents/actions/workflows/check-plugin-content.yml/badge.svg)](https://github.com/ArchAstro/archagents/actions/workflows/check-plugin-content.yml)
[![installer-smoke-test](https://github.com/ArchAstro/archagents/actions/workflows/installer-smoke-test.yml/badge.svg)](https://github.com/ArchAstro/archagents/actions/workflows/installer-smoke-test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[ArchAgents](https://archagents.com) accelerates post-sales work —
discovery, integration, migration, and the long tail of customer-specific
code — with agents that run on webhooks, schedules, and API triggers.
Import a production-ready sample Solution from this repo (PR review,
compliance, security triage, changelogs, and more), or build your own:
define behavior in YAML, plug in any model, add custom tools and routines.

## Try it now

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Set up ArchAgents in this repo and deploy a working agent I can test.

1) Read https://docs.archagents.com/llms-full.txt
2) Ask me for my email and any missing credentials
3) Install the CLI: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Pick the best sample Solution from solutions/ for my use case and import it
6) Show me which AgentTemplate, tool templates, routine templates, and setup actions were imported
7) Summarize how to install the imported template into my app
```

Or run the quickstart directly:

```bash
git clone https://github.com/ArchAstro/archagents.git
cd archagents
./quickstart.sh you@company.com
```

This imports the Onboarding Q&A Solution so you can install the bundled
AgentTemplate from the catalog.

## Sample Solutions

| Solution | What it does | Trigger |
|---|---|---|
| [Code Review](solutions/code-review-agent-sample) | Reviews every PR with verified inline comments | PR webhook |
| [Compliance Reviewer](solutions/compliance-reviewer-sample) | Checks PRs against SOC2 / GDPR / your custom rules | PR webhook |
| [Cross-Org Collab](solutions/cross-org-collab-agent-sample) | Privacy-by-construction — field guards block code leaks in shared threads | Thread join |
| [Onboarding Q&A](solutions/onboarding-qa-sample) | Answers new-hire questions from your knowledge base | Thread join |
| [Platform Health](solutions/platform-health-agent-sample) | Daily repo health, GitHub event alerts, and 5xx digests | Mixed |
| [Release Notes](solutions/release-notes-bot-sample) | Drafts weekly changelog from merged PRs | Weekly cron |
| [Security Triage](solutions/security-triage-agent-sample) | Scans dependencies for CVEs, auto-fixes simple ones, escalates the rest | Daily cron |
| [Threat Intel](solutions/threat-intel-agent-sample) | Daily security brief from HN + GitHub Advisories cross-referenced against your stack | Daily cron |

Each Solution bundle has its own README and ships a deployable
AgentTemplate plus any standalone custom tool and routine templates.

## Recipes: agents working together

These templates are designed to compose. Install multiples into the same
repo for layered coverage:

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

Install the local Claude Code and Codex plugins with the setup command:

```bash
archagent setup
```

To install into the current project instead of your user-level config:

```bash
archagent setup --scope project
```

The `archagents` plugin bundles CLI auth, agent authoring, script and
workflow builders, deployment, chat, config management, and embed.

## CI

Sample validation and release workflows use
[`ArchAstro/archastro-github-actions`](https://github.com/ArchAstro/archastro-github-actions):

- `validate-sample-scripts.yml` schema-validates `agents/` and `solutions/` bundles.
- `check-sample-version-bumps.yml` requires changed samples to bump `sample.yaml` `version:`.
- `release-samples.yml` creates missing `<slug>-<version>.tar.gz` GitHub Releases and deploys solution samples.

The release-and-deploy job passes `ARCHASTRO_CI_ACCESS_TOKEN` to the
reusable action as the ArchAstro system-user token and sets `owner: system`
so solution samples deploy through the system-owned `archastro` path.

## Docs

- [Getting Started](https://docs.archagents.com/docs/getting-started) — zero to one working agent
- [For Coding Agents](https://docs.archagents.com/docs/for-coding-agents) — machine-friendly setup
- [CLI Reference](https://docs.archagents.com/docs/cli) — terminal workflow
- [Agents](https://docs.archagents.com/docs/agents) — the full agent model
