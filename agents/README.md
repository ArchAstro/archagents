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

## Customizing

These agents are starting points. Fork the identity prompt, swap the
model, add tools, change the schedule — make them yours.

The [CLI docs](https://docs.archagents.com) and the
[archagents plugin](https://github.com/ArchAstro/archagents) for
Claude Code / Codex can help you author and deploy changes.
