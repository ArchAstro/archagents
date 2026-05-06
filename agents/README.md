# Sample Agents

Production-grade agents you can deploy to the ArchAgents platform in
minutes. Every sample includes the agent identity, custom scripts,
routines, and its deploy sequence declared in `sample.yaml` — one CLI
command installs the whole thing.

## Agents

| Agent | What it does |
|---|---|
| [archastro](archastro) | Default ArchAstro concierge for ongoing project and account maintenance |
| [archastro-onboarding](archastro-onboarding) | Guides a new user through setting up their first agent in ArchAstro |
| [code-review-agent](code-review-agent) | Reviews every PR, posts inline comments anchored to specific lines |
| [compliance-reviewer](compliance-reviewer) | Reviews PRs against SOC2 / GDPR / your custom compliance rules |
| [cross-org-collab-agent](cross-org-collab-agent) | Privacy by construction — multi-layer field guards for cross-org threads |
| [fde-agent](fde-agent) | Generic Forward Deployed Engineer base agent for customers to specialize with their own docs and knowledge |
| [onboarding-qa](onboarding-qa) | Answers new-hire questions from your knowledge base |
| [platform-health-agent](platform-health-agent) | Daily report on repo health, GitHub event alerts, and a 5xx digest from production logs — delivered to Slack |
| [release-notes-bot](release-notes-bot) | Watches merged PRs weekly, drafts changelog as a GitHub issue |
| [security-triage-agent](security-triage-agent) | Daily dependency scan, auto-fix simple CVEs, escalate the rest |
| [threat-intel-agent](threat-intel-agent) | Daily security brief from HN + GitHub Advisories + your dependency exposure |

## Quick start

```bash
# 1. Install the CLI
brew install ArchAstro/tools/archagent

# 2. Authenticate
archagent auth login you@company.com

# 3. Pick an agent and deploy
archagent install agentsample code-review-agent
```

`install agentsample <slug>` fetches the sample's release tarball,
parses its `sample.yaml`'s `steps:` block, and runs every step
(scripts upload, skills upload, agent create, knowledge ingest) in
one pass. Nothing lands on your disk — the sample deploys straight
to your app.

Most samples have a few setup actions to finish after install
(agent-scoped env vars, GitHub App installs, Slack bot installs,
verifiers, etc.). The developer portal reads each sample's
`setup_requirements:` block and shows those actions in the agent's
"Finish setup" panel.

### GitHub authentication in samples

Several samples currently use `GITHUB_TOKEN` from their custom scripts
because they call GitHub REST endpoints directly. For those samples,
use a fine-grained PAT whenever possible and grant only the permissions
the sample README lists. A classic `repo` token still works, but is
broader than most samples need.

GitHub App installation is separate: it delivers `webhook.github_app.*`
events to routines, and some samples use App-backed integration tools
for writes. If a sample still lists `GITHUB_TOKEN`, the token is still
required for that sample's script-level GitHub API calls.

## Structure

Every sample follows the same layout:

```
agent-name/
  README.md        — what it does, how to configure it
  agent.yaml       — the AgentTemplate (identity, tools, routines, installations)
  sample.yaml      — catalog metadata + the `steps:` block that drives deploy
  env.example      — local reference for required agent environment variables
  scripts/         — custom ArchAstro scripts, including GitHub API calls
  skills/          — (some samples) markdown skills the agent loads on demand
  schemas/         — (some samples) message-schema configs referenced by agent.yaml
  rules/           — (compliance-reviewer) markdown rules uploaded as knowledge
  knowledge/       — (onboarding-qa) markdown docs seeded into the knowledge base
  examples/        — sample output so you know what to expect
```

## Recipes: agents working together

These agents compose. Deploy multiples on the same repo for layered
automation:

### PR Review Pipeline

Deploy **Code Review** + **Compliance Reviewer** on the same repo.
Both trigger on `webhook.github_app.pull_request`. One reviews
architecture and correctness, the other checks compliance rules.
Same webhook, two agents, two different sets of inline comments.

```bash
archagent install agentsample code-review-agent
archagent install agentsample compliance-reviewer
# Both now review every PR — install the GitHub App on your repo
```

### Security Operations

**Threat Intel** runs a daily morning brief (HN + GitHub Advisories
cross-referenced against your lockfiles). **Security Triage** runs
a daily dependency scan, auto-fixes simple CVEs with PRs, and
escalates the rest as GitHub issues. Together they cover awareness
and action.

```bash
archagent install agentsample threat-intel-agent
archagent install agentsample security-triage-agent
# Daily brief at 07:00 UTC, dependency scan at 08:00 UTC
```

### Dev Lifecycle

**Code Review** catches issues on PRs. **Release Notes Bot** drafts
the weekly changelog from the same PRs once they merge. The review
history informs what's worth highlighting in the notes.

```bash
archagent install agentsample code-review-agent
archagent install agentsample release-notes-bot
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

## Hacking on a sample locally

Clone this repo, edit a sample, deploy from your checkout without
waiting for a release:

```bash
cd agents/code-review-agent
archagent install sample .
```

`install sample [path]` reads `sample.yaml` from the given directory
and runs the same executor as `install agentsample <slug>` — useful
for iterating on `agent.yaml`, scripts, or `steps:` before cutting a
release.

The [CLI docs](https://docs.archagents.com) and the
[archagents plugin](https://github.com/ArchAstro/archagents) for
Claude Code / Codex can help you author and deploy changes.
