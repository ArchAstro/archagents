# Sample Agents

Production-grade agents you can deploy to the ArchAgents platform in
minutes. Every sample includes the agent identity, custom scripts,
routines, and a deploy script — set a few env vars and `./deploy.sh`.

## Agents

| Agent | What it does |
|---|---|
| [code-review-agent](code-review-agent) | Reviews every PR, posts inline comments anchored to specific lines |
| [compliance-reviewer](compliance-reviewer) | Reviews PRs against SOC2 / GDPR / your custom compliance rules |
| [cross-org-collab-agent](cross-org-collab-agent) | Privacy by construction — multi-layer field guards for cross-org threads |
| [archagent-fde](archagent-fde) | A Forward Deployed Engineer for ArchAgents — 15 bundled skills, impersonate-into-Claude-Code ready |
| [onboarding-qa](onboarding-qa) | Answers new-hire questions from your knowledge base |
| [release-notes-bot](release-notes-bot) | Watches merged PRs weekly, drafts changelog as a GitHub issue |
| [security-triage-agent](security-triage-agent) | Daily dependency scan, auto-fix simple CVEs, escalate the rest |
| [threat-intel-agent](threat-intel-agent) | Daily security brief from HN + GitHub Advisories + your dependency exposure |

## Quick start

```bash
# 1. Install the CLI
brew install ArchAstro/tools/archagent

# 2. Authenticate
archagent auth login you@company.com

# 3. Link your project
archagent init

# 4. Pick an agent and deploy
cd agents/code-review-agent
cp env.example .env
# Fill in your values (GITHUB_TOKEN, etc.)
./deploy.sh
```

Each agent's README has setup details, required env vars, and example output.

## Structure

Every agent follows the same layout:

```
agent-name/
  README.md        — what it does, how to configure it
  agent.yaml       — the AgentTemplate (identity, tools, routines, installations)
  deploy.sh        — one-command deploy script
  env.example      — required environment variables
  scripts/         — custom ArchAstro scripts (PAT-based GitHub tools, etc.)
  examples/        — sample output so you know what to expect
```

## Recipes: agents working together

These agents compose. Deploy multiples on the same repo for
layered automation:

### PR Review Pipeline

Deploy **Code Review** + **Compliance Reviewer** on the same repo.
Both trigger on `webhook.github_app.pull_request`. One reviews
architecture and correctness, the other checks compliance rules.
Same webhook, two agents, two different sets of inline comments.

```bash
cd code-review-agent && ./deploy.sh
cd ../compliance-reviewer && ./deploy.sh
# Both now review every PR — install the GitHub App on your repo
```

### Security Operations

**Threat Intel** runs a daily morning brief (HN + GitHub Advisories
cross-referenced against your lockfiles). **Security Triage** runs
a daily dependency scan, auto-fixes simple CVEs with PRs, and
escalates the rest as GitHub issues. Together they cover awareness
and action.

```bash
cd threat-intel-agent && ./deploy.sh
cd ../security-triage-agent && ./deploy.sh
# Daily brief at 07:00 UTC, dependency scan at 08:00 UTC
```

### Dev Lifecycle

**Code Review** catches issues on PRs. **Release Notes Bot** drafts
the weekly changelog from the same PRs once they merge. The review
history informs what's worth highlighting in the notes.

```bash
cd code-review-agent && ./deploy.sh
cd ../release-notes-bot && ./deploy.sh
# Reviews land instantly, changelog drafts every Monday
```

## Customizing

These agents are starting points. Fork the identity prompt, swap the
model, add tools, change the schedule — make them yours.

```bash
# Change the model
archagent update agent <id> -m claude-sonnet-latest

# Edit the identity
archagent edit agent <id>

# Change a cron schedule
archagent update agentroutine <id> --schedule "0 9 * * MON"
```

The [CLI docs](https://docs.archagents.com) and the
[archagents plugin](https://github.com/ArchAstro/archagents) for
Claude Code / Codex can help you author and deploy changes.
