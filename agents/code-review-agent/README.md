# Code Review Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Code Review Agent from this repo.

1) Read agents/code-review-agent/agent.yaml and agents/code-review-agent/env.example
2) Ask me for: GITHUB_TOKEN (a PAT with repo scope)
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key GITHUB_TOKEN --value <token>
6) Deploy: archagent install agentsample code-review-agent
7) Test it: create an agent session and ask it to review the most recent open PR in ArchAstro/archagents
8) Show me the result
```

> 🤖 **Reviews every pull request like a senior engineer who actually cares.**

Posts inline review comments anchored to specific files and lines on
every PR opened in your repo. Reads the actual code being changed,
verifies findings against the surrounding context, and only flags real
issues — never speculation, never style nits.

## What it does

When a PR is opened or updated:

1. **Dedup check** — confirms the action is `opened` or `synchronize`, and
   that no review from this agent already exists on the current commit
2. **Reads the diff** via the GitHub API
3. **Reads the actual called code** for any function references in the diff
   so it can verify rather than guess
4. **Force-ranks findings** by severity using a "would you mass-revert
   production for this?" test
5. **Posts up to 8 inline comments** anchored to specific file/line locations
6. **Stays silent if there's nothing to flag** — silence is approval

## What it won't do

- Post style or documentation suggestions
- Speculate about code it hasn't read
- Post the same finding on multiple lines
- Write summaries, preambles, or "overall this looks good" comments
- Approve PRs (humans approve)

## Setup

```bash
# 1. Set required env vars
cp env.example .env
# Edit .env with your GITHUB_TOKEN and other values

# 2. Deploy
archagent install agentsample code-review-agent
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | Personal access token with `repo` scope. Reviews will post as this account. |
| `REPO_OWNER` | GitHub org/user the agent reviews PRs for (e.g., `your-org`) |
| `REPO_NAME` | Repository name (e.g., `your-repo`) |

For multi-repo support, the agent reads `REPO_OWNER` and `REPO_NAME` as
defaults but the GitHub webhook tells it which repo each PR is in, so
it works across all repos the GitHub App is installed in.

## How it triggers

The agent has a webhook routine that fires on
`webhook.github_app.pull_request` events. Install the ArchAstro GitHub
App on your org and the routine will fire automatically.

## Customization

### Different review style

Edit `agent.yaml` `identity` block. The shipped persona is "tough but
fair, occasionally funny, technical substance first." Some teams prefer
"strictly factual, no personality." Both work — the persona only
affects tone, not what gets flagged.

### Different comment budget

Search for `MAX 8` in `agent.yaml` and change the number. The agent
will force-rank findings by severity and post the top N.

### Different language stack

The shipped agent is language-agnostic but the **examples** in the
identity prompt use Elixir conventions. If your stack is Python/Go/etc.,
update the example references in the identity to match.

### Different model

Change the `default_model` in your portal or via:
```bash
archagent update agents code-review-agent --default-model openrouter/anthropic/claude-sonnet-latest
```

We've tested this agent on Claude Opus 4, Claude Sonnet, and GPT-5.
Sonnet is the recommended default — strong reasoning at low cost.

## Example output

See [examples/sample-review.md](examples/sample-review.md).

## What this demonstrates

This sample showcases:

- **Webhook-triggered routines** — `webhook.github_app.pull_request` event
- **Custom scripts** — five small scripts wrap the GitHub REST API
- **Long-term memory** — dedup check stores `Reviewing PR #N at commit SHA`
- **Skills** — the `code-review` skill is loaded on demand to keep the
  identity prompt small
- **GitHub App integration** — read PRs, read file contents, post reviews

## Files

```
code-review-agent/
├── README.md                    # this file
├── agent.yaml                   # AgentTemplate config
├── env.example                  # required env vars
├── scripts/
│   ├── get_pr_files.aascript    # GET /pulls/{n}/files
│   ├── get_repo_file.aascript   # GET /repos/{o}/{r}/contents/{path}
│   ├── list_pr_reviews.aascript # GET /pulls/{n}/reviews
│   ├── create_pr_review.aascript # POST /pulls/{n}/reviews with inline comments
│   └── resolve_review_threads.aascript # GraphQL: resolve own threads
├── skills/
│   └── code-review/SKILL.md     # full review rubric (loaded on demand)
└── examples/
    └── sample-review.md         # example output on a real PR
```
